# -*- coding: utf-8 -*-
"""
设备健康度评分 & RUL（剩余使用寿命）预测路由
- /api/rul/overview：全部设备健康度概览（按健康度分级统计）
- /api/rul/device/{device_id}：单设备详细健康度报告
- /api/rul/ranking：健康度排名（最差 Top 10 设备）

设计要点：
1. 仅对具有 nominal_cop 的设备（HVAC/精密空调/制冷/热水器）做评分
2. 健康度评分 = COP 衰减度(30%) + 运行稳定性(20%) + 负载率合理性(20%)
              + 故障频率(15%) + 温差异常度(15%)
3. RUL 预测：基于 COP 衰减趋势线性外推，当预测 COP 降到额定值 60% 时认为是寿命终点
4. loading_rate 字段在数据库中为空，按 elec_consumption / rated_power 推算
5. 全程异步（run_in_thread + asyncio.to_thread），不阻塞事件循环
"""
import math
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.response_cache import cache_response
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 健康度分级阈值 =====
HEALTH_GRADE = {
    "excellent": {"min": 80, "name": "优秀", "color": "#52c41a"},
    "good":      {"min": 60, "max": 80, "name": "良好", "color": "#1890ff"},
    "watch":     {"min": 40, "max": 60, "name": "关注", "color": "#faad14"},
    "warning":   {"min": 0,  "max": 40, "name": "预警", "color": "#ff4d4f"},
}

# 健康度各维度权重
WEIGHTS = {
    "cop_degradation": 0.30,   # COP 衰减度
    "stability":       0.20,   # 运行稳定性
    "loading_rate":    0.20,   # 负载率合理性
    "fault_freq":      0.15,   # 故障频率
    "delta_temp":      0.15,   # 温差异常度
}

# RUL 预测寿命终点判定：COP 衰减到额定值 60%
RUL_END_OF_LIFE_RATIO = 0.60


def _grade_of(score: float) -> str:
    """根据健康度分数返回分级 key"""
    if score > 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "watch"
    return "warning"


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


def _fetch_devices_with_cop() -> pd.DataFrame:
    """获取所有有 nominal_cop 的设备清单（HVAC/精密空调/制冷/热水器）"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT d.device_id, d.device_name, d.device_type, d.building_id,
                   d.rated_power, d.nominal_cop, d.installation_date,
                   b.building_name, b.building_type
            FROM dim_devices d
            LEFT JOIN dim_buildings b ON b.building_id = d.building_id
            WHERE d.nominal_cop IS NOT NULL AND d.nominal_cop > 0
            """,
            conn,
        )
    return df


def _fetch_device_metrics(device_id: str, days: int = 30) -> pd.DataFrame:
    """取单设备近 N 天的小时级运行记录"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT monitor_time, elec_consumption, cop, supply_temp, return_temp,
                   delta_temp, cooling_load, run_status, fault_code
            FROM fact_energy_records
            WHERE device_id = ? AND monitor_time >= datetime('now', 'localtime', ?)
            ORDER BY monitor_time ASC
            """,
            conn,
            params=[device_id, f"-{days} days"],
        )
    return df


def _fetch_device_fault_count(device_id: str, days: int = 30) -> int:
    """取单设备近 N 天的故障（fault_code 非空且非 NONE）次数"""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM fact_energy_records
            WHERE device_id = ? AND monitor_time >= datetime('now', 'localtime', ?)
              AND fault_code IS NOT NULL AND fault_code != '' AND fault_code != 'NONE'
            """,
            [device_id, f"-{days} days"],
        )
        row = cur.fetchone()
    return int(row["cnt"]) if row else 0


def _fetch_all_devices_recent_stats(days: int = 30) -> pd.DataFrame:
    """
    一次性聚合所有设备的近 N 天关键统计指标（避免 N 次 SQL）。
    返回字段：device_id, cop_mean, cop_std, cop_recent, delta_mean, delta_recent,
             fault_count, elec_mean, record_count, recent_7d_records
    """
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT
                device_id,
                AVG(CASE WHEN cop IS NOT NULL THEN cop END) AS cop_mean,
                -- 标准差需在 Python 端补算（SQLite 无 STDDEV）
                MAX(CASE WHEN cop IS NOT NULL THEN cop END) AS cop_max,
                MIN(CASE WHEN cop IS NOT NULL THEN cop END) AS cop_min,
                AVG(CASE WHEN delta_temp IS NOT NULL THEN delta_temp END) AS delta_mean,
                AVG(CASE WHEN elec_consumption IS NOT NULL THEN elec_consumption END) AS elec_mean,
                COUNT(*) AS record_count,
                SUM(CASE WHEN fault_code IS NOT NULL AND fault_code != '' AND fault_code != 'NONE' THEN 1 ELSE 0 END) AS fault_count
            FROM fact_energy_records
            WHERE monitor_time >= datetime('now', 'localtime', ?)
            GROUP BY device_id
            """,
            conn,
            params=[f"-{days} days"],
        )
    return df


