# -*- coding: utf-8 -*-
"""
数据导出路由
- /api/export/energy_records：导出能耗记录为 CSV / XLSX

设计要点：
1. 参数化 SQL，杜绝注入（沿用 devices.py 风格）
2. limit 强制上限 10000，防止超大导出拖垮内存
3. CSV 走 StringIO + StreamingResponse（pandas to_csv）
4. XLSX 走 BytesIO + pandas to_excel（openpyxl 引擎）
5. slowapi 限流 5/minute（导出是重操作）
6. require_auth 鉴权
7. 异常时返回 JSON 错误信息（保持与 report.py 一致）
"""
import io
import logging
import datetime

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.database import get_conn, DBUnavailableError
from app.core.rate_limit import limiter
from app.core.security import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# 导出条数硬上限（防止超大导出拖垮内存）
MAX_EXPORT_LIMIT = 10000
# 默认导出列（按业务可读顺序排列）
DEFAULT_COLUMNS = [
    "record_id", "device_id", "monitor_time", "building_id", "building_type",
    "device_name", "param_type", "elec_consumption", "hvac_consumption",
    "water_consumption", "hvac_mode", "supply_temp", "return_temp",
    "water_flow_rate", "delta_temp", "cooling_load", "cop", "loading_rate",
    "eer", "power_factor", "current_unbalance", "condensing_water_temp",
    "system_pressure_diff", "fan_speed", "vfd_frequency", "carbon_emission",
    "electricity_cost", "run_status", "fault_code",
]


def _build_query(
    start_date: str | None,
    end_date: str | None,
    building_id: str | None,
    device_id: str | None,
    limit: int,
) -> tuple[str, list]:
    """构造参数化查询 SQL，返回 (sql, params)"""
    query = "SELECT * FROM fact_energy_records WHERE 1=1"
    params: list = []

    if start_date:
        query += " AND monitor_time >= ?"
        params.append(f"{start_date} 00:00:00")
    if end_date:
        query += " AND monitor_time <= ?"
        params.append(f"{end_date} 23:59:59")
    if building_id:
        query += " AND building_id = ?"
        params.append(building_id)
    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)

    query += " ORDER BY monitor_time DESC LIMIT ?"
    params.append(limit)
    return query, params


@router.get("/api/export/energy_records")
@limiter.limit("5/minute")
async def export_energy_records(
    request: Request,
    user: str = Depends(require_auth),
    start_date: str | None = Query(None, description="起始日期，如 2026-07-01"),
    end_date: str | None = Query(None, description="结束日期，如 2026-07-28"),
    building_id: str | None = Query(None, description="建筑ID（可选）"),
    device_id: str | None = Query(None, description="设备ID（可选）"),
    format: str = Query("csv", description="导出格式：csv 或 xlsx"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大导出条数"),
):
    """
    导出能耗记录为 CSV / XLSX
    - 限流：5 次/分钟（导出是重操作）
    - 默认导出 10000 条，硬上限 10000
    - format=csv 返回 text/csv；format=xlsx 返回 Excel 二进制流
    """
    fmt = (format or "csv").lower()
    if fmt not in ("csv", "xlsx"):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"不支持的导出格式: {format}，仅支持 csv / xlsx"},
        )

    try:
        sql, params = _build_query(start_date, end_date, building_id, device_id, limit)

        with get_conn() as conn:
            df = pd.read_sql(sql, conn, params=params)

        # 仅保留业务可读列（容错：缺失列自动跳过）
        cols = [c for c in DEFAULT_COLUMNS if c in df.columns]
        df = df[cols]

        # 空数据也允许导出（带表头），便于下游流程对接
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"energy_records_{timestamp}"

        if fmt == "csv":
            stream = io.StringIO()
            df.to_csv(stream, index=False, encoding="utf-8-sig")  # utf-8-sig 兼容 Excel 中文
            stream.seek(0)

            def csv_iter():
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    yield chunk

            return StreamingResponse(
                csv_iter(),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename={base_name}.csv"},
            )
        else:
            # xlsx：用 BytesIO + openpyxl 引擎生成
            stream = io.BytesIO()
            with pd.ExcelWriter(stream, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="energy_records")
            stream.seek(0)

            def xlsx_iter():
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    yield chunk

            return StreamingResponse(
                xlsx_iter(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={base_name}.xlsx"},
            )
    except DBUnavailableError:
        # 由全局异常处理器返回 503
        raise
    except Exception as e:
        logger.exception(f"导出能耗记录失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "导出失败，请稍后重试或联系管理员"},
        )
