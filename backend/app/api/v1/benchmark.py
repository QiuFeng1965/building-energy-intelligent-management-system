# -*- coding: utf-8 -*-
"""
能耗基准对标系统路由
- /api/benchmark/overview：全部建筑对标概览
- /api/benchmark/building/{building_id}：单建筑详细对标报告
- /api/benchmark/standards：国标基准参考值

设计要点：
1. 基于 GB 50189《公共建筑节能设计标准》及行业标准建立基准线
2. 用 MAX(DATE(monitor_time)) 作为"营业日"，往前推 30 天估算年化能耗
3. 评级：A 先进 / B 合理 / C 落后 / D 超标
4. 节能潜力 = (实际强度 - 先进值) × 面积
5. building_type 从 dim_buildings 读取，total_area 从 dim_buildings 读取
"""
import math
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 国标能耗基准库 =====
# 单位：kWh/㎡·年
# 依据：GB 50189《公共建筑节能设计标准》及行业能耗限额
# 字段：limit(限额) / advanced(先进值) / reasonable(合理值)
BENCHMARK_STANDARDS = {
    "OFFICE":     {"limit": 70, "advanced": 50, "reasonable": 65, "name": "办公楼",   "standard": "GB 50189"},
    "TEACHING":   {"limit": 45, "advanced": 30, "reasonable": 40, "name": "教学楼",   "standard": "JGJ/T 288"},
    "LIBRARY":    {"limit": 55, "advanced": 35, "reasonable": 50, "name": "图书馆",   "standard": "JGJ/T 288"},
    "CANTEEN":    {"limit": 80, "advanced": 55, "reasonable": 70, "name": "食堂",     "standard": "行业限额"},
    "DORMITORY":  {"limit": 40, "advanced": 25, "reasonable": 35, "name": "公寓",     "standard": "GB 50189"},
    "LABORATORY": {"limit": 90, "advanced": 60, "reasonable": 80, "name": "科研实验", "standard": "GB 50189"},
    "PLAZA":      {"limit": 20, "advanced": 15, "reasonable": 18, "name": "广场",     "standard": "地方标准"},
    # 会议/交流楼按办公类对标
    "CONFERENCE": {"limit": 70, "advanced": 50, "reasonable": 65, "name": "会议中心", "standard": "GB 50189"},
}

# 兜底基准（未知建筑类型）
DEFAULT_STANDARD = {"limit": 50, "advanced": 35, "reasonable": 45, "name": "其他", "standard": "默认参考"}

# 评级映射
GRADE_DESC = {
    "A": {"name": "先进", "color": "#52c41a", "desc": "实际能耗低于先进值"},
    "B": {"name": "合理", "color": "#1890ff", "desc": "实际能耗在先进值与合理值之间"},
    "C": {"name": "落后", "color": "#faad14", "desc": "实际能耗在合理值与限额之间"},
    "D": {"name": "超标", "color": "#ff4d4f", "desc": "实际能耗超过限额"},
}


def _safe_float(v, ndigits=2):
    """安全转换为 float，处理 NaN/Infinity/None"""
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, ndigits)
    except (TypeError, ValueError):
        return None


def _get_standard(building_type: Optional[str]) -> dict:
    """根据建筑类型获取基准标准"""
    if not building_type:
        return DEFAULT_STANDARD.copy()
    return BENCHMARK_STANDARDS.get(building_type, DEFAULT_STANDARD).copy()


def _calc_grade(intensity: float, std: dict) -> str:
    """根据能耗强度与基准评级"""
    if intensity < std["advanced"]:
        return "A"
    if intensity < std["reasonable"]:
        return "B"
    if intensity < std["limit"]:
        return "C"
    return "D"


def _fetch_building_list() -> pd.DataFrame:
    """获取所有建筑清单"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT building_id, building_name, building_type, total_area, location_zone
            FROM dim_buildings
            ORDER BY building_id
            """,
            conn,
        )
    return df


def _fetch_building_energy(building_id: Optional[str] = None) -> pd.DataFrame:
    """
    取近 30 天能耗聚合（按建筑）
    - 使用 MAX(DATE(monitor_time)) 作为"营业日"
    - 往前推 30 天，年化系数 = 365 / 30 = 12.17
    """
    with get_conn() as conn:
        if building_id:
            sql = """
                SELECT
                    building_id,
                    MAX(DATE(monitor_time)) AS last_day,
                    SUM(elec_consumption) AS kwh_30d,
                    COUNT(*) AS record_cnt,
                    COUNT(DISTINCT DATE(monitor_time)) AS day_cnt,
                    AVG(elec_consumption) AS avg_hourly_kwh
                FROM fact_energy_records
                WHERE building_id = ?
                  AND monitor_time >= (SELECT datetime(MAX(DATE(monitor_time)), '-30 days')
                                       FROM fact_energy_records WHERE building_id = ?)
                GROUP BY building_id
            """
            df = pd.read_sql(sql, conn, params=[building_id, building_id])
        else:
            sql = """
                SELECT
                    building_id,
                    MAX(DATE(monitor_time)) AS last_day,
                    SUM(elec_consumption) AS kwh_30d,
                    COUNT(*) AS record_cnt,
                    COUNT(DISTINCT DATE(monitor_time)) AS day_cnt,
                    AVG(elec_consumption) AS avg_hourly_kwh
                FROM fact_energy_records
                WHERE monitor_time >= (SELECT datetime(MAX(DATE(monitor_time)), '-30 days')
                                       FROM fact_energy_records)
                GROUP BY building_id
            """
            df = pd.read_sql(sql, conn)
    return df


