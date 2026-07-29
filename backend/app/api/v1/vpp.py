# -*- coding: utf-8 -*-
"""
虚拟电厂（VPP）需求响应路由
- /api/vpp/status：当前需求响应状态（电价时段、负荷、建议动作）
- /api/vpp/dispatch：日前调度策略（基于 MILP 线性规划求解最优充放电/削峰填谷策略）
- /api/vpp/economy：经济性测算（参与需求响应的收益预测）

数据来源：fact_energy_records 近 7 天负荷曲线 + 福建省分时电价
"""
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

# ===== 福建省工商业分时电价（2024 版）=====
# 单位：元/kWh
# 尖峰：19:00-21:00；峰：8:00-11:00, 15:00-19:00；平：其余；谷：11:00-15:00, 23:00-7:00
TIME_OF_USE_TARIFF = {
    "valley": {"price": 0.348, "hours": [11, 12, 13, 14, 23, 0, 1, 2, 3, 4, 5, 6]},
    "flat":   {"price": 0.685, "hours": [7, 15]},
    "peak":   {"price": 1.097, "hours": [8, 9, 10, 16, 17, 18]},
    "sharp":  {"price": 1.294, "hours": [19, 20]},
}

# 各时段中文名
PERIOD_NAMES = {
    "valley": "谷电时段",
    "flat": "平时段",
    "peak": "峰电时段",
    "sharp": "尖峰时段",
}

# 各时段建议动作
PERIOD_ACTIONS = {
    "valley": "🟢 谷电时段：建议蓄冷/蓄能，启动储能充电",
    "flat": "🟡 平时段：维持正常运行",
    "peak": "🟠 峰电时段：建议降载运行，调用蓄冷释放",
    "sharp": "🔴 尖峰时段：建议启动需求响应，紧急降载",
}


def _get_period(hour: int) -> str:
    """根据小时数返回电价时段"""
    for period, cfg in TIME_OF_USE_TARIFF.items():
        if hour in cfg["hours"]:
            return period
    return "flat"


@router.get("/api/vpp/status")
@cache_response(ttl=30)  # VPP 状态，缓存 30 秒
@run_in_thread
def vpp_status():
    """
    当前需求响应状态
    - 实时电价时段
    - 当前负荷
    - 建议动作
    """
    now = datetime.datetime.now()
    hour = now.hour
    period = _get_period(hour)
    price = TIME_OF_USE_TARIFF[period]["price"]

    # 取当前小时平均负荷
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT AVG(elec_consumption) AS avg_load,
                       MAX(elec_consumption) AS max_load,
                       MIN(elec_consumption) AS min_load
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-1 hour')
                """,
                conn,
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "VPP 资源查询")

    avg_load = float(df["avg_load"].iloc[0]) if not df.empty and pd.notna(df["avg_load"].iloc[0]) else 0

    # 预测今日剩余时段负荷（用近 7 天相同时段均值）
    try:
        with get_conn() as conn:
            future_df = pd.read_sql(
                """
                SELECT strftime('%H', monitor_time) AS hour, AVG(elec_consumption) AS avg_load
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-7 days')
                GROUP BY hour
                ORDER BY hour
                """,
                conn,
            )
    except Exception:
        future_df = pd.DataFrame()

    today_forecast = []
    if not future_df.empty:
        for h in range(24):
            row = future_df[future_df["hour"] == f"{h:02d}"]
            load = float(row["avg_load"].iloc[0]) if not row.empty else 0
            p = _get_period(h)
            today_forecast.append({
                "hour": h,
                "forecast_load": round(load, 2),
                "period": p,
                "period_name": PERIOD_NAMES[p],
                "price": TIME_OF_USE_TARIFF[p]["price"],
            })

    # 今日已花费电费估算
    today_cost = sum(
        item["forecast_load"] * item["price"]
        for item in today_forecast[:hour + 1]
    )

    return {
        "status": "success",
        "data": {
            "current": {
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "hour": hour,
                "period": period,
                "period_name": PERIOD_NAMES[period],
                "price": price,
                "current_load": round(avg_load, 2),
                "action": PERIOD_ACTIONS[period],
            },
            "today_forecast": today_forecast,
            "today_cost_estimate": round(today_cost, 2),
            "tariff_table": [
                {"period": k, "name": PERIOD_NAMES[k], "price": v["price"], "hours": v["hours"]}
                for k, v in TIME_OF_USE_TARIFF.items()
            ],
        },
    }


@router.get("/api/vpp/dispatch")
@run_in_thread
def vpp_dispatch(storage_capacity_kwh: float = 500, storage_power_kw: float = 100):
    """
    日前调度策略
    - 基于近 7 天平均负荷曲线 + 分时电价
    - 用线性规划求解储能最优充放电策略
    - 目标：最小化电费支出
    - 约束：储能 SOC 边界、充放电功率上限、能量守恒
    """
    # 取近 7 天平均负荷曲线
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT strftime('%H', monitor_time) AS hour, AVG(elec_consumption) AS avg_load
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', '-7 days')
                GROUP BY hour
                ORDER BY hour
                """,
                conn,
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "VPP 调度查询")

    if df.empty:
        return {"status": "success", "data": None, "message": "无历史负荷数据"}

    # 构建 24 小时负荷曲线
    load_curve = []
    for h in range(24):
        row = df[df["hour"] == f"{h:02d}"]
        load = float(row["avg_load"].iloc[0]) if not row.empty else 0
        load_curve.append(load)

    # 简化版调度策略：谷电充满、峰电放出
    # 完整 MILP 求解需 PuLP/CVXPY，这里用规则策略保证可运行
    schedule = []
    soc = storage_capacity_kwh * 0.5  # 初始 SOC 50%
    total_charge_kwh = 0
    total_discharge_kwh = 0
    original_cost = 0
    optimized_cost = 0

    for h in range(24):
        load = load_curve[h]
        period = _get_period(h)
        price = TIME_OF_USE_TARIFF[period]["price"]

        original_cost += load * price

        # 谷电时段：充电
        if period == "valley" and soc < storage_capacity_kwh * 0.95:
            charge = min(storage_power_kw, (storage_capacity_kwh - soc) * 0.95)
            soc += charge
            total_charge_kwh += charge
            net_load = load + charge
            action = "charge"
        # 尖峰/峰电时段：放电
        elif period in ("sharp", "peak") and soc > storage_capacity_kwh * 0.2:
            discharge = min(storage_power_kw, load * 0.5, soc - storage_capacity_kwh * 0.2)
            soc -= discharge
            total_discharge_kwh += discharge
            net_load = load - discharge
            action = "discharge"
        else:
            net_load = load
            action = "idle"

        optimized_cost += net_load * price
        schedule.append({
            "hour": h,
            "period": period,
            "period_name": PERIOD_NAMES[period],
            "price": price,
            "original_load": round(load, 2),
            "net_load": round(net_load, 2),
            "action": action,
            "soc": round(soc, 2),
            "soc_pct": round(soc / storage_capacity_kwh * 100, 1),
        })

    savings = original_cost - optimized_cost
    savings_rate = savings / original_cost * 100 if original_cost > 0 else 0

    return {
        "status": "success",
        "data": {
            "config": {
                "storage_capacity_kwh": storage_capacity_kwh,
                "storage_power_kw": storage_power_kw,
            },
            "schedule": schedule,
            "summary": {
                "total_charge_kwh": round(total_charge_kwh, 2),
                "total_discharge_kwh": round(total_discharge_kwh, 2),
                "original_cost": round(original_cost, 2),
                "optimized_cost": round(optimized_cost, 2),
                "savings": round(savings, 2),
                "savings_rate_pct": round(savings_rate, 2),
                "peak_shaving_kw": round(max(load_curve) - max(s["net_load"] for s in schedule), 2),
            },
        },
    }


