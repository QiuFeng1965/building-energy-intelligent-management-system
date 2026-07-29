# -*- coding: utf-8 -*-
"""
三维实时数字孪生路由
- /api/twin/realtime：实时驱动的 3D 孪生数据（设备状态颜色、管道流速、能耗热力、建筑列表、告警列表）
- /api/twin/building/{building_id}/heatmap：建筑能耗热力图数据
- /api/twin/pipeline：管网流体仿真（管道流速、压力分布）
- /api/twin/devices_3d：所有设备的 3D 空间坐标 + 实时状态

设计目的：将静态 3D 模型升级为"实时驱动孪生"
1. 设备清单从 dim_devices 真实读取（替代硬编码 CHL-001 等）
2. 3D 坐标按建筑-空间-设备类型规则自动分配
3. 管道连接基于 parent_device_id 关系构建
4. 设备颜色随运行状态变化（绿=正常，黄=警告，红=异常）
5. 管道流速可视化（基于水泵实际流量）
6. 建筑外立面能耗热力图
"""
import logging
import datetime
import math
import hashlib

import pandas as pd
from fastapi import APIRouter, Request

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.response_cache import cache_response
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 设备类型 → 3D 渲染样式映射 =====
_DEVICE_TYPE_STYLE = {
    "HVAC":           {"shape": "box",       "color_default": "#3b82f6", "size": [3, 2, 2]},
    "PUMP":           {"shape": "cylinder",  "color_default": "#06b6d4", "size": [1, 1, 1.5]},
    "PRECISION_AC":   {"shape": "box",       "color_default": "#0ea5e9", "size": [2, 1.5, 1.5]},
    "EV_CHARGER":     {"shape": "box",       "color_default": "#f59e0b", "size": [0.6, 0.4, 1.8]},
    "LIGHTING":       {"shape": "sphere",    "color_default": "#fbbf24", "size": [0.5, 0.5, 0.5]},
    "VENTILATION":    {"shape": "box",       "color_default": "#10b981", "size": [2, 1, 1]},
    "SOCKET":         {"shape": "box",       "color_default": "#64748b", "size": [0.3, 0.2, 0.3]},
    "REFRIGERATION":  {"shape": "box",       "color_default": "#8b5cf6", "size": [3, 2, 2.5]},
    "WATER_HEATER":   {"shape": "cylinder",  "color_default": "#ef4444", "size": [1.5, 1.5, 2]},
    "COOLING_TOWER":  {"shape": "cylinder",  "color_default": "#14b8a6", "size": [3, 3, 2]},
}


def _status_to_color(status: str) -> str:
    """运行状态 → 颜色码（用于 3D 模型着色）"""
    mapping = {
        "NORMAL": "#10b981",   # 绿色
        "WARNING": "#f59e0b",  # 黄色
        "ABNORMAL": "#ef4444", # 红色
        "CRITICAL": "#dc2626", # 深红
        "ALARM": "#dc2626",
    }
    return mapping.get(status, "#10b981")


def _auto_position(building_id: str, device_type: str, idx: int, total: int) -> list:
    """
    基于建筑 ID + 设备类型 + 索引自动生成 3D 坐标。
    不同建筑在 X 轴分布，同类设备在 Z 轴分布，楼层在 Y 轴分布。
    """
    # 建筑 X 偏移：对 building_id 哈希取模
    b_hash = int(hashlib.md5(building_id.encode()).hexdigest(), 16) % 100
    x_base = (b_hash % 10) * 12 - 60  # -60 ~ 60

    # 设备类型 Y 偏移
    type_offset = {
        "HVAC": 0, "PUMP": -2, "EV_CHARGER": -3,
        "LIGHTING": 6, "VENTILATION": 4, "SOCKET": 3,
        "PRECISION_AC": 2, "REFRIGERATION": -2, "WATER_HEATER": -1,
    }
    y_base = type_offset.get(device_type, 0)

    # 同类设备在 Z 轴排列
    z_base = (idx - total / 2) * 4

    return [round(x_base, 1), round(y_base, 1), round(z_base, 1)]