def _fetch_building_daily_energy(building_id: str, days: int = 30) -> pd.DataFrame:
    """取单建筑近 N 天每日能耗"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT DATE(monitor_time) AS day,
                   SUM(elec_consumption) AS kwh,
                   AVG(elec_consumption) AS avg_hourly,
                   MAX(elec_consumption) AS peak_hourly
            FROM fact_energy_records
            WHERE building_id = ?
              AND monitor_time >= datetime('now', 'localtime', ?)
            GROUP BY day
            ORDER BY day
            """,
            conn,
            params=[building_id, f"-{days} days"],
        )
    return df


def _fetch_building_type_breakdown(building_id: str, days: int = 30) -> pd.DataFrame:
    """取单建筑按设备类型的能耗占比"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT r.param_type AS device_type,
                   SUM(r.elec_consumption) AS kwh,
                   COUNT(DISTINCT r.device_id) AS device_cnt
            FROM fact_energy_records r
            WHERE r.building_id = ?
              AND r.monitor_time >= datetime('now', 'localtime', ?)
            GROUP BY r.param_type
            ORDER BY kwh DESC
            """,
            conn,
            params=[building_id, f"-{days} days"],
        )
    return df


def _build_benchmark_record(building_row: dict, energy_row: Optional[dict]) -> dict:
    """组装单建筑的对标记录"""
    std = _get_standard(building_row.get("building_type"))
    area = _safe_float(building_row.get("total_area"), 2) or 0

    if not energy_row or not energy_row.get("kwh_30d"):
        return {
            "building_id": building_row["building_id"],
            "building_name": building_row["building_name"],
            "building_type": building_row.get("building_type") or "",
            "building_type_name": std["name"],
            "total_area": area,
            "kwh_30d": 0,
            "annual_kwh": 0,
            "intensity": 0,
            "grade": "N/A",
            "grade_name": "无数据",
            "color": "#d9d9d9",
            "standard": std,
            "saving_potential_kwh": 0,
            "saving_potential_pct": 0,
            "has_data": False,
        }

    kwh_30d = float(energy_row["kwh_30d"] or 0)
    day_cnt = int(energy_row.get("day_cnt") or 30)
    # 年化：30 天累计 × (365 / 实际天数)，避免数据缺失导致偏差
    annual_kwh = kwh_30d * (365.0 / max(1, day_cnt))
    intensity = annual_kwh / area if area > 0 else 0

    grade = _calc_grade(intensity, std)
    grade_info = GRADE_DESC[grade]

    # 节能潜力 = (实际强度 - 先进值) × 面积；低于先进值则无潜力
    saving_kwh = max(0.0, (intensity - std["advanced"]) * area)
    saving_pct = (saving_kwh / annual_kwh * 100) if annual_kwh > 0 else 0

    return {
        "building_id": building_row["building_id"],
        "building_name": building_row["building_name"],
        "building_type": building_row.get("building_type") or "",
        "building_type_name": std["name"],
        "total_area": area,
        "kwh_30d": round(kwh_30d, 2),
        "annual_kwh": round(annual_kwh, 2),
        "intensity": round(intensity, 2),
        "grade": grade,
        "grade_name": grade_info["name"],
        "color": grade_info["color"],
        "standard": std,
        "saving_potential_kwh": round(saving_kwh, 2),
        "saving_potential_pct": round(saving_pct, 2),
        "last_day": str(energy_row.get("last_day") or ""),
        "day_cnt": day_cnt,
        "has_data": True,
    }


