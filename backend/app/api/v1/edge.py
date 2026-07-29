# -*- coding: utf-8 -*-
"""
边缘计算网关路由
- /api/edge/gateway/status：网关状态
- /api/edge/gateway/inject_anomaly：注入异常事件（演练用）
- /api/edge/devices：边缘设备列表（从 dim_devices 真实读取）
- /api/edge/snapshot：实时数据快照（从 fact_energy_records 最新记录读取）

设计说明：
1. 设备清单从 dim_devices 真实数据库读取，按设备类型映射协议
2. 实时快照从 fact_energy_records 取每个设备的最新一条记录
3. 异常注入仍为内存模拟（这是合理的演练功能）
4. 全局状态使用 threading.Lock 保护，避免多线程并发读写造成数据竞态
"""
import logging
import asyncio
import datetime
import threading
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_conn
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 设备类型 → 协议映射（基于工业惯例）=====
_DEVICE_TYPE_PROTOCOL = {
    "CHILLER": "Modbus RTU",
    "PUMP": "OPC-UA",
    "COOLING_TOWER": "MQTT",
    "AHU": "BACnet",
    "METER": "Modbus RTU",
    "LIGHTING": "DALI",
    "ELEVATOR": "OPC-UA",
}

# 默认采样频率（Hz）
_DEFAULT_SAMPLING_HZ = 1


def _load_devices_from_db() -> list:
    """从 dim_devices 表读取真实设备清单（含空间名称）"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT d.device_id, d.device_name, d.device_type, d.building_id, d.space_id,
                       d.rated_power, d.nominal_cop,
                       b.building_name, s.space_name
                FROM dim_devices d
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                LEFT JOIN dim_spaces s ON s.space_id = d.space_id
                ORDER BY d.building_id, d.space_id, d.device_type, d.device_id
            """)
            devices = []
            for row in cur.fetchall():
                d = dict(row)
                protocol = _DEVICE_TYPE_PROTOCOL.get(d["device_type"], "Modbus RTU")
                devices.append({
                    "id": d["device_id"],
                    "name": d["device_name"],
                    "type": d["device_type"],
                    "protocol": protocol,
                    "address": f"0x{hash(d['device_id']) % 256:02X}",
                    "register": 40001,
                    "sampling_hz": _DEFAULT_SAMPLING_HZ,
                    "building_id": d["building_id"],
                    "building_name": d.get("building_name") or d["building_id"],
                    "space_id": d["space_id"],
                    "space_name": d.get("space_name") or d.get("space_id") or "-",
                    "rated_power": d["rated_power"],
                    "nominal_cop": d["nominal_cop"],
                })
            return devices
    except Exception as e:
        logger.warning(f"读取 dim_devices 失败，使用兜底设备清单: {e}")
        return []


def _load_latest_records(device_ids: list) -> dict:
    """从 fact_energy_records 取每个设备的最新一条记录"""
    if not device_ids:
        return {}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            # 取每个设备的最新记录
            placeholders = ",".join(["?"] * len(device_ids))
            cur.execute(f"""
                SELECT r.*
                FROM fact_energy_records r
                INNER JOIN (
                    SELECT device_id, MAX(monitor_time) as max_time
                    FROM fact_energy_records
                    WHERE device_id IN ({placeholders})
                    GROUP BY device_id
                ) latest ON r.device_id = latest.device_id AND r.monitor_time = latest.max_time
            """, device_ids)
            return {row["device_id"]: dict(row) for row in cur.fetchall()}
    except Exception as e:
        logger.warning(f"读取 fact_energy_records 最新记录失败: {e}")
        return {}


# ===== 网关运行状态（内存，使用 Lock 保护并发读写）=====
# 同步路由 def 运行在 FastAPI 线程池中，必须使用 threading.Lock 而非 asyncio.Lock
_state_lock = threading.Lock()
_gateway_state = {
    "is_running": True,  # 默认运行中
    "started_at": datetime.datetime.now().isoformat(),
    "messages_sent": 0,
    "last_message_time": None,
    "active_devices": 0,  # 在首次请求时填充
    "anomaly_injection": None,
}

# 异常注入幂等键：device_id+type → 注入时间戳（秒）
# 60 秒内同一 device_id + type 拒绝重复创建，防止演练误操作
_injection_keys: dict[str, float] = {}
_INJECTION_TTL = 60  # 秒


def _get_state_snapshot() -> dict:
    """获取网关状态的线程安全快照（深拷贝 anomaly_injection 避免外部修改）"""
    with _state_lock:
        return {
            "is_running": _gateway_state["is_running"],
            "started_at": _gateway_state["started_at"],
            "messages_sent": _gateway_state["messages_sent"],
            "last_message_time": _gateway_state["last_message_time"],
            "active_devices": _gateway_state["active_devices"],
            "anomaly_injection": (
                dict(_gateway_state["anomaly_injection"])
                if _gateway_state["anomaly_injection"]
                else None
            ),
        }


def _get_anomaly_injection() -> Optional[dict]:
    """线程安全地读取 anomaly_injection（返回拷贝避免外部修改）"""
    with _state_lock:
        inj = _gateway_state["anomaly_injection"]
        return dict(inj) if inj else None