def _fetch_recent_cop_per_device(days: int = 7) -> pd.DataFrame:
    """取所有设备近 N 天的 COP 序列（用于算稳定性 std 与近期均值）"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT device_id, monitor_time, cop, elec_consumption, delta_temp
            FROM fact_energy_records
            WHERE monitor_time >= datetime('now', 'localtime', ?)
              AND cop IS NOT NULL
            ORDER BY device_id, monitor_time ASC
            """,
            conn,
            params=[f"-{days} days"],
        )
    return df


def _fetch_cop_trend_by_month(device_id: str) -> pd.DataFrame:
    """取设备近 6 个月的 COP 月度均值，用于 RUL 衰减趋势外推"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT strftime('%Y-%m', monitor_time) AS month,
                   AVG(cop) AS cop_avg,
                   COUNT(*) AS cnt
            FROM fact_energy_records
            WHERE device_id = ? AND cop IS NOT NULL
              AND monitor_time >= datetime('now', 'localtime', '-183 days')
            GROUP BY month
            ORDER BY month
            """,
            conn,
            params=[device_id],
        )
    return df


def _score_cop_degradation(current_cop: Optional[float],
                           hist_cop: Optional[float],
                           nominal_cop: float) -> float:
    """
    COP 衰减度评分（满分 100）
    - 衰减率 = (nominal - current) / nominal，0% 衰减=100 分，50% 衰减=0 分
    - 用历史均值与额定值取较小者作为基准（防止历史数据本身偏低时误判）
    """
    if current_cop is None or nominal_cop is None or nominal_cop <= 0:
        return 50.0  # 数据缺失时给中位分
    baseline = min(hist_cop or nominal_cop, nominal_cop)
    if baseline <= 0:
        return 50.0
    degradation = max(0.0, (baseline - current_cop) / baseline)
    # 衰减 0% → 100 分；衰减 50% → 0 分
    score = 100 * (1 - degradation * 2)
    return max(0.0, min(100.0, score))


def _score_stability(cop_std: Optional[float], nominal_cop: float) -> float:
    """
    运行稳定性评分（满分 100）
    - 用 COP 标准差归一化到额定 COP，越小越稳定
    - cv = std / nominal，cv=0 → 100 分，cv>=0.2 → 0 分
    """
    if cop_std is None or nominal_cop is None or nominal_cop <= 0:
        return 50.0
    cv = cop_std / nominal_cop
    score = 100 * (1 - cv / 0.2)
    return max(0.0, min(100.0, score))


def _score_loading_rate(loading_rate: Optional[float]) -> float:
    """
    负载率合理性评分（满分 100）
    - 40-90% 区间为健康区间 = 100 分
    - 低于 40% 或高于 90% 线性衰减
    """
    if loading_rate is None:
        return 50.0
    if 40 <= loading_rate <= 90:
        return 100.0
    if loading_rate < 40:
        # 0% → 40 分，40% → 100 分
        return 40 + (loading_rate / 40) * 60
    # 90% → 100 分，120%+ → 40 分
    if loading_rate >= 120:
        return 40.0
    return 100 - (loading_rate - 90) / 30 * 60


