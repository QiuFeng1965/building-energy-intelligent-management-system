# -*- coding: utf-8 -*-
"""
ESG 报告生成器路由（符合 GRI / SASB 标准）
- GET /api/esg/overview           ：ESG 概览（E/S/G 三大维度得分 + 总分）
- GET /api/esg/report             ：完整 ESG 报告（含各指标详情）
- GET /api/esg/trend              ：ESG 指标趋势（近 12 个月）
- GET /api/esg/building-carbon    ：按建筑的碳排放明细（用于碳排放排名/占比分析）
- GET /api/esg/benchmark          ：ESG 行业对标分析（与国标/行业基准对比）
- GET /api/esg/recommendations    ：基于当前评分的智能改进建议

维度与权重：
- E（环境）权重 50%：碳排放总量、能耗强度、绿电占比、碳排放强度（用水/废弃物为 mock）
- S（社会）权重 25%：员工安全(mock)、社区影响(基于建筑功能)、合规性(基于告警数)
- G（治理）权重 25%：数据治理(数据完整性)、合规管理(工单完成率)、风险管控(基于异常检测)
- ESG 总分 = E*0.5 + S*0.25 + G*0.25（0-100 分）

数据来源：
- 碳排放 = fact_energy_records.elec_consumption × 0.6231 kgCO2/kWh（华东电网排放因子）
- 绿电 = fact_new_energy.pv_generation_kw（光伏）
- 异常/告警 = fact_energy_records.run_status != 'NORMAL' 或 fault_code 非空
- 工单完成率 = fact_work_orders.status IN ('COMPLETED','VERIFIED') / 总数
"""
import math
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, Query

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.response_cache import cache_response

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 常量 =====
# 电网排放因子（kgCO2/kWh），任务约定 0.6231
GRID_EMISSION_FACTOR = 0.6231

# ESG 维度权重
WEIGHT_E = 0.5
WEIGHT_S = 0.25
WEIGHT_G = 0.25

# 建筑类型 → 社区影响贡献映射（教学/科研/生活服务类社区影响较高）
COMMUNITY_IMPACT_MAP = {
    "TEACHING": 1.0,     # 教学：高社区影响
    "DORMITORY": 0.9,    # 公寓：高
    "CANTEEN": 0.85,     # 食堂：高
    "LIBRARY": 0.8,      # 图书馆：较高
    "LABORATORY": 0.7,   # 科研：中高
    "CONFERENCE": 0.6,   # 会议：中
    "OFFICE": 0.5,       # 办公：中
    "PLAZA": 0.6,        # 广场：中
}