@router.get("/api/edge/gateway/status")
def gateway_status():
    """网关运行状态"""
    # 实时统计活跃设备数
    devices = _load_devices_from_db()

    # 加锁更新计数器和时间戳，避免并发递增丢失
    with _state_lock:
        _gateway_state["active_devices"] = len(devices)
        _gateway_state["messages_sent"] += 1
        _gateway_state["last_message_time"] = datetime.datetime.now().isoformat()
        state = {
            "is_running": _gateway_state["is_running"],
            "started_at": _gateway_state["started_at"],
            "messages_sent": _gateway_state["messages_sent"],
            "last_message_time": _gateway_state["last_message_time"],
            "active_devices": _gateway_state["active_devices"],
            "anomaly_injection": (
                dict(_gateway_state["anomaly_injection"])
                if _gateway_state["anomaly_injection"]
                else None
            ),
        }

    return {
        "status": "success",
        "data": {
            **state,
            "uptime_seconds": (
                (datetime.datetime.now() - datetime.datetime.fromisoformat(state["started_at"])).total_seconds()
                if state["started_at"] else 0
            ),
        },
    }


@router.get("/api/edge/devices")
def list_edge_devices():
    """边缘设备列表（从真实数据库读取）"""
    devices = _load_devices_from_db()
    return {
        "status": "success",
        "data": devices,
        "total": len(devices),
    }


@router.get("/api/edge/snapshot")
def edge_snapshot():
    """获取当前一帧所有设备的实时数据快照（从真实数据库最新记录读取）"""
    devices = _load_devices_from_db()
    device_ids = [d["id"] for d in devices]
    latest_records = _load_latest_records(device_ids)

    # 线程安全地读取异常注入配置的快照
    anomaly_injection = _get_anomaly_injection()

    now = datetime.datetime.now()
    snapshot = []
    for dev in devices:
        rec = latest_records.get(dev["id"], {})
        item = {
            "device_id": dev["id"],
            "device_name": dev["name"],
            "device_type": dev["type"],
            "protocol": dev["protocol"],
            "timestamp": rec.get("monitor_time", now.isoformat()),
            "elec_consumption": rec.get("elec_consumption", 0),
            "cop": rec.get("cop", 0),
            "supply_temp": rec.get("supply_temp", 0),
            "return_temp": rec.get("return_temp", 0),
            "delta_temp": rec.get("delta_temp", 0),
            "loading_rate": rec.get("loading_rate", 0),
            "water_flow_rate": rec.get("water_flow_rate", 0),
            "system_pressure_diff": rec.get("system_pressure_diff", 0),
            "run_status": rec.get("run_status", "UNKNOWN"),
            "fault_code": rec.get("fault_code"),
            "building_id": dev["building_id"],
            "building_name": dev.get("building_name", "-"),
            "space_id": dev.get("space_id"),
            "space_name": dev.get("space_name", "-"),
        }

        # 异常注入覆盖（演练功能，使用快照避免竞态）
        if anomaly_injection:
            target = anomaly_injection.get("device_id")
            if not target or target == dev["id"]:
                if "cop_drop" in anomaly_injection.get("type", ""):
                    item["cop"] = 2.5
                    item["run_status"] = "WARNING"
                elif "overheat" in anomaly_injection.get("type", ""):
                    item["supply_temp"] = 11.5
                    item["return_temp"] = 16.2
                    item["run_status"] = "ABNORMAL"

        snapshot.append(item)

    return {
        "status": "success",
        "data": {
            "timestamp": now.isoformat(),
            "device_count": len(snapshot),
            "snapshot": snapshot,
        },
    }


class AnomalyInjection(BaseModel):
    type: str  # cop_drop | overheat | clear
    device_id: Optional[str] = None
    duration_seconds: int = 60


@router.post("/api/edge/gateway/inject_anomaly")
async def inject_anomaly(req: AnomalyInjection):
    """注入异常事件（用于演练）

    改为 async def 以使用 asyncio.create_task；状态写入仍通过 threading.Lock 保护，
    因为同步路由（gateway_status / edge_snapshot）在线程池中也会访问同一份状态。

    幂等保护：同一 device_id + type 在 60 秒内拒绝重复创建（返回 409）。
    """
    if req.type == "clear":
        with _state_lock:
            _gateway_state["anomaly_injection"] = None
        return {"status": "success", "message": "已清除异常注入"}

    # 幂等检查：同一 device_id + type 在 60 秒内拒绝重复创建
    injection_key = f"{req.device_id or 'all'}:{req.type}"
    now_ts = time.time()
    with _state_lock:
        # 惰性清理过期 key
        expired = [k for k, ts in _injection_keys.items() if (now_ts - ts) >= _INJECTION_TTL]
        for k in expired:
            _injection_keys.pop(k, None)

        last_ts = _injection_keys.get(injection_key)
        if last_ts and (now_ts - last_ts) < _INJECTION_TTL:
            remaining = int(_INJECTION_TTL - (now_ts - last_ts))
            raise HTTPException(
                status_code=409,
                detail=(
                    f"同一设备 {req.device_id or '全部'} 的异常类型 {req.type} "
                    f"在 {_INJECTION_TTL} 秒内已注入，请 {remaining} 秒后重试"
                ),
            )
        # 记录本次注入时间戳
        _injection_keys[injection_key] = now_ts

    new_injection = {
        "type": req.type,
        "device_id": req.device_id,
        "started_at": datetime.datetime.now().isoformat(),
        "duration_seconds": req.duration_seconds,
    }

    with _state_lock:
        _gateway_state["anomaly_injection"] = new_injection

    async def _clear_after():
        await asyncio.sleep(req.duration_seconds)
        with _state_lock:
            # 仅当仍是当前注入时才清除，避免被后续新注入误清
            if _gateway_state["anomaly_injection"] == new_injection:
                _gateway_state["anomaly_injection"] = None
                logger.info(f"异常注入 {req.type} 已自动清除")

    asyncio.create_task(_clear_after())

    return {
        "status": "success",
        "message": f"已注入异常 {req.type}，{req.duration_seconds} 秒后自动清除",
        "data": dict(new_injection),
    }