def _score_fault_freq(fault_count: int) -> float:
    """
    故障频率评分（满分 100）
    - 0 次 = 100 分
    - 每 5 次扣 20 分，30 次以上 = 0 分
    """
    if fault_count <= 0:
        return 100.0
    if fault_count >= 30:
        return 0.0
    return 100 - (fault_count / 30) * 100


def _score_delta_temp(delta_current: Optional[float],
                      delta_hist: Optional[float]) -> float:
    """
    温差异常度评分（满分 100）
    - 偏离历史均值越多分越低
    - 偏离 0℃ → 100 分；偏离 5℃ → 0 分
    """
    if delta_current is None or delta_hist is None:
        return 50.0
    deviation = abs(delta_current - delta_hist)
    score = 100 * (1 - deviation / 5.0)
    return max(0.0, min(100.0, score))


def _compute_health_score(metrics: dict) -> dict:
    """
    根据多维指标计算健康度总分
    metrics 字段：current_cop, hist_cop, nominal_cop, cop_std,
                 loading_rate, fault_count, delta_current, delta_hist
    返回：{total, dimensions: {key: {score, weight, contribution}}}
    """
    dims = {
        "cop_degradation": _score_cop_degradation(
            metrics.get("current_cop"), metrics.get("hist_cop"), metrics.get("nominal_cop") or 0
        ),
        "stability": _score_stability(
            metrics.get("cop_std"), metrics.get("nominal_cop") or 0
        ),
        "loading_rate": _score_loading_rate(metrics.get("loading_rate")),
        "fault_freq": _score_fault_freq(metrics.get("fault_count") or 0),
        "delta_temp": _score_delta_temp(
            metrics.get("delta_current"), metrics.get("delta_hist")
        ),
    }
    total = sum(dims[k] * WEIGHTS[k] for k in dims)
    return {
        "total": round(total, 2),
        "dimensions": {
            k: {
                "score": round(v, 2),
                "weight": WEIGHTS[k],
                "contribution": round(v * WEIGHTS[k], 2),
            }
            for k, v in dims.items()
        },
    }


def _predict_rul(monthly_trend: pd.DataFrame, nominal_cop: float) -> dict:
    """
    基于 COP 月度趋势线性外推 RUL
    - 取最近 6 个月的 COP 月度均值做线性回归
    - 当预测 COP 降到 nominal_cop * 60% 时为寿命终点
    - 返回：{rul_days, slope_per_month, end_of_life_date, current_cop, threshold_cop, confidence}
    """
    threshold = nominal_cop * RUL_END_OF_LIFE_RATIO
    if monthly_trend.empty or len(monthly_trend) < 2:
        return {
            "rul_days": None,
            "slope_per_month": None,
            "end_of_life_date": None,
            "current_cop": None,
            "threshold_cop": round(threshold, 2),
            "confidence": "insufficient_data",
        }

    x = list(range(len(monthly_trend)))
    y = monthly_trend["cop_avg"].astype(float).tolist()
    n = len(x)
    # 简单线性回归：y = a + b*x
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den = sum((xi - mean_x) ** 2 for xi in x)
    slope = num / den if den != 0 else 0
    intercept = mean_y - slope * mean_x
    current_cop = y[-1]

    if slope >= 0:
        # COP 在改善或不变 → 无明确寿命终点
        return {
            "rul_days": None,
            "slope_per_month": round(slope, 4),
            "end_of_life_date": None,
            "current_cop": round(current_cop, 3),
            "threshold_cop": round(threshold, 2),
            "confidence": "no_degradation",
        }

    # 外推到 threshold 的月数
    months_to_eol = (threshold - intercept) / slope
    if months_to_eol <= 0:
        # 已低于阈值
        return {
            "rul_days": 0,
            "slope_per_month": round(slope, 4),
            "end_of_life_date": datetime.date.today().isoformat(),
            "current_cop": round(current_cop, 3),
            "threshold_cop": round(threshold, 2),
            "confidence": "below_threshold",
        }

    rul_days = int(months_to_eol * 30)
    eol_date = datetime.date.today() + datetime.timedelta(days=rul_days)
    # 置信度：基于样本数与斜率强度
    if n >= 5 and abs(slope) > 0.05:
        confidence = "high"
    elif n >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "rul_days": rul_days,
        "slope_per_month": round(slope, 4),
        "end_of_life_date": eol_date.isoformat(),
        "current_cop": round(current_cop, 3),
        "threshold_cop": round(threshold, 2),
        "confidence": confidence,
    }