@router.get("/api/benchmark/overview")
@run_in_thread
def benchmark_overview():
    """
    全部建筑对标概览
    - 每栋建筑的能耗强度、评级、节能潜力
    """
    try:
        buildings_df = _fetch_building_list()
        if buildings_df.empty:
            return {"status": "success", "data": None, "message": "无建筑数据"}

        energy_df = _fetch_building_energy()
        energy_map = {row["building_id"]: dict(row) for _, row in energy_df.iterrows()}

        records = []
        for _, b_row in buildings_df.iterrows():
            b_dict = dict(b_row)
            e_dict = energy_map.get(b_dict["building_id"])
            records.append(_build_benchmark_record(b_dict, e_dict))

        # 按能耗强度降序（能耗高的在前）
        records.sort(key=lambda r: r.get("intensity", 0), reverse=True)

        # 汇总
        total_area = sum(r["total_area"] for r in records if r.get("has_data"))
        total_annual_kwh = sum(r["annual_kwh"] for r in records if r.get("has_data"))
        total_saving = sum(r["saving_potential_kwh"] for r in records if r.get("has_data"))
        avg_intensity = total_annual_kwh / total_area if total_area > 0 else 0

        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "N/A": 0}
        for r in records:
            grade_counts[r["grade"]] = grade_counts.get(r["grade"], 0) + 1

        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_buildings": len(records),
                    "buildings_with_data": sum(1 for r in records if r.get("has_data")),
                    "total_area": round(total_area, 2),
                    "total_annual_kwh": round(total_annual_kwh, 2),
                    "avg_intensity": round(avg_intensity, 2),
                    "total_saving_potential_kwh": round(total_saving, 2),
                    "total_saving_potential_pct": round(
                        total_saving / total_annual_kwh * 100, 2
                    ) if total_annual_kwh > 0 else 0,
                    "grade_counts": grade_counts,
                },
                "grades": [
                    {"grade": g, "name": GRADE_DESC[g]["name"],
                     "color": GRADE_DESC[g]["color"], "desc": GRADE_DESC[g]["desc"],
                     "count": grade_counts.get(g, 0)}
                    for g in ["A", "B", "C", "D"]
                ],
                "buildings": records,
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "对标数据查询")