# 能耗强度评级阈值（kWh/㎡·年，用于 E 维度子项打分）
INTENSITY_THRESHOLDS = {
    "advanced": 35,    # 先进值
    "reasonable": 50,  # 合理值
    "limit": 70,       # 限额
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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """限制数值在 [lo, hi] 区间"""
    return max(lo, min(hi, v))


# ===== 真实数据采集 =====
def _fetch_energy_summary(days: int = 30) -> dict:
    """
    汇总近 N 天的能耗真实数据
    - 总用电量、总碳排放、异常记录数、故障记录数、记录总数、覆盖天数
    - 用 MAX(DATE(monitor_time)) 作为基准日往前推 N 天，避免数据断层
    """
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT
                SUM(elec_consumption) AS total_kwh,
                COUNT(*) AS record_cnt,
                COUNT(DISTINCT DATE(monitor_time)) AS day_cnt,
                SUM(CASE WHEN run_status IS NOT NULL AND run_status != 'NORMAL' THEN 1 ELSE 0 END) AS anomaly_cnt,
                SUM(CASE WHEN fault_code IS NOT NULL AND fault_code != '' THEN 1 ELSE 0 END) AS fault_cnt,
                MAX(monitor_time) AS last_day_ts
            FROM fact_energy_records
            WHERE monitor_time >= datetime('now', 'localtime', ?)
            """,
            conn,
            params=[f"-{days} days"],
        )
    if df.empty:
        return {
            "total_kwh": 0.0, "record_cnt": 0, "day_cnt": 0,
            "anomaly_cnt": 0, "fault_cnt": 0, "last_day": None,
        }
    row = df.iloc[0]
    # 从 timestamp 提取日期（MAX(monitor_time) 可走索引，比 MAX(DATE(monitor_time)) 高效）
    last_day_ts = row["last_day_ts"]
    if last_day_ts is not None:
        last_day = str(last_day_ts)[:10]  # "2026-07-28 12:00:00" -> "2026-07-28"
    else:
        last_day = None
    return {
        "total_kwh": float(row["total_kwh"] or 0),
        "record_cnt": int(row["record_cnt"] or 0),
        "day_cnt": int(row["day_cnt"] or 0),
        "anomaly_cnt": int(row["anomaly_cnt"] or 0),
        "fault_cnt": int(row["fault_cnt"] or 0),
        "last_day": last_day,
    }


def _fetch_green_energy(days: int = 30) -> float:
    """近 N 天光伏发电量累计（fact_new_energy.pv_generation_kw，按小时采样近似 kWh）"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT SUM(pv_generation_kw) AS pv_sum
            FROM fact_new_energy
            WHERE timestamp >= datetime('now', 'localtime', ?)
            """,
            conn,
            params=[f"-{days} days"],
        )
    if df.empty:
        return 0.0
    return float(df.iloc[0]["pv_sum"] or 0)


def _fetch_building_stats() -> dict:
    """建筑总数、总面积、各建筑类型分布（真实数据）"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT building_id, building_name, building_type, total_area
            FROM dim_buildings
            """,
            conn,
        )
    if df.empty:
        return {"total_buildings": 0, "total_area": 0.0, "type_distribution": {}}
    total_area = float(df["total_area"].sum() or 0)
    type_dist = df.groupby("building_type").size().to_dict()
    return {
        "total_buildings": int(len(df)),
        "total_area": total_area,
        "type_distribution": {k: int(v) for k, v in type_dist.items()},
    }


def _fetch_workorder_completion(days: int = 30) -> dict:
    """
    近 N 天工单完成情况（真实数据，用于 G 维度合规管理打分）
    - 总工单数、已完成数、完成率
    - 平均处理时长（小时）
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT
                    COUNT(*) AS total_cnt,
                    SUM(CASE WHEN status IN ('COMPLETED','VERIFIED') THEN 1 ELSE 0 END) AS completed_cnt,
                    AVG(CASE WHEN completed_at IS NOT NULL AND created_at IS NOT NULL
                        THEN (julianday(completed_at) - julianday(created_at)) * 24 END) AS avg_hours
                FROM fact_work_orders
                WHERE created_at >= datetime('now', 'localtime', ?)
                """,
                conn,
                params=[f"-{days} days"],
            )
        if df.empty:
            return {"total": 0, "completed": 0, "completion_rate": 0.0, "avg_hours": 0.0}
        row = df.iloc[0]
        total = int(row["total_cnt"] or 0)
        completed = int(row["completed_cnt"] or 0)
        rate = (completed / total) if total > 0 else 0.0
        avg_h = float(row["avg_hours"] or 0)
        return {
            "total": total,
            "completed": completed,
            "completion_rate": round(rate, 4),
            "avg_hours": round(avg_h, 2),
        }
    except Exception as e:
        logger.warning(f"工单完成率查询失败（可能表不存在）: {e}")
        return {"total": 0, "completed": 0, "completion_rate": 0.0, "avg_hours": 0.0}


# ===== 维度打分 =====
def _score_e(total_kwh: float, total_area: float, green_kwh: float, day_cnt: int) -> dict:
    """
    E（环境）维度打分（0-100）
    - 子项1 碳排放强度（kgCO2/㎡·年）：越低越好
    - 子项2 能耗强度（kWh/㎡·年）：按国标阈值评级映射
    - 子项3 绿电占比：越高越好
    - 用水/废弃物：mock（标注）
    """
    # 年化系数：基于实际覆盖天数
    annual_factor = 365.0 / max(1, day_cnt) if day_cnt > 0 else 0
    annual_kwh = total_kwh * annual_factor
    annual_carbon_kg = annual_kwh * GRID_EMISSION_FACTOR

    carbon_intensity = (annual_carbon_kg / total_area) if total_area > 0 else 0  # kgCO2/㎡·年
    energy_intensity = (annual_kwh / total_area) if total_area > 0 else 0        # kWh/㎡·年
    green_ratio = (green_kwh / total_kwh) if total_kwh > 0 else 0                # 0-1
    green_ratio = _clamp(green_ratio, 0.0, 1.0)

    # 子项1：碳排放强度得分（基准 30 kgCO2/㎡·年为 60 分，每低 5 分加 10 分，每高 5 分扣 8 分）
    sub1 = _clamp(60 + (30 - carbon_intensity) / 5 * 10, 0, 100)
    # 子项2：能耗强度评级映射
    if energy_intensity < INTENSITY_THRESHOLDS["advanced"]:
        sub2 = 95.0
    elif energy_intensity < INTENSITY_THRESHOLDS["reasonable"]:
        sub2 = 80.0
    elif energy_intensity < INTENSITY_THRESHOLDS["limit"]:
        sub2 = 65.0
    else:
        sub2 = 45.0
    # 子项3：绿电占比得分（占比 30% 即满分，线性映射）
    sub3 = _clamp(green_ratio / 0.3 * 100, 0, 100)

    e_score = _clamp(sub1 * 0.4 + sub2 * 0.4 + sub3 * 0.2, 0, 100)

    return {
        "score": round(e_score, 1),
        "sub_metrics": {
            "carbon_emission_total_kg": round(annual_carbon_kg, 2),
            "carbon_intensity_kg_per_m2": round(carbon_intensity, 2),
            "energy_intensity_kwh_per_m2": round(energy_intensity, 2),
            "green_ratio_pct": round(green_ratio * 100, 2),
            "green_energy_kwh": round(green_kwh, 2),
            "total_kwh_annual": round(annual_kwh, 2),
            "sub_scores": {
                "carbon_intensity_score": round(sub1, 1),
                "energy_intensity_score": round(sub2, 1),
                "green_ratio_score": round(sub3, 1),
            },
            # mock 指标（标注）
            "water_consumption_t": {"value": 1250.0, "mock": True, "desc": "用水量（模拟数据）"},
            "waste_recycled_pct": {"value": 78.5, "mock": True, "desc": "废弃物回收率%（模拟数据）"},
        },
    }


def _score_s(anomaly_cnt: int, type_distribution: dict) -> dict:
    """
    S（社会）维度打分（0-100）
    - 员工安全：mock（标注）
    - 社区影响：基于建筑功能（教学/科研/生活服务类占比）
    - 合规性：基于告警/异常数（越少越好）
    """
    # 子项1：员工安全（mock）
    sub1 = 92.0  # mock：近一年无工伤事故

    # 子项2：社区影响：高影响建筑类型占比 → 得分
    high_impact_types = {"TEACHING", "DORMITORY", "CANTEEN", "LIBRARY"}
    total_b = sum(type_distribution.values()) if type_distribution else 0
    high_cnt = sum(c for t, c in (type_distribution or {}).items() if t in high_impact_types)
    high_ratio = (high_cnt / total_b) if total_b > 0 else 0
    sub2 = _clamp(60 + high_ratio * 40, 0, 100)

    # 子项3：合规性：异常数越少得分越高（基准 50 条异常 = 60 分）
    sub3 = _clamp(100 - anomaly_cnt * 0.8, 0, 100)

    s_score = _clamp(sub1 * 0.3 + sub2 * 0.35 + sub3 * 0.35, 0, 100)

    return {
        "score": round(s_score, 1),
        "sub_metrics": {
            "employee_safety": {"value": sub1, "mock": True, "desc": "员工安全（模拟：无工伤事故）"},
            "community_impact_score": round(sub2, 1),
            "community_impact_ratio": round(high_ratio * 100, 2),
            "compliance_score": round(sub3, 1),
            "anomaly_count": anomaly_cnt,
            "sub_scores": {
                "employee_safety_score": round(sub1, 1),
                "community_impact_score": round(sub2, 1),
                "compliance_score": round(sub3, 1),
            },
        },
    }


def _score_g(record_cnt: int, day_cnt: int, anomaly_cnt: int, fault_cnt: int, workorder: Optional[dict] = None) -> dict:
    """
    G（治理）维度打分（0-100）
    - 数据治理：数据完整性（记录数/预期）+ 系统可用性（mock）
    - 合规管理：工单完成率（真实数据，fallback mock 90%）
    - 风险管控：基于异常检测结果（异常/故障越少越好）
    """
    # 子项1：数据治理
    # 数据完整性：预期每小时 1 条 × 设备数 × 天数，这里用 day_cnt 覆盖率近似
    # 预期覆盖天数取 30，完整性 = day_cnt / 30
    data_completeness = _clamp(day_cnt / 30.0, 0, 1)
    system_availability = 99.5  # mock
    sub1 = _clamp(data_completeness * 60 + (system_availability - 95) * 8, 0, 100)

    # 子项2：合规管理 —— 优先使用真实工单完成率，无数据时 fallback 90%
    if workorder and workorder.get("total", 0) > 0:
        audit_completion = workorder["completion_rate"] * 100.0
        wo_avg_hours = workorder.get("avg_hours", 0)
        wo_total = workorder.get("total", 0)
        wo_completed = workorder.get("completed", 0)
        wo_source = "real"
    else:
        audit_completion = 90.0  # mock
        wo_avg_hours = 0.0
        wo_total = 0
        wo_completed = 0
        wo_source = "mock"
    sub2 = _clamp(audit_completion, 0, 100)

    # 子项3：风险管控：异常 + 故障数越少越好（基准 100 条 = 50 分）
    risk_count = anomaly_cnt + fault_cnt
    sub3 = _clamp(100 - risk_count * 0.5, 0, 100)

    g_score = _clamp(sub1 * 0.4 + sub2 * 0.3 + sub3 * 0.3, 0, 100)

    return {
        "score": round(g_score, 1),
        "sub_metrics": {
            "data_governance_score": round(sub1, 1),
            "data_completeness_pct": round(data_completeness * 100, 2),
            "system_availability_pct": {"value": system_availability, "mock": True, "desc": "系统可用性（模拟）"},
            "audit_completion_pct": {
                "value": round(audit_completion, 2),
                "mock": wo_source == "mock",
                "source": wo_source,
                "desc": "工单完成率（真实数据）" if wo_source == "real" else "审计完成率（模拟）",
                "total_workorders": wo_total,
                "completed_workorders": wo_completed,
                "avg_handle_hours": wo_avg_hours,
            },
            "risk_management_score": round(sub3, 1),
            "anomaly_count": anomaly_cnt,
            "fault_count": fault_cnt,
            "sub_scores": {
                "data_governance_score": round(sub1, 1),
                "compliance_management_score": round(sub2, 1),
                "risk_management_score": round(sub3, 1),
            },
        },
    }


def _compute_esg(days: int = 30) -> dict:
    """汇总真实数据并计算 E/S/G 三维度得分与总分"""
    energy = _fetch_energy_summary(days=days)
    green_kwh = _fetch_green_energy(days=days)
    building_stats = _fetch_building_stats()
    workorder = _fetch_workorder_completion(days=days)

    total_area = building_stats["total_area"]
    e = _score_e(energy["total_kwh"], total_area, green_kwh, energy["day_cnt"])
    s = _score_s(energy["anomaly_cnt"], building_stats["type_distribution"])
    g = _score_g(energy["record_cnt"], energy["day_cnt"], energy["anomaly_cnt"], energy["fault_cnt"], workorder)

    total_score = _clamp(e["score"] * WEIGHT_E + s["score"] * WEIGHT_S + g["score"] * WEIGHT_G, 0, 100)

    return {
        "scores": {
            "total": round(total_score, 1),
            "E": e["score"],
            "S": s["score"],
            "G": g["score"],
            "weights": {"E": WEIGHT_E, "S": WEIGHT_S, "G": WEIGHT_G},
        },
        "E": e,
        "S": s,
        "G": g,
        "raw_data": {
            "period_days": days,
            "last_day": energy["last_day"],
            "total_kwh": round(energy["total_kwh"], 2),
            "green_energy_kwh": round(green_kwh, 2),
            "total_area": round(total_area, 2),
            "total_buildings": building_stats["total_buildings"],
            "record_count": energy["record_cnt"],
            "anomaly_count": energy["anomaly_cnt"],
            "fault_count": energy["fault_cnt"],
            "workorder": workorder,
        },
    }


# ===== 路由 =====
@router.get("/api/esg/overview")
@cache_response(ttl=60)  # ESG 概览，缓存 1 分钟
@run_in_thread
def esg_overview(days: int = Query(30, ge=1, le=365, description="统计天数")):
    """ESG 概览：E/S/G 三大维度得分 + 总分"""
    try:
        result = _compute_esg(days=days)
        scores = result["scores"]
        return {
            "status": "success",
            "data": {
                "total_score": scores["total"],
                "dimensions": {
                    "E": {"name": "环境", "score": scores["E"], "weight": WEIGHT_E},
                    "S": {"name": "社会", "score": scores["S"], "weight": WEIGHT_S},
                    "G": {"name": "治理", "score": scores["G"], "weight": WEIGHT_G},
                },
                "grade": _esg_grade(scores["total"]),
                "period_days": days,
                "last_day": result["raw_data"]["last_day"],
                "standards": ["GRI Standards", "SASB Standards"],
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ESG 概览查询失败: {e}")
        return {"status": "error", "message": "ESG 概览查询失败，请稍后重试"}


@router.get("/api/esg/report")
@cache_response(ttl=60)  # ESG 报告，缓存 1 分钟
@run_in_thread
def esg_report(days: int = Query(30, ge=1, le=365, description="统计天数")):
    """完整 ESG 报告：含各指标详情"""
    try:
        result = _compute_esg(days=days)
        report_id = f"ESG-{datetime.datetime.now().strftime('%Y%m%d')}"
        return {
            "status": "success",
            "data": {
                "report_id": report_id,
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "period_days": days,
                "standards": ["GRI Standards", "SASB Standards"],
                "scores": result["scores"],
                "grade": _esg_grade(result["scores"]["total"]),
                "dimensions": {
                    "E": {
                        "name": "环境",
                        "weight": WEIGHT_E,
                        "score": result["E"]["score"],
                        "metrics": result["E"]["sub_metrics"],
                        "description": "碳排放、能耗强度、绿电占比等环境绩效指标",
                    },
                    "S": {
                        "name": "社会",
                        "weight": WEIGHT_S,
                        "score": result["S"]["score"],
                        "metrics": result["S"]["sub_metrics"],
                        "description": "员工安全、社区影响、合规性等社会责任指标",
                    },
                    "G": {
                        "name": "治理",
                        "weight": WEIGHT_G,
                        "score": result["G"]["score"],
                        "metrics": result["G"]["sub_metrics"],
                        "description": "数据治理、合规管理、风险管控等公司治理指标",
                    },
                },
                "raw_data": result["raw_data"],
                "conclusion": _esg_conclusion(result),
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ESG 报告生成失败: {e}")
        return {"status": "error", "message": "ESG 报告生成失败，请稍后重试"}


@router.get("/api/esg/trend")
@cache_response(ttl=300)  # 月度趋势数据，缓存 5 分钟
@run_in_thread
def esg_trend():
    """ESG 指标趋势：近 12 个月的 E/S/G 得分"""
    try:
        # 按月聚合近 12 个月的能耗与异常数据（真实数据）
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT
                    strftime('%Y-%m', monitor_time) AS month,
                    SUM(elec_consumption) AS kwh,
                    COUNT(*) AS record_cnt,
                    COUNT(DISTINCT DATE(monitor_time)) AS day_cnt,
                    SUM(CASE WHEN run_status IS NOT NULL AND run_status != 'NORMAL' THEN 1 ELSE 0 END) AS anomaly_cnt,
                    SUM(CASE WHEN fault_code IS NOT NULL AND fault_code != '' THEN 1 ELSE 0 END) AS fault_cnt
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-12 months')
                GROUP BY month
                ORDER BY month
                """,
                conn,
            )
            # 光伏月度数据
            pv_df = pd.read_sql(
                """
                SELECT
                    strftime('%Y-%m', timestamp) AS month,
                    SUM(pv_generation_kw) AS pv_sum
                FROM fact_new_energy
                WHERE timestamp >= datetime('now', 'localtime', '-12 months')
                GROUP BY month
                ORDER BY month
                """,
                conn,
            )
            # 总面积（用于强度计算）
            area_df = pd.read_sql("SELECT SUM(total_area) AS total_area FROM dim_buildings", conn)
        total_area = float(area_df.iloc[0]["total_area"] or 0) if not area_df.empty else 0
        pv_map = {r["month"]: float(r["pv_sum"] or 0) for _, r in pv_df.iterrows()} if not pv_df.empty else {}

        trend = []
        for _, row in df.iterrows():
            month = str(row["month"])
            kwh = float(row["kwh"] or 0)
            day_cnt = int(row["day_cnt"] or 0)
            anomaly_cnt = int(row["anomaly_cnt"] or 0)
            fault_cnt = int(row["fault_cnt"] or 0)
            pv_kwh = pv_map.get(month, 0.0)

            # 月度年化：该月能耗 × 12 近似年化（用于强度计算）
            e = _score_e(kwh, total_area, pv_kwh, max(day_cnt, 1))
            # 月度 E 用年化系数会放大，这里改用月度数据直接计算强度（kWh/㎡·月 → ×12 年化）
            annual_kwh = kwh * 12
            annual_carbon = annual_kwh * GRID_EMISSION_FACTOR
            carbon_intensity = (annual_carbon / total_area) if total_area > 0 else 0
            energy_intensity = (annual_kwh / total_area) if total_area > 0 else 0
            green_ratio = _clamp((pv_kwh / kwh) if kwh > 0 else 0, 0, 1)
            e_score = e["score"]

            # S 维度：基于月度异常数
            s = _score_s(anomaly_cnt, {})  # 社区影响用默认
            # G 维度：基于月度数据完整性与异常
            g = _score_g(int(row["record_cnt"] or 0), day_cnt, anomaly_cnt, fault_cnt)

            total = _clamp(e_score * WEIGHT_E + s["score"] * WEIGHT_S + g["score"] * WEIGHT_G, 0, 100)

            trend.append({
                "month": month,
                # 兼容字段：同时返回 E/S/G/total 和 e_score/s_score/g_score/total_score
                "E": round(e_score, 1),
                "S": round(s["score"], 1),
                "G": round(g["score"], 1),
                "total": round(total, 1),
                "e_score": round(e_score, 1),
                "s_score": round(s["score"], 1),
                "g_score": round(g["score"], 1),
                "total_score": round(total, 1),
                "metrics": {
                    "kwh": round(kwh, 2),
                    "carbon_kg": round(kwh * GRID_EMISSION_FACTOR, 2),
                    "carbon_intensity_kg_per_m2": round(carbon_intensity, 2),
                    "energy_intensity_kwh_per_m2": round(energy_intensity, 2),
                    "green_ratio_pct": round(green_ratio * 100, 2),
                    "anomaly_cnt": anomaly_cnt,
                    "fault_cnt": fault_cnt,
                },
            })

        return {
            "status": "success",
            "data": {
                "months": len(trend),
                "trend": trend,
                "weights": {"E": WEIGHT_E, "S": WEIGHT_S, "G": WEIGHT_G},
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ESG 趋势查询失败: {e}")
        return {"status": "error", "message": "ESG 趋势查询失败，请稍后重试"}


# ===== 辅助 =====
def _esg_grade(score: float) -> dict:
    """ESG 总分评级"""
    if score >= 90:
        return {"grade": "AAA", "name": "卓越", "color": "#52c41a"}
    if score >= 80:
        return {"grade": "AA", "name": "优秀", "color": "#73d13d"}
    if score >= 70:
        return {"grade": "A", "name": "良好", "color": "#1890ff"}
    if score >= 60:
        return {"grade": "BBB", "name": "合格", "color": "#faad14"}
    if score >= 50:
        return {"grade": "BB", "name": "待改进", "color": "#fa8c16"}
    return {"grade": "C", "name": "落后", "color": "#ff4d4f"}


def _esg_conclusion(result: dict) -> str:
    """根据 ESG 评分生成结论文字"""
    s = result["scores"]
    grade = _esg_grade(s["total"])
    conclusion = f"本期 ESG 总分 {s['total']} 分，评级 {grade['grade']}（{grade['name']}）。"
    # 找出最弱维度
    dims = {"环境(E)": s["E"], "社会(S)": s["S"], "治理(G)": s["G"]}
    weakest = min(dims, key=dims.get)
    strongest = max(dims, key=dims.get)
    conclusion += f"最强维度为 {strongest}（{dims[strongest]} 分），"
    conclusion += f"建议重点关注 {weakest}（{dims[weakest]} 分）的提升空间。"
    return conclusion


# ===== 新增接口 1：按建筑的碳排放明细 =====
@router.get("/api/esg/building-carbon")
@cache_response(ttl=120)  # 建筑碳排放明细，缓存 2 分钟
@run_in_thread
def esg_building_carbon(days: int = Query(30, ge=1, le=365, description="统计天数")):
    """
    按建筑维度展示碳排放明细，用于碳排放占比/排名分析
    - 每栋建筑的总能耗、总碳排放、碳排放强度、年化碳排放
    - 排放占比、累计占比（帕累托分析）
    - 排名标识（top3 标红，节能改造优先级）
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT
                    b.building_id,
                    b.building_name,
                    b.building_type,
                    b.total_area,
                    COALESCE(SUM(e.elec_consumption), 0) AS total_kwh,
                    COUNT(DISTINCT DATE(e.monitor_time)) AS day_cnt
                FROM dim_buildings b
                LEFT JOIN fact_energy_records e
                    ON e.building_id = b.building_id
                   AND e.monitor_time >= datetime('now', 'localtime', ?)
                GROUP BY b.building_id, b.building_name, b.building_type, b.total_area
                ORDER BY total_kwh DESC
                """,
                conn,
                params=[f"-{days} days"],
            )
        if df.empty:
            return {"status": "success", "data": {"buildings": [], "total_carbon_kg": 0}}

        # 年化系数
        items = []
        total_carbon = 0.0
        for _, row in df.iterrows():
            kwh = float(row["total_kwh"] or 0)
            day_cnt = int(row["day_cnt"] or 0)
            area = float(row["total_area"] or 0)
            annual_factor = 365.0 / max(1, day_cnt) if day_cnt > 0 else 0
            annual_kwh = kwh * annual_factor
            carbon_kg = kwh * GRID_EMISSION_FACTOR
            annual_carbon_kg = annual_kwh * GRID_EMISSION_FACTOR
            carbon_intensity = (annual_carbon_kg / area) if area > 0 else 0
            total_carbon += carbon_kg
            items.append({
                "building_id": str(row["building_id"]),
                "building_name": str(row["building_name"]),
                "building_type": str(row["building_type"] or ""),
                "total_area": round(area, 2),
                "total_kwh": round(kwh, 2),
                "carbon_kg": round(carbon_kg, 2),
                "annual_kwh": round(annual_kwh, 2),
                "annual_carbon_kg": round(annual_carbon_kg, 2),
                "carbon_intensity_kg_per_m2": round(carbon_intensity, 2),
                "day_cnt": day_cnt,
            })

        # 计算占比与累计占比（帕累托）
        for it in items:
            it["carbon_pct"] = round((it["carbon_kg"] / total_carbon * 100) if total_carbon > 0 else 0, 2)

        cumulative = 0.0
        for it in items:
            cumulative += it["carbon_pct"]
            it["cumulative_pct"] = round(cumulative, 2)

        # 排名与优先级标识
        for idx, it in enumerate(items):
            it["rank"] = idx + 1
            if idx < 3:
                it["priority"] = "high"          # 前 3 名：高优先级（排放大户）
            elif it["carbon_pct"] >= 10:
                it["priority"] = "medium"        # 占比 ≥10%：中优先级
            else:
                it["priority"] = "low"

        return {
            "status": "success",
            "data": {
                "period_days": days,
                "total_carbon_kg": round(total_carbon, 2),
                "total_buildings": len(items),
                "buildings": items,
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"建筑碳排放明细查询失败: {e}")
        return {"status": "error", "message": "建筑碳排放明细查询失败，请稍后重试"}


# ===== 新增接口 2：ESG 行业对标分析 =====
# 行业基准数据（公共建筑 ESG 表现参考值，基于 GB/T 51366-2019 与公开 ESG 报告整理）
INDUSTRY_BENCHMARKS = {
    "energy_intensity_kwh_per_m2": {
        "advanced": 35.0,    # 先进值（领先 25%）
        "average": 55.0,     # 行业平均
        "laggard": 80.0,     # 落后值（后 25%）
        "unit": "kWh/㎡·年",
        "desc": "能耗强度",
    },
    "carbon_intensity_kg_per_m2": {
        "advanced": 22.0,    # 先进值
        "average": 35.0,
        "laggard": 50.0,
        "unit": "kgCO2/㎡·年",
        "desc": "碳排放强度",
    },
    "green_ratio_pct": {
        "advanced": 30.0,
        "average": 10.0,
        "laggard": 0.0,
        "unit": "%",
        "desc": "绿电占比",
    },
    "anomaly_rate_per_thousand": {
        "advanced": 1.0,     # 异常率（每千条记录异常数）
        "average": 5.0,
        "laggard": 15.0,
        "unit": "‰",
        "desc": "异常率",
    },
}


@router.get("/api/esg/benchmark")
@cache_response(ttl=300)  # 对标分析，缓存 5 分钟
@run_in_thread
def esg_benchmark(days: int = Query(30, ge=1, le=365, description="统计天数")):
    """
    ESG 行业对标分析
    - 将本项目各项 ESG 指标与行业基准（先进/平均/落后）对比
    - 计算对标得分（0-100）：先进=100，平均=70，落后=40
    - 给出该指标的对标等级（领先/平均/落后）
    """
    try:
        result = _compute_esg(days=days)
        e_metrics = result["E"]["sub_metrics"]
        raw = result["raw_data"]

        # 计算异常率（每千条记录异常数）
        record_cnt = raw.get("record_count", 0)
        anomaly_cnt = raw.get("anomaly_count", 0)
        anomaly_rate = (anomaly_cnt / record_cnt * 1000) if record_cnt > 0 else 0

        # 当前项目实际值
        actuals = {
            "energy_intensity_kwh_per_m2": e_metrics.get("energy_intensity_kwh_per_m2", 0),
            "carbon_intensity_kg_per_m2": e_metrics.get("carbon_intensity_kg_per_m2", 0),
            "green_ratio_pct": e_metrics.get("green_ratio_pct", 0),
            "anomaly_rate_per_thousand": round(anomaly_rate, 2),
        }

        benchmarks = []
        for key, bench in INDUSTRY_BENCHMARKS.items():
            actual = actuals.get(key, 0)
            advanced = bench["advanced"]
            average = bench["average"]
            laggard = bench["laggard"]

            # 对于"越低越好"的指标（能耗强度/碳排放强度/异常率）：先进值 < 平均值 < 落后值
            # 对于"越高越好"的指标（绿电占比）：先进值 > 平均值 > 落后值
            lower_is_better = advanced < average

            if lower_is_better:
                if actual <= advanced:
                    score, level = 100.0, "领先"
                elif actual <= average:
                    # 在先进与平均之间线性插值
                    score = 100 - (actual - advanced) / (average - advanced) * 30
                    level = "领先" if score >= 85 else "平均"
                elif actual <= laggard:
                    score = 70 - (actual - average) / (laggard - average) * 30
                    level = "平均" if score >= 55 else "落后"
                else:
                    score, level = 40.0, "落后"
            else:
                # 越高越好
                if actual >= advanced:
                    score, level = 100.0, "领先"
                elif actual >= average:
                    score = 70 + (actual - average) / (advanced - average) * 30
                    level = "领先" if score >= 85 else "平均"
                elif actual >= laggard:
                    score = 40 + (actual - laggard) / (average - laggard) * 30
                    level = "平均" if score >= 55 else "落后"
                else:
                    score, level = 40.0, "落后"

            score = _clamp(score, 0, 100)
            gap_to_advanced = (actual - advanced) if lower_is_better else (advanced - actual)
            benchmarks.append({
                "metric_key": key,
                "metric_name": bench["desc"],
                "unit": bench["unit"],
                "actual_value": round(actual, 2),
                "benchmark": {
                    "advanced": advanced,
                    "average": average,
                    "laggard": laggard,
                },
                "score": round(score, 1),
                "level": level,
                "gap_to_advanced": round(gap_to_advanced, 2),
                "lower_is_better": lower_is_better,
            })

        # 总体对标得分（各指标平均）
        overall_score = sum(b["score"] for b in benchmarks) / max(1, len(benchmarks))
        overall_level = "领先" if overall_score >= 85 else ("平均" if overall_score >= 55 else "落后")

        return {
            "status": "success",
            "data": {
                "period_days": days,
                "overall_score": round(overall_score, 1),
                "overall_level": overall_level,
                "benchmarks": benchmarks,
                "standards_reference": "GB/T 51366-2019《建筑碳排放计算标准》",
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ESG 对标分析失败: {e}")
        return {"status": "error", "message": "ESG 对标分析失败，请稍后重试"}


# ===== 新增接口 3：ESG 智能改进建议 =====
@router.get("/api/esg/recommendations")
@cache_response(ttl=300)  # 改进建议，缓存 5 分钟
@run_in_thread
def esg_recommendations(days: int = Query(30, ge=1, le=365, description="统计天数")):
    """
    基于当前 ESG 评分生成具体的改进建议
    - 按维度（E/S/G）给出弱项分析
    - 每条建议包含：维度、当前得分、目标得分、改进措施、预期提升、实施难度
    """
    try:
        result = _compute_esg(days=days)
        scores = result["scores"]
        recommendations = []

        # ===== E 维度建议 =====
        e_score = scores["E"]
        e_metrics = result["E"]["sub_metrics"]
        green_ratio = e_metrics.get("green_ratio_pct", 0)
        carbon_intensity = e_metrics.get("carbon_intensity_kg_per_m2", 0)
        energy_intensity = e_metrics.get("energy_intensity_kwh_per_m2", 0)

        if e_score < 80:
            if green_ratio < 10:
                recommendations.append({
                    "dimension": "E",
                    "dimension_name": "环境",
                    "current_score": e_score,
                    "target_score": min(100, e_score + 15),
                    "title": "提升绿电占比",
                    "issue": f"当前绿电占比仅 {green_ratio}%，远低于行业先进值 30%",
                    "actions": [
                        "屋顶分布式光伏加装（建议装机 100-200kW）",
                        "采购绿色电力证书（GEC）或参与绿电交易",
                        "建设储能系统，提升光伏自消纳率",
                    ],
                    "expected_improvement": 8,
                    "difficulty": "中",
                    "priority": "high",
                })
            if energy_intensity > 50:
                recommendations.append({
                    "dimension": "E",
                    "dimension_name": "环境",
                    "current_score": e_score,
                    "target_score": min(100, e_score + 12),
                    "title": "降低能耗强度",
                    "issue": f"当前能耗强度 {energy_intensity} kWh/㎡·年，高于国标先进值 35",
                    "actions": [
                        "暖通系统改造：更换磁悬浮冷水机组（节能 25%）",
                        "加装变频驱动 VFD（节能 15%）",
                        "智能照明改造 LED（节能 60%）",
                        "建筑外保温改造（节能 12%）",
                    ],
                    "expected_improvement": 12,
                    "difficulty": "高",
                    "priority": "high",
                })
            if carbon_intensity > 35:
                recommendations.append({
                    "dimension": "E",
                    "dimension_name": "环境",
                    "current_score": e_score,
                    "target_score": min(100, e_score + 6),
                    "title": "降低碳排放强度",
                    "issue": f"当前碳排放强度 {carbon_intensity} kgCO2/㎡·年",
                    "actions": [
                        "优化运行策略，减少空载能耗",
                        "参与碳市场交易，抵消部分排放",
                    ],
                    "expected_improvement": 6,
                    "difficulty": "中",
                    "priority": "medium",
                })

        # ===== S 维度建议 =====
        s_score = scores["S"]
        s_metrics = result["S"]["sub_metrics"]
        anomaly_cnt = s_metrics.get("anomaly_count", 0)
        compliance_score = s_metrics.get("compliance_score", 0)

        if s_score < 80:
            if compliance_score < 70:
                recommendations.append({
                    "dimension": "S",
                    "dimension_name": "社会",
                    "current_score": s_score,
                    "target_score": min(100, s_score + 10),
                    "title": "降低异常告警数量",
                    "issue": f"近 {days} 天异常记录 {anomaly_cnt} 条，合规得分 {compliance_score} 分",
                    "actions": [
                        "建立异常告警根因分析机制",
                        "对高频告警设备进行预防性维护",
                        "完善告警静默与压缩策略，减少无效告警",
                    ],
                    "expected_improvement": 10,
                    "difficulty": "中",
                    "priority": "high",
                })
            else:
                recommendations.append({
                    "dimension": "S",
                    "dimension_name": "社会",
                    "current_score": s_score,
                    "target_score": min(100, s_score + 5),
                    "title": "提升社区影响",
                    "issue": "社区影响维度可进一步提升",
                    "actions": [
                        "公开 ESG 报告，增强信息透明度",
                        "开展节能宣传与社区共建活动",
                    ],
                    "expected_improvement": 5,
                    "difficulty": "低",
                    "priority": "low",
                })

        # ===== G 维度建议 =====
        g_score = scores["G"]
        g_metrics = result["G"]["sub_metrics"]
        data_completeness = g_metrics.get("data_completeness_pct", 0)
        audit_info = g_metrics.get("audit_completion_pct", {})
        audit_pct = audit_info.get("value", 0) if isinstance(audit_info, dict) else 0
        risk_score = g_metrics.get("risk_management_score", 0)

        if g_score < 80:
            if data_completeness < 90:
                recommendations.append({
                    "dimension": "G",
                    "dimension_name": "治理",
                    "current_score": g_score,
                    "target_score": min(100, g_score + 8),
                    "title": "提升数据完整性",
                    "issue": f"当前数据完整性 {data_completeness}%，存在数据缺失",
                    "actions": [
                        "排查数据采集断点，补齐缺失时段数据",
                        "增加数据采集冗余，关键节点双路采集",
                        "建立数据质量监控告警机制",
                    ],
                    "expected_improvement": 8,
                    "difficulty": "中",
                    "priority": "medium",
                })
            if audit_pct < 90:
                recommendations.append({
                    "dimension": "G",
                    "dimension_name": "治理",
                    "current_score": g_score,
                    "target_score": min(100, g_score + 10),
                    "title": "提升工单完成率",
                    "issue": f"当前工单完成率 {audit_pct}%，存在工单积压",
                    "actions": [
                        "优化工单派发策略，按技能自动匹配",
                        "建立工单超时升级机制，SLA 警戒线提醒",
                        "增加备件库存预警，避免缺料延误",
                    ],
                    "expected_improvement": 10,
                    "difficulty": "中",
                    "priority": "high",
                })
            if risk_score < 70:
                recommendations.append({
                    "dimension": "G",
                    "dimension_name": "治理",
                    "current_score": g_score,
                    "target_score": min(100, g_score + 8),
                    "title": "强化风险管控",
                    "issue": f"风险管控得分 {risk_score} 分，异常/故障数偏高",
                    "actions": [
                        "部署设备健康度 RUL 预测，提前预警",
                        "建立关键设备故障应急预案",
                        "定期开展风险评估与隐患排查",
                    ],
                    "expected_improvement": 8,
                    "difficulty": "高",
                    "priority": "medium",
                })

        # 按优先级排序：high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: (priority_order.get(x["priority"], 99), -x["expected_improvement"]))

        total_expected = sum(r["expected_improvement"] for r in recommendations)
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "current_total_score": scores["total"],
                "potential_total_score": min(100, scores["total"] + total_expected),
                "total_improvement": total_expected,
                "recommendations_count": len(recommendations),
                "recommendations": recommendations,
                "summary": (
                    f"共识别 {len(recommendations)} 项改进点，"
                    f"预计可将 ESG 总分从 {scores['total']} 提升至 {min(100, scores['total'] + total_expected)} 分。"
                ) if recommendations else "当前 ESG 表现已达优秀水平，暂无重大改进需求。",
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ESG 改进建议生成失败: {e}")
        return {"status": "error", "message": "ESG 改进建议生成失败，请稍后重试"}