def _generate_maintenance_suggestion(score: float, dims: dict, rul: dict) -> str:
    """根据健康度评分和 RUL 生成维保建议"""
    if score < 40:
        base = "⚠️ 设备健康度严重偏低，建议立即停机检修"
    elif score < 60:
        base = "🔴 设备处于关注区，建议两周内安排深度维保"
    elif score < 80:
        base = "🟡 设备运行尚可，建议加强巡检频次"
    else:
        base = "🟢 设备运行健康，按计划保养即可"

    # 找出扣分最严重的维度
    worst = min(dims.items(), key=lambda kv: kv[1]["score"])
    worst_name_map = {
        "cop_degradation": "COP 衰减",
        "stability": "运行稳定性",
        "loading_rate": "负载率合理性",
        "fault_freq": "故障频率",
        "delta_temp": "温差异常",
    }
    detail = ""
    if worst[1]["score"] < 60:
        wn = worst_name_map.get(worst[0], worst[0])
        detail = f"；主要扣分项：{wn}（{worst[1]['score']:.0f} 分）"

    rul_hint = ""
    if rul.get("rul_days") is not None:
        if rul["rul_days"] <= 30:
            rul_hint = f"；RUL 仅剩 {rul['rul_days']} 天，建议紧急制定更换计划"
        elif rul["rul_days"] <= 180:
            rul_hint = f"；RUL 约 {rul['rul_days']} 天，建议提前纳入年度技改计划"
    elif rul.get("confidence") == "below_threshold":
        rul_hint = "；COP 已低于寿命阈值，建议立即评估更换"

    return base + detail + rul_hint


