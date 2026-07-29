# -*- coding: utf-8 -*-
"""
AR 远程运维路由
- /api/ar/device/{device_id}：通过设备标识（二维码/AR锚点）获取设备实时数据叠加层
- /api/ar/work_orders/{device_id}：获取该设备的历史工单
- /api/ar/manual/{device_id}：获取设备维修手册片段
- /api/ar/annotate：保存现场运维人员的标注（持久化到数据库）
- /api/ar/annotations：查询标注列表
- /api/ar/devices：获取可用的 AR 设备清单（从 dim_devices 真实读取）

设计目的：现场人员用手机摄像头扫描设备二维码，立即在 AR 界面叠加：
1. 实时运行参数（温度、压力、COP 等）
2. 最近告警与工单
3. 关键检修步骤
4. 现场拍照标注上传（持久化到数据库，跨会话保留）
"""
import logging
import datetime
import json
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_annotation_table():
    """确保 AR 标注表存在（幂等创建）"""
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sys_ar_annotations (
                    id VARCHAR(64) PRIMARY KEY,
                    device_id VARCHAR(50) NOT NULL,
                    operator VARCHAR(100) DEFAULT 'anonymous',
                    note TEXT,
                    photo_url TEXT,
                    location TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ar_anno_device ON sys_ar_annotations(device_id, created_at)")
            conn.commit()
    except Exception as e:
        logger.warning(f"创建 AR 标注表失败: {e}")


# ===== 设备类型 → 维修手册映射（基于暖通工程知识库）=====
_MANUAL_LIBRARY = {
    "HVAC": {
        "title": "冷水机组/空调维保要点",
        "steps": [
            "1. 检查制冷剂压力（高压 1.6MPa / 低压 0.4MPa）",
            "2. 检查油位与油温（30-65℃）",
            "3. 清洗冷凝器铜管（每年 1 次）",
            "4. 校验安全保护装置",
            "5. 检查导叶开度与电机电流",
        ],
        "warning": "⚠️ 维护前必须断电并挂警示牌",
    },
    "PUMP": {
        "title": "水泵维保要点",
        "steps": [
            "1. 检查机械密封泄漏情况",
            "2. 测量轴承振动（< 4.5mm/s）",
            "3. 检查联轴器对中",
            "4. 加注润滑脂（每月 1 次）",
            "5. 检查电机绝缘",
        ],
        "warning": "⚠️ 维护前关闭进出口阀门",
    },
    "PRECISION_AC": {
        "title": "精密空调维保要点",
        "steps": [
            "1. 检查室内外机清洁度",
            "2. 校验温湿度传感器精度",
            "3. 检查制冷剂高压低压",
            "4. 测试应急排水",
            "5. 检查加湿系统",
        ],
        "warning": "⚠️ 维护前断电并关闭冷冻水阀",
    },
    "EV_CHARGER": {
        "title": "充电桩维保要点",
        "steps": [
            "1. 检查充电枪接口磨损",
            "2. 测试漏电保护",
            "3. 检查通讯连接",
            "4. 清洁散热风扇",
            "5. 校验计量精度",
        ],
        "warning": "⚠️ 维护前断开主电源",
    },
    "LIGHTING": {
        "title": "照明系统维保要点",
        "steps": [
            "1. 检查 LED 光衰（年衰减 < 5%）",
            "2. 清洁灯具表面",
            "3. 检查驱动电源温升",
            "4. 校验照度达标",
            "5. 测试应急照明切换",
        ],
        "warning": "⚠️ 维护前断电",
    },
    "VENTILATION": {
        "title": "新风机组维保要点",
        "steps": [
            "1. 更换或清洗过滤网（每月 1 次）",
            "2. 检查皮带张紧度",
            "3. 清洗表冷器",
            "4. 检查冷凝水管排水",
            "5. 校验温湿度传感器",
        ],
        "warning": "⚠️ 维护前断电并关闭冷冻水阀",
    },
    "SOCKET": {
        "title": "插座线路维保要点",
        "steps": [
            "1. 检查插座接触良好性",
            "2. 测试接地连续性",
            "3. 紧固接线端子",
            "4. 检查漏电保护",
            "5. 测量回路负载",
        ],
        "warning": "⚠️ 维护前断开对应回路断路器",
    },
    "REFRIGERATION": {
        "title": "冷库维保要点",
        "steps": [
            "1. 检查制冷剂高压低压",
            "2. 除霜系统测试",
            "3. 检查门封条密封性",
            "4. 清洁冷凝器",
            "5. 校验库温均匀性",
        ],
        "warning": "⚠️ 维护前断电并佩戴防护装备",
    },
    "WATER_HEATER": {
        "title": "空气源热泵维保要点",
        "steps": [
            "1. 清洗蒸发器翅片",
            "2. 检查制冷剂充注量",
            "3. 校验高低压保护",
            "4. 检查水箱镁棒",
            "5. 测试化霜功能",
        ],
        "warning": "⚠️ 维护前断电并关闭水阀",
    },
}


@router.get("/api/ar/devices")
@run_in_thread
def ar_device_list():
    """获取可用于 AR 扫描的设备清单（从 dim_devices 真实读取，含空间信息）"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT d.device_id, d.device_name, d.device_type, d.building_id,
                       d.space_id, b.building_name, s.space_name
                FROM dim_devices d
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                LEFT JOIN dim_spaces s ON s.space_id = d.space_id
                ORDER BY d.building_id, d.space_id, d.device_type, d.device_id
            """)
            devices = []
            for row in cur.fetchall():
                r = dict(row)
                building_name = r.get("building_name") or r["building_id"]
                space_name = r.get("space_name") or r.get("space_id") or "-"
                devices.append({
                    "device_id": r["device_id"],
                    "device_name": r["device_name"],
                    "device_type": r["device_type"],
                    "building_id": r["building_id"],
                    "building_name": building_name,
                    "space_id": r.get("space_id"),
                    "space_name": space_name,
                    "label": f"{r['device_name']}（{building_name} / {space_name}）",
                })
            return {"status": "success", "data": devices, "total": len(devices)}
    except Exception as e:
        return handle_route_error(e, logger, "AR 设备列表查询", extra_fields={"data": []})


