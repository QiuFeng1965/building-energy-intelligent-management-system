# -*- coding: utf-8 -*-
"""
WebSocket 路由
- /ws/realtime_energy：实时能耗推送
  - 每 3 秒推送一次最新能耗快照（从 fact_energy_records 取最新一条）
  - 检测到异常设备（run_status != 'NORMAL'）时立即推送告警事件
"""
import json
import asyncio
import logging

import pandas as pd
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()


def _fetch_latest_snapshot() -> dict:
    """从数据库取最新一条能耗记录 + 当前累计告警数"""
    try:
        with get_conn() as conn:
            # 最新一条记录
            df = pd.read_sql(
                "SELECT monitor_time, elec_consumption, cop, run_status, "
                "device_name, building_id "
                "FROM fact_energy_records "
                "ORDER BY monitor_time DESC LIMIT 1",
                conn
            )
            # 当前异常告警计数
            alarm_count = conn.execute(
                "SELECT COUNT(*) FROM fact_energy_records "
                "WHERE run_status != 'NORMAL' "
                "AND DATE(monitor_time) = DATE('now', 'localtime')"
            ).fetchone()[0]

        if df.empty:
            return {
                "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
                "total_power": 0.0,
                "cop_value": 0.0,
                "active_alarms": 0,
                "device_name": "无数据",
                "data_source": "empty"
            }

        row = df.iloc[0]
        return {
            "timestamp": str(row['monitor_time']),
            "total_power": round(float(row['elec_consumption'] or 0), 2),
            "cop_value": round(float(row['cop'] or 0), 2),
            "active_alarms": int(alarm_count),
            "device_name": str(row['device_name']),
            "building_id": str(row['building_id']),
            "run_status": str(row['run_status']),
            "data_source": "real_db"
        }
    except Exception as e:
        logger.exception(f"WebSocket 数据拉取失败: {e}")
        return {
            "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
            "total_power": 0.0,
            "cop_value": 0.0,
            "active_alarms": 0,
            "data_source": f"error: {e}"
        }


def _fetch_latest_alarm() -> dict | None:
    """检查最近 10 秒内是否有新的异常事件"""
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                "SELECT monitor_time, device_name, run_status, fault_code, "
                "building_id, elec_consumption "
                "FROM fact_energy_records "
                "WHERE run_status != 'NORMAL' "
                "AND monitor_time >= datetime('now', 'localtime', '-10 seconds') "
                "ORDER BY monitor_time DESC LIMIT 1",
                conn
            )
        if df.empty:
            return None
        row = df.iloc[0]
        return {
            "type": "alarm",
            "timestamp": str(row['monitor_time']),
            "device_name": str(row['device_name']),
            "building_id": str(row['building_id']),
            "run_status": str(row['run_status']),
            "fault_code": str(row['fault_code'] or ''),
            "elec_consumption": float(row['elec_consumption'] or 0)
        }
    except Exception as e:
        logger.exception(f"告警检查失败: {e}")
        return None


@router.websocket("/ws/realtime_energy")
async def websocket_energy_endpoint(websocket: WebSocket):
    """实时能耗推送：每 3 秒推送快照，检测到新告警立即推送告警事件"""
    # WebSocket 鉴权：从 query 参数读取 token 并校验
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="缺少 token 参数")
        return
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload or not payload.get("sub"):
            await websocket.close(code=4401, reason="token 无效或已过期")
            return
    except Exception:
        await websocket.close(code=4401, reason="token 校验失败")
        return

    await websocket.accept()
    logger.info(f"🟢 WebSocket 实时连接已建立（用户: {payload.get('sub', '-')}）")
    # 记录已推送过的告警时间戳，避免重复推送
    last_alarm_ts = None
    try:
        while True:
            # 1. 推送最新能耗快照
            snapshot = _fetch_latest_snapshot()
            await websocket.send_text(json.dumps({
                "type": "snapshot",
                **snapshot
            }, ensure_ascii=False))

            # 2. 检查是否有新告警
            alarm = _fetch_latest_alarm()
            if alarm and alarm["timestamp"] != last_alarm_ts:
                await websocket.send_text(json.dumps({
                    **alarm
                }, ensure_ascii=False))
                last_alarm_ts = alarm["timestamp"]
                logger.warning(f"🚨 推送实时告警: {alarm['device_name']} - {alarm['run_status']}")

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        logger.info("🔴 WebSocket 连接已断开")
    except Exception as e:
        logger.exception(f"⚠️ WebSocket 异常: {e}")