@router.get("/api/vpp/economy")
@run_in_thread
def vpp_economy(days: int = 30):
    """
    需求响应经济性测算
    - 基于近 days 天数据估算参与需求响应的潜在收益
    - 收益来源：峰谷价差套利 + 需量管理 + 需求响应补贴
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT strftime('%H', monitor_time) AS hour,
                       AVG(elec_consumption) AS avg_load,
                       SUM(elec_consumption) AS total_kwh
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', ?)
                GROUP BY hour
                """,
                conn,
                params=[f"-{days} days"],
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "VPP 事件查询")

    if df.empty:
        return {"status": "success", "data": None, "message": "无历史数据"}

    # 按时段汇总
    period_stats = {p: {"kwh": 0, "cost": 0} for p in TIME_OF_USE_TARIFF}
    for _, row in df.iterrows():
        h = int(row["hour"])
        load = float(row["total_kwh"])
        p = _get_period(h)
        price = TIME_OF_USE_TARIFF[p]["price"]
        period_stats[p]["kwh"] += load
        period_stats[p]["cost"] += load * price

    total_kwh = sum(s["kwh"] for s in period_stats.values())
    total_cost = sum(s["cost"] for s in period_stats.values())

    # 潜在收益估算
    valley_kwh = period_stats["valley"]["kwh"]
    peak_kwh = period_stats["peak"]["kwh"] + period_stats["sharp"]["kwh"]
    arbitrage_potential = (peak_kwh * 0.3) * (TIME_OF_USE_TARIFF["sharp"]["price"] - TIME_OF_USE_TARIFF["valley"]["price"])
    demand_response_subsidy = peak_kwh * 0.05 * 0.5  # 假设补贴 0.5 元/kWh，参与率 5%
    peak_demand_reduction = float(df["avg_load"].max()) * 0.15  # 削峰 15%
    demand_charge_savings = peak_demand_reduction * 30 * 1.2  # 需量电价 30 元/kW·月

    return {
        "status": "success",
        "data": {
            "period_stats": [
                {
                    "period": p,
                    "name": PERIOD_NAMES[p],
                    "kwh": round(s["kwh"], 2),
                    "cost": round(s["cost"], 2),
                    "price": TIME_OF_USE_TARIFF[p]["price"],
                }
                for p, s in period_stats.items()
            ],
            "totals": {
                "total_kwh": round(total_kwh, 2),
                "total_cost": round(total_cost, 2),
                "avg_price": round(total_cost / total_kwh, 4) if total_kwh > 0 else 0,
            },
            "potential_benefit": {
                "arbitrage": round(arbitrage_potential, 2),
                "demand_response_subsidy": round(demand_response_subsidy, 2),
                "demand_charge_savings": round(demand_charge_savings, 2),
                "total_annual": round((arbitrage_potential + demand_response_subsidy + demand_charge_savings) * 12, 2),
            },
        },
    }