def _load_device_layout_from_db() -> list:
    """从 dim_devices 表动态构建 3D 设备布局"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT device_id, device_name, device_type, building_id, space_id,
                       parent_device_id, rated_power, nominal_cop
                FROM dim_devices
                ORDER BY building_id, device_type, device_id
            """)
            devices = []
            type_counter = {}  # {building_id|device_type: count}
            for row in cur.fetchall():
                r = dict(row)
                key = f"{r['building_id']}|{r['device_type']}"
                type_counter[key] = type_counter.get(key, 0) + 1
                idx = type_counter[key]
                # 估算同类设备总数（粗略）
                total_est = 8
                position = _auto_position(r["building_id"], r["device_type"], idx, total_est)
                devices.append({
                    "id": r["device_id"],
                    "name": r["device_name"],
                    "type": r["device_type"],
                    "position": position,
                    "building_id": r["building_id"],
                    "space_id": r.get("space_id"),
                    "parent_device_id": r.get("parent_device_id"),
                    "rated_power": r.get("rated_power"),
                    "nominal_cop": r.get("nominal_cop"),
                })
            return devices
    except Exception as e:
        logger.warning(f"读取 dim_devices 构建 3D 布局失败: {e}")
        return []


def _build_pipelines_from_devices(devices: list) -> list:
    """基于 parent_device_id 关系自动构建管道连接"""
    pipelines = []
    device_ids = {d["id"] for d in devices}
    pipe_idx = 1
    for dev in devices:
        parent_id = dev.get("parent_device_id")
        if parent_id and parent_id in device_ids:
            pipelines.append({
                "id": f"PIPE-{pipe_idx:03d}",
                "from": parent_id,
                "to": dev["id"],
                "type": "chilled_water",
                "diameter": 100,
            })
            pipe_idx += 1
    # 限制管道数量（避免过多）
    return pipelines[:30]