@router.get("/api/benchmark/building/{building_id}")
@run_in_thread
def benchmark_building_detail(building_id: str):
    """
    单建筑详细对标报告
    - 概览、每日能耗趋势、设备类型能耗占比、节能建议
    """
    try:
        # 建筑元信息
        with get_conn() as conn:
            b_df = pd.read_sql(
                "SELECT * FROM dim_buildings WHERE building_id = ?",
                conn,
                params=[building_id],
            )
        if b_df.empty:
            return {"status": "error", "code": "NOT_FOUND",
                    "message": f"建筑 {building_id} 不存在"}

        b_dict = dict(b_df.iloc[0])

        # 30 天对标数据
        energy_df = _fetch_building_energy(building_id=building_id)
        energy_row = dict(energy_df.iloc[0]) if not energy_df.empty else None
        benchmark = _build_benchmark_record(b_dict, energy_row)

        # 每日能耗趋势（近 30 天）
        daily_df = _fetch_building_daily_energy(building_id, days=30)
        daily_trend = []
        for _, r in daily_df.iterrows():
            daily_trend.append({
                "day": str(r["day"]),
                "kwh": _safe_float(r["kwh"], 2),
                "avg_hourly": _safe_float(r["avg_hourly"], 2),
                "peak_hourly": _safe_float(r["peak_hourly"], 2),
            })

        # 设备类型能耗占比
        type_df = _fetch_building_type_breakdown(building_id, days=30)
        type_breakdown = []
        total_kwh = float(type_df["kwh"].sum()) if not type_df.empty else 0
        for _, r in type_df.iterrows():
            kwh = _safe_float(r["kwh"], 2) or 0
            type_breakdown.append({
                "device_type": str(r["device_type"]),
                "kwh": kwh,
                "device_cnt": int(r["device_cnt"]),
                "pct": round(kwh / total_kwh * 100, 2) if total_kwh > 0 else 0,
            })

        # 同类型建筑横向对比
        building_type = b_dict.get("building_type")
        with get_conn() as conn:
            peer_df = pd.read_sql(
                """
                SELECT b.building_id, b.building_name, b.total_area,
                       SUM(r.elec_consumption) AS kwh_30d
                FROM dim_buildings b
                LEFT JOIN fact_energy_records r
                  ON r.building_id = b.building_id
                  AND r.monitor_time >= (SELECT datetime(MAX(DATE(monitor_time)), '-30 days')
                                         FROM fact_energy_records)
                WHERE b.building_type = ?
                GROUP BY b.building_id
                ORDER BY kwh_30d DESC
                """,
                conn,
                params=[building_type],
            )
        peers = []
        for _, r in peer_df.iterrows():
            area = _safe_float(r["total_area"], 2) or 0
            kwh = _safe_float(r["kwh_30d"], 2) or 0
            day_cnt = 30
            annual = kwh * (365.0 / day_cnt)
            intensity = annual / area if area > 0 else 0
            peers.append({
                "building_id": str(r["building_id"]),
                "building_name": str(r["building_name"]),
                "total_area": area,
                "annual_kwh": round(annual, 2),
                "intensity": round(intensity, 2),
                "is_current": str(r["building_id"]) == building_id,
            })
        # 按能耗强度排序并填排名
        peers.sort(key=lambda x: x["intensity"])
        for i, p in enumerate(peers):
            p["rank"] = i + 1

        # 生成节能建议
        suggestion = _generate_suggestion(benchmark, type_breakdown)

        std = benchmark["standard"]
        return {
            "status": "success",
            "data": {
                "building": {
                    "building_id": b_dict["building_id"],
                    "building_name": b_dict["building_name"],
                    "building_type": b_dict.get("building_type") or "",
                    "building_type_name": std["name"],
                    "total_area": _safe_float(b_dict.get("total_area"), 2),
                    "location_zone": b_dict.get("location_zone") or "",
                },
                "benchmark": benchmark,
                "standard": std,
                "daily_trend": daily_trend,
                "type_breakdown": type_breakdown,
                "peer_comparison": {
                    "total_peers": len(peers),
                    "current_rank": next((p["rank"] for p in peers if p["is_current"]), None),
                    "best_intensity": min((p["intensity"] for p in peers), default=None),
                    "avg_intensity": round(
                        sum(p["intensity"] for p in peers) / max(1, len(peers)), 2
                    ),
                    "peers": peers,
                },
                "suggestion": suggestion,
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "对标详情查询")


def _generate_suggestion(benchmark: dict, type_breakdown: list) -> str:
    """根据对标结果生成节能建议"""
    if not benchmark.get("has_data"):
        return "暂无能耗数据，无法生成节能建议"

    grade = benchmark["grade"]
    intensity = benchmark["intensity"]
    std = benchmark["standard"]

    if grade == "A":
        base = f"🟢 能耗强度 {intensity:.1f} kWh/㎡·年，达到先进水平（<{std['advanced']}），建议保持当前运行策略"
    elif grade == "B":
        base = f"🔵 能耗强度 {intensity:.1f} kWh/㎡·年，处于合理区间，距离先进值还有 {intensity - std['advanced']:.1f} 的优化空间"
    elif grade == "C":
        base = f"🟠 能耗强度 {intensity:.1f} kWh/㎡·年，已超过合理值（{std['reasonable']}），建议开展节能诊断"
    else:
        base = f"🔴 能耗强度 {intensity:.1f} kWh/㎡·年，超过限额（{std['limit']}），需立即实施节能改造"

    # 主要耗能设备类型
    if type_breakdown:
        top_type = type_breakdown[0]
        type_cn_map = {
            "HVAC": "暖通空调",
            "LIGHTING": "照明",
            "SOCKET": "插座",
            "VENTILATION": "通风",
            "PRECISION_AC": "精密空调",
            "PUMP": "水泵",
            "WATER_HEATER": "热水器",
            "REFRIGERATION": "冷藏",
            "EV_CHARGER": "充电桩",
        }
        top_name = type_cn_map.get(top_type["device_type"], top_type["device_type"])
        base += f"；主要耗能项：{top_name}（{top_type['pct']:.1f}%）"

    saving = benchmark.get("saving_potential_kwh", 0)
    if saving > 0:
        base += f"；预计节能潜力 {saving:.0f} kWh/年"

    return base


@router.get("/api/benchmark/standards")
@run_in_thread
def benchmark_standards():
    """
    国标基准参考值
    - 不同建筑类型的能耗限额、先进值、合理值
    """
    try:
        standards = []
        for bt, cfg in BENCHMARK_STANDARDS.items():
            standards.append({
                "building_type": bt,
                "building_type_name": cfg["name"],
                "limit": cfg["limit"],
                "advanced": cfg["advanced"],
                "reasonable": cfg["reasonable"],
                "standard_source": cfg["standard"],
                "unit": "kWh/㎡·年",
            })

        return {
            "status": "success",
            "data": {
                "standards": standards,
                "grades": [
                    {"grade": g, "name": GRADE_DESC[g]["name"],
                     "color": GRADE_DESC[g]["color"], "desc": GRADE_DESC[g]["desc"],
                     "criteria": crit}
                    for g, crit in [
                        ("A", f"实际强度 < 先进值"),
                        ("B", f"先进值 ≤ 实际强度 < 合理值"),
                        ("C", f"合理值 ≤ 实际强度 < 限额"),
                        ("D", f"实际强度 ≥ 限额"),
                    ]
                ],
                "reference_docs": [
                    "GB 50189《公共建筑节能设计标准》",
                    "JGJ/T 288《建筑节能气象参数标准》",
                    "地方公共建筑能耗限额标准",
                ],
                "unit": "kWh/㎡·年",
            },
        }
    except Exception as e:
        return handle_route_error(e, logger, "对标分析查询")