@router.get("/api/rul/overview")
@cache_response(ttl=120)  # RUL 计算耗时，缓存 2 分钟
@run_in_thread
def rul_overview():
    """
    全部设备健康度概览
    - 按健康度分级统计（优秀/良好/关注/预警）
    - 列出每台设备的健康度评分与分级
    """
    try:
        devices_df = _fetch_devices_with_cop()
        if devices_df.empty:
            return {"status": "success", "data": None, "message": "无可评分设备"}

        # 一次性聚合所有设备的统计指标
        stats_df = _fetch_all_devices_recent_stats(days=30)
        recent_df = _fetch_recent_cop_per_device(days=7)

        # 计算每台设备近 7 天 COP 标准差与近期均值
        stability_map = {}
        recent_cop_map = {}
        recent_delta_map = {}
        if not recent_df.empty:
            for dev_id, group in recent_df.groupby("device_id"):
                cop_series = group["cop"].dropna()
                delta_series = group["delta_temp"].dropna()
                if len(cop_series) > 1:
                    stability_map[dev_id] = float(cop_series.std())
                if len(cop_series) > 0:
                    recent_cop_map[dev_id] = float(cop_series.iloc[-1])  # 最近一条
                if len(delta_series) > 0:
                    recent_delta_map[dev_id] = float(delta_series.iloc[-1])

        # 合并设备信息与统计指标
        merged = devices_df.merge(stats_df, on="device_id", how="left")

        devices = []
        grade_counts = {"excellent": 0, "good": 0, "watch": 0, "warning": 0}

        for _, row in merged.iterrows():
            dev_id = row["device_id"]
            nominal_cop = float(row["nominal_cop"])
            rated_power = float(row["rated_power"]) if pd.notna(row["rated_power"]) else None

            # 推算负载率：elec_consumption / rated_power * 100（小时级 kWh 与 kW 数值上可对应）
            elec_mean = _safe_float(row.get("elec_mean"), 3)
            if rated_power and rated_power > 0 and elec_mean is not None:
                loading_rate = (elec_mean / rated_power) * 100
            else:
                loading_rate = None

            metrics = {
                "current_cop": recent_cop_map.get(dev_id),
                "hist_cop": _safe_float(row.get("cop_mean"), 3),
                "nominal_cop": nominal_cop,
                "cop_std": stability_map.get(dev_id),
                "loading_rate": loading_rate,
                "fault_count": int(row.get("fault_count") or 0),
                "delta_current": recent_delta_map.get(dev_id),
                "delta_hist": _safe_float(row.get("delta_mean"), 3),
            }

            health = _compute_health_score(metrics)
            score = health["total"]
            grade_key = _grade_of(score)
            grade_counts[grade_key] += 1

            devices.append({
                "device_id": dev_id,
                "device_name": str(row["device_name"]),
                "device_type": str(row["device_type"]),
                "building_name": str(row.get("building_name") or ""),
                "health_score": score,
                "grade": grade_key,
                "grade_name": HEALTH_GRADE[grade_key]["name"],
                "color": HEALTH_GRADE[grade_key]["color"],
                "nominal_cop": round(nominal_cop, 2),
                "current_cop": metrics["current_cop"],
                "fault_count_30d": metrics["fault_count"],
            })

        # 按健康度升序（最差的在前）
        devices.sort(key=lambda d: d["health_score"])

        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_devices": len(devices),
                    "grade_counts": grade_counts,
                    "grade_distribution_pct": {
                        k: round(grade_counts[k] / max(1, len(devices)) * 100, 2)
                        for k in grade_counts
                    },
                    "avg_score": round(sum(d["health_score"] for d in devices) / max(1, len(devices)), 2),
                    "worst_score": min(d["health_score"] for d in devices) if devices else None,
                    "best_score": max(d["health_score"] for d in devices) if devices else None,
                },
                "grades": [
                    {"key": k, "name": v["name"], "color": v["color"],
                     "range": f">{v['min']}" if k == "excellent" else f"{v.get('min',0)}-{v.get('max',100)}",
                     "count": grade_counts[k]}
                    for k, v in HEALTH_GRADE.items()
                ],
                "devices": devices,
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "RUL 预测查询")