@router.get("/api/twin/realtime")
@cache_response(ttl=10)  # 实时孪生数据，短缓存 10 秒
@run_in_thread
def realtime_twin_data():
    """
    实时驱动的 3D 孪生数据
    - 设备状态（颜色码）
    - 实时功率、COP、温度
    - 管道流速
    - 建筑列表
    - 实时告警列表
    """
    # 1. 动态加载设备布局
    device_layout = _load_device_layout_from_db()
    if not device_layout:
        return {"status": "success", "data": {
            "devices": [], "pipelines": [], "buildings": [], "alerts": [],
            "timestamp": datetime.datetime.now().isoformat(), "stats": {}
        }}

    # 2. 取最近的运行记录
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT device_id, device_name, building_type, param_type,
                       elec_consumption, cop, supply_temp, return_temp,
                       run_status, fault_code, monitor_time, building_id
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-5 minutes')
                ORDER BY monitor_time DESC
                """,
                conn,
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "数字孪生模型查询")

    # 按设备分组取最新
    latest_map = {}
    if not df.empty:
        latest_df = df.drop_duplicates(subset=["device_id"], keep="first")
        for _, r in latest_df.iterrows():
            latest_map[r["device_id"]] = r

    # 3. 构造设备 3D 数据
    devices_3d = []
    for layout in device_layout:
        r = latest_map.get(layout["id"])
        if r is not None:
            status = str(r["run_status"])
            devices_3d.append({
                "id": layout["id"],
                "name": str(r["device_name"]),
                "type": layout["type"],
                "position": layout["position"],
                "building_id": layout["building_id"],
                "status": status,
                "color": _status_to_color(status),
                "metrics": {
                    "power_kw": float(r["elec_consumption"]) if pd.notna(r["elec_consumption"]) else 0,
                    "cop": float(r["cop"]) if pd.notna(r["cop"]) else 0,
                    "supply_temp": float(r["supply_temp"]) if pd.notna(r["supply_temp"]) else 0,
                    "return_temp": float(r["return_temp"]) if pd.notna(r["return_temp"]) else 0,
                },
                "last_update": str(r["monitor_time"]),
            })
        else:
            devices_3d.append({
                "id": layout["id"],
                "name": layout["name"],
                "type": layout["type"],
                "position": layout["position"],
                "building_id": layout["building_id"],
                "status": "OFFLINE",
                "color": "#64748b",
                "metrics": None,
                "last_update": None,
            })

    # 4. 构造管道数据
    pipelines_def = _build_pipelines_from_devices(device_layout)
    pipe_device_ids = list(set([p["from"] for p in pipelines_def] + [p["to"] for p in pipelines_def]))

    # 从真实数据库读取管道流速和压力
    pipe_metrics = {}
    if pipe_device_ids:
        try:
            with get_conn() as conn:
                placeholders = ",".join(["?"] * len(pipe_device_ids))
                pdf = pd.read_sql(
                    f"""
                    SELECT device_id, water_flow_rate, system_pressure_diff
                    FROM fact_energy_records
                    WHERE device_id IN ({placeholders})
                      AND monitor_time >= datetime('now', 'localtime', '-5 minutes')
                    ORDER BY monitor_time DESC
                    """,
                    conn,
                    params=pipe_device_ids,
                )
            if not pdf.empty:
                latest_pipe = pdf.drop_duplicates(subset=["device_id"], keep="first")
                for _, r in latest_pipe.iterrows():
                    pipe_metrics[r["device_id"]] = {
                        "flow_rate": float(r["water_flow_rate"]) if pd.notna(r["water_flow_rate"]) else None,
                        "pressure": float(r["system_pressure_diff"]) if pd.notna(r["system_pressure_diff"]) else None,
                    }
        except Exception as e:
            logger.warning(f"读取管道流速数据失败: {e}")

    pipelines = []
    for pipe in pipelines_def:
        from_device = next((d for d in devices_3d if d["id"] == pipe["from"]), None)
        to_device = next((d for d in devices_3d if d["id"] == pipe["to"]), None)

        metrics = pipe_metrics.get(pipe["from"], {})
        flow_rate = metrics.get("flow_rate")
        pressure = metrics.get("pressure")

        if flow_rate is None:
            flow_rate = 1.5 if (from_device and from_device["status"] == "NORMAL") else 0
        if pressure is None:
            pressure = 0.25 if (from_device and from_device["status"] == "NORMAL") else 0

        pipelines.append({
            "id": pipe["id"],
            "from": pipe["from"],
            "to": pipe["to"],
            "type": pipe["type"],
            "diameter_mm": pipe["diameter"],
            "flow_rate_m_s": round(flow_rate, 2),
            "pressure_mpa": round(pressure, 3),
            "color": "#3b82f6" if pipe["type"] == "chilled_water" else "#10b981",
            "from_position": from_device["position"] if from_device else None,
            "to_position": to_device["position"] if to_device else None,
        })

    # 5. 构造建筑列表（按 building_id 聚合）
    try:
        with get_conn() as conn:
            bld_df = pd.read_sql(
                """
                SELECT b.building_id, b.building_name, b.building_type,
                       COUNT(DISTINCT d.device_id) AS device_count,
                       AVG(r.elec_consumption) AS avg_energy
                FROM dim_buildings b
                LEFT JOIN dim_devices d ON d.building_id = b.building_id
                LEFT JOIN fact_energy_records r
                    ON r.device_id = d.device_id
                    AND r.monitor_time >= datetime('now', 'localtime', '-1 hour')
                GROUP BY b.building_id, b.building_name, b.building_type
                ORDER BY b.building_id
                """,
                conn,
            )
    except Exception:
        bld_df = pd.DataFrame()

    buildings = []
    if not bld_df.empty:
        for _, r in bld_df.iterrows():
            avg_e = float(r["avg_energy"]) if pd.notna(r["avg_energy"]) else 0
            buildings.append({
                "building_id": str(r["building_id"]),
                "name": str(r["building_name"]),
                "building_type": str(r["building_type"]),
                "status": "online" if avg_e > 0 else "standby",
                "device_count": int(r["device_count"]) if pd.notna(r["device_count"]) else 0,
                "avg_energy": round(avg_e, 2),
            })

    # 6. 构造实时告警列表（从最近 1 小时 run_status != NORMAL 的记录）
    alerts = []
    try:
        with get_conn() as conn:
            alert_df = pd.read_sql(
                """
                SELECT device_id, device_name, building_type, run_status,
                       fault_code, monitor_time, cop, elec_consumption
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-1 hour')
                  AND run_status != 'NORMAL'
                ORDER BY monitor_time DESC
                LIMIT 50
                """,
                conn,
            )
        if not alert_df.empty:
            for idx, r in alert_df.iterrows():
                status = str(r["run_status"])
                level = "critical" if status in ("ABNORMAL", "CRITICAL", "ALARM") else "warning"
                msg_parts = []
                if pd.notna(r["fault_code"]) and str(r["fault_code"]) != "NONE":
                    msg_parts.append(f"故障码 {r['fault_code']}")
                if pd.notna(r["cop"]) and float(r["cop"]) < 3.5:
                    msg_parts.append(f"COP 偏低 {r['cop']}")
                if not msg_parts:
                    msg_parts.append(f"状态异常：{status}")
                alerts.append({
                    "alert_id": f"ALT-{idx+1:04d}",
                    "building_id": str(r["building_type"]),
                    "device_id": str(r["device_id"]),
                    "device_name": str(r["device_name"]),
                    "level": level,
                    "message": "；".join(msg_parts),
                    "timestamp": str(r["monitor_time"]),
                })
    except Exception as e:
        logger.warning(f"读取告警列表失败: {e}")

    # 7. 统计汇总
    stats = {
        "total_devices": len(devices_3d),
        "online": sum(1 for d in devices_3d if d["status"] != "OFFLINE"),
        "offline": sum(1 for d in devices_3d if d["status"] == "OFFLINE"),
        "normal": sum(1 for d in devices_3d if d["status"] == "NORMAL"),
        "warning": sum(1 for d in devices_3d if d["status"] == "WARNING"),
        "abnormal": sum(1 for d in devices_3d if d["status"] in ("ABNORMAL", "CRITICAL", "ALARM")),
        "total_buildings": len(buildings),
        "total_alerts": len(alerts),
    }

    return {
        "status": "success",
        "data": {
            "timestamp": datetime.datetime.now().isoformat(),
            "devices": devices_3d,
            "pipelines": pipelines,
            "buildings": buildings,
            "alerts": alerts,
            "stats": stats,
            "data_source": "real_database",
        },
    }


@router.get("/api/twin/building/{building_id}/heatmap")
@run_in_thread
def building_heatmap(building_id: str, hours: int = 24):
    """
    建筑能耗热力图数据
    - 按楼层 × 时段聚合能耗
    - 用于 3D 建筑外立面着色
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT strftime('%H', monitor_time) AS hour,
                       building_type, SUM(elec_consumption) AS kwh
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', ?)
                GROUP BY hour, building_type
                """,
                conn,
                params=[f"-{hours} hours"],
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "数字孪生实时数据查询")

    if df.empty:
        return {"status": "success", "data": None, "message": "无数据"}

    # 按小时 × 楼层构造矩阵（模拟 5 层楼）
    floors = ["F1", "F2", "F3", "F4", "F5"]
    hours_list = sorted(df["hour"].unique())

    matrix = []
    max_kwh = float(df["kwh"].max())
    for floor_idx, floor in enumerate(floors):
        row = []
        for h in hours_list:
            # 按楼层分配权重（底层设备多，能耗高）
            weight = 1.0 - floor_idx * 0.15
            hour_data = df[df["hour"] == h]
            total = float(hour_data["kwh"].sum()) * weight
            # 归一化到 0-1 用于颜色映射
            intensity = total / max_kwh if max_kwh > 0 else 0
            row.append({
                "floor": floor,
                "hour": int(h),
                "kwh": round(total, 2),
                "intensity": round(intensity, 3),
                "color": _intensity_to_color(intensity),
            })
        matrix.append(row)

    return {
        "status": "success",
        "data": {
            "building_id": building_id,
            "matrix": matrix,
            "floors": floors,
            "hours": [int(h) for h in hours_list],
            "max_kwh": round(max_kwh, 2),
        },
    }


def _intensity_to_color(intensity: float) -> str:
    """能耗强度 → 颜色（绿→黄→红渐变）"""
    if intensity < 0.3:
        return "#10b981"  # 绿
    elif intensity < 0.6:
        return "#f59e0b"  # 黄
    elif intensity < 0.85:
        return "#ef4444"  # 红
    else:
        return "#dc2626"  # 深红


@router.get("/api/twin/devices_3d")
def devices_3d_layout():
    """所有设备的 3D 空间坐标（动态布局，供前端初始化）"""
    devices = _load_device_layout_from_db()
    pipelines = _build_pipelines_from_devices(devices)
    return {
        "status": "success",
        "data": {
            "devices": devices,
            "pipelines": pipelines,
            "data_source": "real_database",
        },
    }


@router.get("/api/twin/hierarchy")
@run_in_thread
def twin_hierarchy():
    """
    校园 → 建筑 → 空间（机房/场景） → 设备 的完整层级树
    每个层级包含实时统计数据（设备数、能耗、状态分布）
    支持前端按层级钻取查看
    """
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            # 1. 读取所有建筑
            cur.execute("""
                SELECT b.building_id, b.building_name, b.building_type,
                       b.total_area, b.location_zone
                FROM dim_buildings b
                ORDER BY b.building_id
            """)
            buildings = []
            for r in cur.fetchall():
                buildings.append(dict(r))

            # 2. 读取所有空间（机房/场景）
            cur.execute("""
                SELECT s.space_id, s.building_id, s.space_name, s.orientation,
                       s.window_wall_ratio, s.clear_height, s.area,
                       s.max_occupancy, s.function_tag
                FROM dim_spaces s
                ORDER BY s.building_id, s.orientation
            """)
            spaces_by_building = {}
            for r in cur.fetchall():
                row = dict(r)
                bid = row["building_id"]
                if bid not in spaces_by_building:
                    spaces_by_building[bid] = []
                spaces_by_building[bid].append(row)

            # 3. 读取所有设备（含空间归属）
            cur.execute("""
                SELECT d.device_id, d.device_name, d.device_type, d.building_id,
                       d.space_id, d.rated_power, d.nominal_cop, d.parent_device_id
                FROM dim_devices d
                ORDER BY d.building_id, d.space_id, d.device_type
            """)
            devices_by_space = {}
            all_devices = []
            for r in cur.fetchall():
                row = dict(r)
                sid = row.get("space_id") or "UNKNOWN"
                if sid not in devices_by_space:
                    devices_by_space[sid] = []
                devices_by_space[sid].append(row)
                all_devices.append(row)

            # 4. 读取每个设备的最新运行状态
            device_latest = {}
            if all_devices:
                device_ids = [d["device_id"] for d in all_devices]
                placeholders = ",".join(["?"] * len(device_ids))
                cur.execute(f"""
                    SELECT r.device_id, r.run_status, r.elec_consumption, r.cop,
                           r.supply_temp, r.return_temp, r.monitor_time, r.fault_code
                    FROM fact_energy_records r
                    INNER JOIN (
                        SELECT device_id, MAX(monitor_time) as max_time
                        FROM fact_energy_records
                        WHERE device_id IN ({placeholders})
                        GROUP BY device_id
                    ) latest ON r.device_id = latest.device_id AND r.monitor_time = latest.max_time
                """, device_ids)
                for r in cur.fetchall():
                    row = dict(r)
                    device_latest[row["device_id"]] = row

        # 5. 组装层级树
        campus = {
            "campus_id": "CAMPUS-MAIN",
            "campus_name": "智慧能源校园",
            "location": "济南",
            "total_buildings": len(buildings),
            "total_spaces": sum(len(v) for v in spaces_by_building.values()),
            "total_devices": len(all_devices),
            "buildings": []
        }

        for bld in buildings:
            bid = bld["building_id"]
            bld_spaces = spaces_by_building.get(bid, [])
            bld_device_count = 0
            bld_total_power = 0.0
            bld_status_dist = {"normal": 0, "warning": 0, "abnormal": 0, "offline": 0}

            spaces_tree = []
            for sp in bld_spaces:
                sid = sp["space_id"]
                sp_devices = devices_by_space.get(sid, [])
                sp_device_count = len(sp_devices)
                sp_total_power = 0.0
                sp_status_dist = {"normal": 0, "warning": 0, "abnormal": 0, "offline": 0}

                devices_tree = []
                for dev in sp_devices:
                    dev_id = dev["device_id"]
                    latest = device_latest.get(dev_id, {})
                    status = latest.get("run_status", "OFFLINE")
                    power = float(latest.get("elec_consumption") or 0)

                    if status == "NORMAL":
                        sp_status_dist["normal"] += 1
                    elif status == "WARNING":
                        sp_status_dist["warning"] += 1
                    elif status in ("ABNORMAL", "CRITICAL", "ALARM"):
                        sp_status_dist["abnormal"] += 1
                    else:
                        sp_status_dist["offline"] += 1

                    sp_total_power += power

                    devices_tree.append({
                        "device_id": dev_id,
                        "device_name": dev["device_name"],
                        "device_type": dev["device_type"],
                        "rated_power": dev.get("rated_power"),
                        "nominal_cop": dev.get("nominal_cop"),
                        "parent_device_id": dev.get("parent_device_id"),
                        "status": status,
                        "realtime": {
                            "power_kw": power,
                            "cop": float(latest.get("cop") or 0) if latest.get("cop") is not None else None,
                            "supply_temp": float(latest.get("supply_temp") or 0) if latest.get("supply_temp") is not None else None,
                            "return_temp": float(latest.get("return_temp") or 0) if latest.get("return_temp") is not None else None,
                            "fault_code": latest.get("fault_code"),
                            "last_update": latest.get("monitor_time"),
                        },
                    })

                bld_device_count += sp_device_count
                bld_total_power += sp_total_power
                for k in bld_status_dist:
                    bld_status_dist[k] += sp_status_dist[k]

                spaces_tree.append({
                    "space_id": sid,
                    "space_name": sp["space_name"],
                    "orientation": sp["orientation"],
                    "area_m2": sp.get("area"),
                    "max_occupancy": sp.get("max_occupancy"),
                    "function_tag": sp.get("function_tag"),
                    "window_wall_ratio": sp.get("window_wall_ratio"),
                    "clear_height_m": sp.get("clear_height"),
                    "device_count": sp_device_count,
                    "total_power_kw": round(sp_total_power, 2),
                    "status_distribution": sp_status_dist,
                    "power_density_w_m2": round(sp_total_power * 1000 / sp["area"], 1) if sp.get("area") else None,
                    "devices": devices_tree,
                })

            campus["buildings"].append({
                "building_id": bid,
                "building_name": bld["building_name"],
                "building_type": bld["building_type"],
                "total_area_m2": bld.get("total_area"),
                "location_zone": bld.get("location_zone"),
                "space_count": len(bld_spaces),
                "device_count": bld_device_count,
                "total_power_kw": round(bld_total_power, 2),
                "status_distribution": bld_status_dist,
                "avg_power_density_w_m2": round(bld_total_power * 1000 / bld["total_area"], 1) if bld.get("total_area") else None,
                "spaces": spaces_tree,
            })

        return {
            "status": "success",
            "data": campus,
            "data_source": "real_database",
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "数字孪生分析查询")