@router.get("/api/ar/device/{device_id}")
@run_in_thread
def ar_device_overlay(device_id: str):
    """AR 设备实时数据叠加层"""
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT monitor_time, device_id, device_name, building_type, param_type,
                       elec_consumption, cop, supply_temp, return_temp, delta_temp,
                       run_status, fault_code, system_pressure_diff, current_unbalance,
                       condensing_water_temp, loading_rate
                FROM fact_energy_records
                WHERE device_id = ?
                ORDER BY monitor_time DESC
                LIMIT 10
                """,
                conn,
                params=[device_id],
            )
            # 同时读取设备位置信息
            cur = conn.cursor()
            cur.execute("""
                SELECT d.device_id, d.device_name, d.device_type, d.building_id, d.space_id,
                       b.building_name, s.space_name
                FROM dim_devices d
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                LEFT JOIN dim_spaces s ON s.space_id = d.space_id
                WHERE d.device_id = ?
            """, [device_id])
            device_info_row = cur.fetchone()
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "AR 设备详情查询")

    if df.empty:
        return {"status": "success", "data": None, "message": "设备不存在或无数据"}

    latest = df.iloc[0]
    # 设备位置信息
    device_info = dict(device_info_row) if device_info_row else {}
    building_name = device_info.get("building_name") or str(latest["building_type"])
    space_name = device_info.get("space_name") or "-"

    # AR 叠加层布局
    overlay = {
        "device_info": {
            "id": str(latest["device_id"]),
            "name": device_info.get("device_name") or str(latest["device_name"]),
            "type": device_info.get("device_type") or str(latest["param_type"]),
            "building": building_name,
            "space": space_name,
            "location": f"{building_name} / {space_name}",
        },
        "realtime_metrics": [
            {"label": "COP", "value": float(latest["cop"]) if pd.notna(latest["cop"]) else None, "unit": "", "status": "normal" if (pd.notna(latest["cop"]) and latest["cop"] > 3.5) else "warning"},
            {"label": "耗电功率", "value": float(latest["elec_consumption"]) if pd.notna(latest["elec_consumption"]) else None, "unit": "kW"},
            {"label": "供水温度", "value": float(latest["supply_temp"]) if pd.notna(latest["supply_temp"]) else None, "unit": "℃"},
            {"label": "回水温度", "value": float(latest["return_temp"]) if pd.notna(latest["return_temp"]) else None, "unit": "℃"},
            {"label": "温差", "value": float(latest["delta_temp"]) if pd.notna(latest["delta_temp"]) else None, "unit": "℃"},
            {"label": "负载率", "value": float(latest["loading_rate"]) if pd.notna(latest["loading_rate"]) else None, "unit": "%"},
        ],
        "status": {
            "run_status": str(latest["run_status"]),
            "fault_code": str(latest["fault_code"]) if pd.notna(latest["fault_code"]) and latest["fault_code"] != "NONE" else None,
            "is_alert": str(latest["run_status"]) != "NORMAL",
        },
        "last_update": str(latest["monitor_time"]),
        "trend_10_points": [
            {
                "time": str(row["monitor_time"]),
                "cop": float(row["cop"]) if pd.notna(row["cop"]) else None,
                "elec": float(row["elec_consumption"]) if pd.notna(row["elec_consumption"]) else None,
            }
            for _, row in df.iloc[::-1].iterrows()
        ],
    }
    return {"status": "success", "data": overlay}


@router.get("/api/ar/work_orders/{device_id}")
@run_in_thread
def ar_work_orders(device_id: str, limit: int = 5):
    """设备历史工单（AR 弹窗展示）"""
    try:
        with get_conn() as conn:
            # LEFT JOIN sys_workorder_ext 获取优先级和负责人（列在扩展表中）
            df = pd.read_sql(
                """
                SELECT w.order_id, w.device_id, w.diagnosis_title, w.status,
                       COALESCE(e.priority, 'P3') AS priority,
                       w.created_at,
                       COALESCE(e.assignee, '-') AS assigned_to,
                       w.maintenance_action
                FROM fact_work_orders w
                LEFT JOIN sys_workorder_ext e ON e.order_id = w.order_id
                WHERE w.device_id = ?
                ORDER BY w.created_at DESC
                LIMIT ?
                """,
                conn,
                params=[device_id, limit],
            )
    except Exception:
        # 工单表不存在时返回空
        df = pd.DataFrame()

    return {
        "status": "success",
        "data": df.to_dict(orient="records") if not df.empty else [],
        "total": len(df),
    }


@router.get("/api/ar/manual/{device_id}")
@run_in_thread
def ar_manual_snippet(device_id: str):
    """设备维修手册片段（AR 悬浮提示，按设备类型动态匹配）"""
    # 先从数据库查询设备类型
    device_type = None
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT device_type FROM dim_devices WHERE device_id = ?", [device_id])
            row = cur.fetchone()
            if row:
                device_type = dict(row)["device_type"]
    except Exception as e:
        logger.warning(f"查询设备类型失败: {e}")

    # 按设备类型匹配手册
    manual = _MANUAL_LIBRARY.get(device_type) if device_type else None
    if not manual:
        manual = {
            "title": "通用维保要点",
            "steps": ["1. 参照设备铭牌与厂家手册", "2. 定期巡检并记录"],
            "warning": "⚠️ 维护前必须断电",
        }

    return {"status": "success", "data": manual, "device_type": device_type}


class ARAnnotation(BaseModel):
    device_id: str
    operator: str = "anonymous"
    note: str
    photo_url: Optional[str] = None
    location: Optional[dict] = None  # {lat, lon} 或 AR 空间锚点


@router.post("/api/ar/annotate")
@run_in_thread
def save_annotation(req: ARAnnotation):
    """保存现场运维标注（持久化到数据库 sys_ar_annotations）"""
    _ensure_annotation_table()
    annotation_id = f"ANNOT_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    location_json = json.dumps(req.location, ensure_ascii=False) if req.location else None
    created_at = datetime.datetime.now().isoformat()

    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO sys_ar_annotations (id, device_id, operator, note, photo_url, location, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [annotation_id, req.device_id, req.operator, req.note, req.photo_url, location_json, created_at],
            )
            conn.commit()
    except Exception as e:
        return handle_route_error(e, logger, "保存 AR 标注")

    annotation = {
        "id": annotation_id,
        "device_id": req.device_id,
        "operator": req.operator,
        "note": req.note,
        "photo_url": req.photo_url,
        "location": req.location,
        "created_at": created_at,
    }
    return {"status": "success", "message": "标注已保存", "data": annotation}


@router.get("/api/ar/annotations")
@run_in_thread
def list_annotations(device_id: Optional[str] = None, limit: int = 20):
    """查询标注列表（从数据库读取，支持按设备过滤）"""
    _ensure_annotation_table()
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            if device_id:
                cur.execute(
                    """
                    SELECT id, device_id, operator, note, photo_url, location, created_at
                    FROM sys_ar_annotations
                    WHERE device_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    [device_id, limit],
                )
            else:
                cur.execute(
                    """
                    SELECT id, device_id, operator, note, photo_url, location, created_at
                    FROM sys_ar_annotations
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    [limit],
                )
            items = []
            for row in cur.fetchall():
                r = dict(row)
                # 解析 location JSON
                location = None
                if r.get("location"):
                    try:
                        location = json.loads(r["location"])
                    except (json.JSONDecodeError, TypeError):
                        location = None
                items.append({
                    "id": r["id"],
                    "device_id": r["device_id"],
                    "operator": r["operator"],
                    "note": r["note"],
                    "photo_url": r["photo_url"],
                    "location": location,
                    "created_at": r["created_at"],
                })
            return {"status": "success", "data": items, "total": len(items)}
    except Exception as e:
        return handle_route_error(e, logger, "AR 标注查询", extra_fields={"data": [], "total": 0})