@router.get("/api/rul/device/{device_id}")
@run_in_thread
def rul_device_detail(device_id: str):
    """
    单设备详细健康度报告
    - 健康度趋势（按天）
    - 关键指标衰减曲线（COP 月度趋势）
    - RUL 预测天数
    - 维保建议
    """
    try:
        # 设备元信息
        with get_conn() as conn:
            dev_df = pd.read_sql(
                """
                SELECT d.*, b.building_name, b.building_type
                FROM dim_devices d
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                WHERE d.device_id = ?
                """,
                conn,
                params=[device_id],
            )
        if dev_df.empty:
            return {"status": "error", "code": "NOT_FOUND",
                    "message": f"设备 {device_id} 不存在"}

        dev = dev_df.iloc[0]
        nominal_cop = float(dev["nominal_cop"]) if pd.notna(dev["nominal_cop"]) else 0
        rated_power = float(dev["rated_power"]) if pd.notna(dev["rated_power"]) else 0

        # 取近 30 天记录
        df = _fetch_device_metrics(device_id, days=30)
        if df.empty:
            return {"status": "success", "data": None,
                    "message": "该设备近 30 天无运行数据"}

        # 数值化
        for col in ["elec_consumption", "cop", "supply_temp", "return_temp",
                    "delta_temp", "cooling_load"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 全局统计
        cop_series = df["cop"].dropna()
        delta_series = df["delta_temp"].dropna()
        hist_cop = float(cop_series.mean()) if not cop_series.empty else None
        cop_std_7d = None
        recent_7d = df.tail(24 * 7)  # 最近 7 天小时级
        if not recent_7d.empty:
            cop_std_7d = float(recent_7d["cop"].dropna().std()) if recent_7d["cop"].notna().any() else None

        current_cop = float(cop_series.iloc[-1]) if not cop_series.empty else None
        current_delta = float(delta_series.iloc[-1]) if not delta_series.empty else None
        hist_delta = float(delta_series.mean()) if not delta_series.empty else None

        # 推算负载率
        loading_rate = None
        if rated_power > 0 and pd.notna(df["elec_consumption"]).any():
            recent_elec = df["elec_consumption"].dropna().tail(24)
            if not recent_elec.empty:
                loading_rate = float(recent_elec.mean() / rated_power * 100)

        # 故障次数
        fault_count = _fetch_device_fault_count(device_id, days=30)

        # 计算健康度
        metrics = {
            "current_cop": current_cop,
            "hist_cop": hist_cop,
            "nominal_cop": nominal_cop,
            "cop_std": cop_std_7d,
            "loading_rate": loading_rate,
            "fault_count": fault_count,
            "delta_current": current_delta,
            "delta_hist": hist_delta,
        }
        health = _compute_health_score(metrics)

        # 健康度按天趋势（用每日平均 COP 折算简化分数）
        df["day"] = pd.to_datetime(df["monitor_time"]).dt.strftime("%Y-%m-%d")
        daily = df.groupby("day").agg(
            cop_avg=("cop", "mean"),
            delta_avg=("delta_temp", "mean"),
            elec_avg=("elec_consumption", "mean"),
            fault_cnt=("fault_code", lambda s: ((s.notna()) & (s != "") & (s != "NONE")).sum()),
        ).reset_index()

        daily_trend = []
        for _, r in daily.iterrows():
            day_loading = float(r["elec_avg"] / rated_power * 100) if rated_power > 0 and pd.notna(r["elec_avg"]) else None
            day_metrics = {
                "current_cop": float(r["cop_avg"]) if pd.notna(r["cop_avg"]) else None,
                "hist_cop": hist_cop,
                "nominal_cop": nominal_cop,
                "cop_std": cop_std_7d,
                "loading_rate": day_loading,
                "fault_count": int(r["fault_cnt"]),
                "delta_current": float(r["delta_avg"]) if pd.notna(r["delta_avg"]) else None,
                "delta_hist": hist_delta,
            }
            day_health = _compute_health_score(day_metrics)
            daily_trend.append({
                "day": str(r["day"]),
                "health_score": day_health["total"],
                "cop": _safe_float(r["cop_avg"], 3),
                "delta_temp": _safe_float(r["delta_avg"], 2),
                "loading_rate": _safe_float(day_loading, 1),
                "fault_count": int(r["fault_cnt"]),
            })

        # COP 月度衰减曲线
        monthly_df = _fetch_cop_trend_by_month(device_id)
        cop_trend = [
            {
                "month": str(r["month"]),
                "cop_avg": _safe_float(r["cop_avg"], 3),
                "samples": int(r["cnt"]),
            }
            for _, r in monthly_df.iterrows()
        ]

        # RUL 预测
        rul = _predict_rul(monthly_df, nominal_cop)

        # 维保建议
        suggestion = _generate_maintenance_suggestion(
            health["total"], health["dimensions"], rul
        )

        # 最近故障明细（最多 10 条）
        recent_faults = []
        fault_df = df[(df["fault_code"].notna()) & (df["fault_code"] != "") & (df["fault_code"] != "NONE")]
        for _, fr in fault_df.tail(10).iterrows():
            recent_faults.append({
                "time": str(fr["monitor_time"]),
                "fault_code": str(fr["fault_code"]),
                "run_status": str(fr["run_status"]),
            })

        grade_key = _grade_of(health["total"])

        return {
            "status": "success",
            "data": {
                "device": {
                    "device_id": device_id,
                    "device_name": str(dev["device_name"]),
                    "device_type": str(dev["device_type"]),
                    "building_name": str(dev.get("building_name") or ""),
                    "rated_power": _safe_float(rated_power, 2),
                    "nominal_cop": _safe_float(nominal_cop, 2),
                    "installation_date": str(dev.get("installation_date") or ""),
                },
                "health": {
                    "score": health["total"],
                    "grade": grade_key,
                    "grade_name": HEALTH_GRADE[grade_key]["name"],
                    "color": HEALTH_GRADE[grade_key]["color"],
                    "dimensions": health["dimensions"],
                },
                "key_metrics": {
                    "current_cop": _safe_float(current_cop, 3),
                    "hist_cop": _safe_float(hist_cop, 3),
                    "nominal_cop": _safe_float(nominal_cop, 3),
                    "cop_std_7d": _safe_float(cop_std_7d, 3),
                    "loading_rate": _safe_float(loading_rate, 1),
                    "fault_count_30d": fault_count,
                    "current_delta_temp": _safe_float(current_delta, 2),
                    "hist_delta_temp": _safe_float(hist_delta, 2),
                },
                "rul": rul,
                "trend": {
                    "daily_health": daily_trend,
                    "cop_monthly_trend": cop_trend,
                },
                "recent_faults": recent_faults,
                "suggestion": suggestion,
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "RUL 详情查询")


@router.get("/api/rul/ranking")
@cache_response(ttl=120)  # RUL 排名，缓存 2 分钟
@run_in_thread
def rul_ranking(top: int = 10):
    """
    健康度排名（最差 Top N 设备）
    """
    try:
        devices_df = _fetch_devices_with_cop()
        if devices_df.empty:
            return {"status": "success", "data": [], "message": "无可评分设备"}

        stats_df = _fetch_all_devices_recent_stats(days=30)
        recent_df = _fetch_recent_cop_per_device(days=7)

        stability_map = {}
        recent_cop_map = {}
        recent_delta_map = {}
        if not recent_df.empty:
            for dev_id, group in recent_df.groupby("device_id"):
                cop_series = group["cop"].dropna()
                delta_series = group["delta_temp"].dropna()
                if len(cop_series) > 1:
                    stability_map[dev_id] = float(cop_series.std())
                if not cop_series.empty:
                    recent_cop_map[dev_id] = float(cop_series.iloc[-1])
                if not delta_series.empty:
                    recent_delta_map[dev_id] = float(delta_series.iloc[-1])

        merged = devices_df.merge(stats_df, on="device_id", how="left")

        ranking = []
        for _, row in merged.iterrows():
            dev_id = row["device_id"]
            nominal_cop = float(row["nominal_cop"])
            rated_power = float(row["rated_power"]) if pd.notna(row["rated_power"]) else None
            elec_mean = _safe_float(row.get("elec_mean"), 3)
            if rated_power and rated_power > 0 and elec_mean is not None:
                loading_rate = (elec_mean / rated_power) * 100
            else:
                loading_rate = None

            metrics = {
                "current_cop": recent_cop_map.get(dev_id),
                "hist_cop": _safe_float(row.get("cop_mean"), 3),
                "nominal_cop": nominal_cop,
                "cop_std": stability_map.get(dev_id),
                "loading_rate": loading_rate,
                "fault_count": int(row.get("fault_count") or 0),
                "delta_current": recent_delta_map.get(dev_id),
                "delta_hist": _safe_float(row.get("delta_mean"), 3),
            }
            health = _compute_health_score(metrics)
            grade_key = _grade_of(health["total"])
            ranking.append({
                "rank": 0,  # 后续填充
                "device_id": dev_id,
                "device_name": str(row["device_name"]),
                "device_type": str(row["device_type"]),
                "building_name": str(row.get("building_name") or ""),
                "health_score": health["total"],
                "grade": grade_key,
                "grade_name": HEALTH_GRADE[grade_key]["name"],
                "color": HEALTH_GRADE[grade_key]["color"],
                "current_cop": metrics["current_cop"],
                "nominal_cop": round(nominal_cop, 2),
                "fault_count_30d": metrics["fault_count"],
                "worst_dimension": min(
                    health["dimensions"].items(),
                    key=lambda kv: kv[1]["score"]
                )[0],
            })

        # 升序排列（最差在前），取 Top N
        ranking.sort(key=lambda d: d["health_score"])
        ranking = ranking[:top]
        for i, item in enumerate(ranking):
            item["rank"] = i + 1

        return {
            "status": "success",
            "data": ranking,
            "total": len(ranking),
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "RUL 分析查询")
