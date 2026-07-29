# -*- coding: utf-8 -*-
"""
多能耦合优化引擎路由
- /api/multi_energy/overview：多能系统概览（当前各能源流量、耦合效率）
- /api/multi_energy/optimize：最优调度策略（24h 逐时段电/冷/热调度方案）
- /api/multi_energy/comparison：优化前后对比（能耗、成本、碳排放）

能源耦合模型：
1. 电网购电 → 冷水机组制冷（COP）→ 冷负荷
2. 电网购电 → 锅炉制热（效率 0.95）→ 热负荷
3. 光伏发电 → 抵消购电
4. 储能充放电 → 削峰填谷

优化目标：最小化总成本 = 电费 + 运维成本 - 售电收入
约束：
- 冷热负荷平衡
- 设备容量上限（dim_devices.rated_power）
- 储能 SOC 范围 20%-80%
"""
import math
import logging
import datetime
import asyncio
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request

from app.core.database import get_conn, DBUnavailableError
from app.core.response_cache import cache_response
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 多能系统配置 =====
SYSTEM_CONFIG = {
    "chiller_cop": 4.5,           # 冷水机组平均 COP
    "boiler_efficiency": 0.95,    # 电锅炉效率
    "pv_capacity_kw": 100,        # 光伏装机容量
    "pv_efficiency": 0.85,        # 光伏系统效率
    "battery_capacity_kwh": 500,  # 储能容量
    "battery_power_kw": 100,      # 储能充放电功率
    "battery_initial_soc": 0.5,   # 初始 SOC
    "battery_soc_min": 0.20,      # SOC 下限
    "battery_soc_max": 0.80,      # SOC 上限
    "grid_export_limit_kw": 80,   # 售电功率上限
    "om_cost_per_kwh": 0.02,      # 运维成本（元/kWh）
    "carbon_factor": 0.5366,      # 电网碳排放因子（华东电网, tCO2/MWh）
}

# ===== 分时电价（峰谷平）=====
# 峰：10:00-15:00, 18:00-21:00 = 1.25 元/kWh
# 谷：23:00-7:00 = 0.35 元/kWh
# 平：其余时段 = 0.75 元/kWh
PEAK_HOURS = {10, 11, 12, 13, 14, 18, 19, 20}
VALLEY_HOURS = {23, 0, 1, 2, 3, 4, 5, 6, 7}
TARIFF = {
    "peak":   {"price": 1.25, "name": "峰电"},
    "valley": {"price": 0.35, "name": "谷电"},
    "flat":   {"price": 0.75, "name": "平电"},
}


def _safe_float(v, ndigits=2):
    """安全转换为 float"""
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, ndigits)
    except (TypeError, ValueError):
        return None


def _get_period(hour: int) -> str:
    """根据小时数返回电价时段"""
    if hour in PEAK_HOURS:
        return "peak"
    if hour in VALLEY_HOURS:
        return "valley"
    return "flat"


def _fetch_hourly_load_profile() -> list:
    """
    取近 24h 平均负荷曲线（按小时聚合，所有建筑总和）
    返回长度 24 的列表（kW）
    """
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
    load_curve = []
    for h in range(24):
        row = df[df["hour"] == f"{h:02d}"]
        load = float(row["avg_load"].iloc[0]) if not row.empty and pd.notna(row["avg_load"].iloc[0]) else 0
        load_curve.append(load)
    return load_curve


def _fetch_cooling_heat_load() -> dict:
    """
    取近 24h 平均冷负荷与热负荷
    - 冷负荷：fact_energy_records.cooling_load 平均值
    - 热负荷：fact_energy_records.heat_gain_kw 平均值（含负号代表散热）
    """
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT strftime('%H', monitor_time) AS hour,
                   AVG(cooling_load) AS avg_cooling,
                   AVG(heat_gain_kw) AS avg_heat
            FROM fact_energy_records
            WHERE monitor_time >= datetime('now', 'localtime', '-7 days')
            GROUP BY hour
            ORDER BY hour
            """,
            conn,
        )
    cooling_curve = []
    heat_curve = []
    for h in range(24):
        row = df[df["hour"] == f"{h:02d}"]
        if not row.empty:
            cool = float(row["avg_cooling"].iloc[0]) if pd.notna(row["avg_cooling"].iloc[0]) else 0
            heat = float(row["avg_heat"].iloc[0]) if pd.notna(row["avg_heat"].iloc[0]) else 0
        else:
            cool = 0
            heat = 0
        cooling_curve.append(max(0, cool))
        heat_curve.append(max(0, heat))
    return {"cooling": cooling_curve, "heat": heat_curve}


def _fetch_pv_generation_24h() -> list:
    """
    从 fact_new_energy 取最近 24h 光伏出力
    若数据库无数据，回退到基于天文物理模型的估算
    """
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT strftime('%H', timestamp) AS hour, AVG(pv_generation_kw) AS pv
            FROM fact_new_energy
            WHERE timestamp >= datetime('now', 'localtime', '-7 days')
            GROUP BY hour
            ORDER BY hour
            """,
            conn,
        )

    pv_curve = []
    if not df.empty and df["pv"].notna().any():
        for h in range(24):
            row = df[df["hour"] == f"{h:02d}"]
            pv = float(row["pv"].iloc[0]) if not row.empty and pd.notna(row["pv"].iloc[0]) else 0
            pv_curve.append(max(0, pv))
        if any(v > 0 for v in pv_curve):
            return pv_curve

    # 回退：基于太阳高度角的物理模型
    return _build_physics_pv_curve()


def _build_physics_pv_curve() -> list:
    """
    基于天文物理模型生成 24h 光伏出力曲线（无外部 API 依赖）
    - 福州纬度约 26°N
    - 峰值出力约 12:00，正弦曲线分布
    """
    # 福州纬度
    lat = 26.02
    now = datetime.datetime.now()
    day_of_year = now.timetuple().tm_yday
    declination = 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))
    lat_rad = math.radians(lat)
    decl_rad = math.radians(declination)

    pv_curve = []
    for h in range(24):
        hour_angle = math.radians(15 * (h - 12))
        sin_alt = (math.sin(lat_rad) * math.sin(decl_rad) +
                   math.cos(lat_rad) * math.cos(decl_rad) * math.cos(hour_angle))
        alt = math.degrees(math.asin(max(-1, min(1, sin_alt))))
        if alt > 0:
            radiation = 1000 * math.sin(math.radians(alt)) * 0.75
            power = SYSTEM_CONFIG["pv_capacity_kw"] * (radiation / 1000) * SYSTEM_CONFIG["pv_efficiency"]
        else:
            power = 0
        pv_curve.append(round(power, 2))
    return pv_curve


def _fetch_devices_total_capacity() -> dict:
    """取设备总装机容量（用于约束）"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT device_type, SUM(rated_power) AS total_power, COUNT(*) AS cnt
            FROM dim_devices
            WHERE rated_power IS NOT NULL AND rated_power > 0
            GROUP BY device_type
            """,
            conn,
        )
    hvac_power = 0
    total_power = 0
    for _, r in df.iterrows():
        if r["device_type"] in ("HVAC", "PRECISION_AC"):
            hvac_power += float(r["total_power"])
        total_power += float(r["total_power"])
    return {
        "hvac_power_kw": _safe_float(hvac_power, 2),
        "total_power_kw": _safe_float(total_power, 2),
    }


def _fetch_current_load() -> dict:
    """取当前小时（最近 1h）负荷、冷量、热量"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT AVG(elec_consumption) AS avg_elec,
                   AVG(cooling_load) AS avg_cooling,
                   AVG(heat_gain_kw) AS avg_heat,
                   AVG(cop) AS avg_cop
            FROM fact_energy_records
            WHERE monitor_time >= datetime('now', 'localtime', '-1 hour')
            """,
            conn,
        )
    if df.empty:
        return {"elec": 0, "cooling": 0, "heat": 0, "cop": SYSTEM_CONFIG["chiller_cop"]}
    row = df.iloc[0]
    return {
        "elec": _safe_float(row["avg_elec"], 2) or 0,
        "cooling": _safe_float(row["avg_cooling"], 2) or 0,
        "heat": _safe_float(row["avg_heat"], 2) or 0,
        "cop": _safe_float(row["avg_cop"], 2) or SYSTEM_CONFIG["chiller_cop"],
    }


def _fetch_pv_current() -> float:
    """取当前光伏出力"""
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT AVG(pv_generation_kw) AS pv
            FROM fact_new_energy
            WHERE timestamp >= datetime('now', 'localtime', '-1 hour')
            """,
            conn,
        )
    if not df.empty and pd.notna(df["pv"].iloc[0]):
        return float(df["pv"].iloc[0])
    # 回退到物理模型当前小时
    hour = datetime.datetime.now().hour
    return _build_physics_pv_curve()[hour]


def _optimize_schedule(load_curve, cooling_curve, heat_curve, pv_curve, config):
    """
    基于峰谷电价与光伏富余的储能调度优化
    - 白天（光伏富余）：优先用光伏充电（免费电力）
    - 峰电时段：储能放电抵消电网购电
    - 谷电时段：仅在光伏不足且后续峰电有需求时，从电网补电
    - 保证 SOC 日终回到初始值附近，避免"免费累积"造成对比失真
    返回：24h 逐时段调度方案
    """
    schedule = []
    soc = config["battery_initial_soc"] * config["battery_capacity_kwh"]
    soc_init = soc
    soc_min = config["battery_soc_min"] * config["battery_capacity_kwh"]
    soc_max = config["battery_soc_max"] * config["battery_capacity_kwh"]
    power_limit = config["battery_power_kw"]

    # 预估：白天光伏总富余 + 峰电时段总缺口（用于决策是否需要在谷电补电）
    daily_pv_surplus = 0.0
    daily_peak_deficit = 0.0
    for h in range(24):
        net = pv_curve[h] - load_curve[h]
        if net > 0:
            daily_pv_surplus += net
        else:
            if _get_period(h) in ("peak", "flat"):
                daily_peak_deficit += -net

    # 决策：若白天光伏富余 >= 储能容量，则不需要谷电补电
    need_valley_charge = daily_pv_surplus < (soc_max - soc) * 0.5 and daily_peak_deficit > 0

    total_grid_kwh = 0
    total_pv_kwh = 0
    total_battery_charge = 0
    total_battery_discharge = 0
    total_cost = 0
    total_om_cost = 0
    total_carbon_t = 0

    for h in range(24):
        load = load_curve[h]
        cool = cooling_curve[h]
        heat = heat_curve[h]
        pv = pv_curve[h]
        period = _get_period(h)
        price = TARIFF[period]["price"]

        # 1) 光伏优先供给负荷
        pv_to_load = min(pv, load)
        pv_surplus = max(0, pv - load)
        deficit = max(0, load - pv_to_load)  # 光伏不足的缺口

        battery_power = 0.0
        action = "idle"
        charge_from_grid = 0.0

        # 2) 充电策略：优先光伏富余充电（任何时段）；谷电补电仅当 need_valley_charge=True
        if pv_surplus > 0 and soc < soc_max:
            # 光伏富余 → 储能充电
            charge = min(pv_surplus, power_limit, (soc_max - soc))
            soc += charge
            battery_power = -charge
            total_battery_charge += charge
            action = "charge_pv"
        elif (period == "valley" and need_valley_charge and soc < soc_max
              and deficit == 0):
            # 谷电时段且光伏不足 → 从电网补电（仅当后续峰电有需求）
            charge = min(power_limit, (soc_max - soc))
            charge = min(charge, daily_peak_deficit - total_battery_discharge)
            if charge > 0:
                soc += charge
                battery_power = -charge
                charge_from_grid = charge
                total_battery_charge += charge
                action = "charge_grid"

        # 3) 放电策略：峰电/平电时段且光伏不足时放电
        if deficit > 0 and soc > soc_min and action == "idle":
            if period in ("peak", "flat"):
                discharge = min(deficit, power_limit, (soc - soc_min))
                soc -= discharge
                battery_power = discharge
                total_battery_discharge += discharge
                action = "discharge"

        # 4) 电网功率
        grid_import = max(0, deficit - max(0, battery_power)) + charge_from_grid
        # 光伏富余未充入储能的部分 → 售电
        pv_unused_surplus = max(0, pv_surplus - (-battery_power if battery_power < 0 else 0))
        grid_export = min(pv_unused_surplus, config["grid_export_limit_kw"])

        # 5) 成本计算
        cost = grid_import * price - grid_export * price * 0.5  # 售电半价
        om_cost = (abs(battery_power) + pv) * config["om_cost_per_kwh"]
        carbon_t = grid_import * config["carbon_factor"] / 1000  # tCO2

        total_grid_kwh += grid_import
        total_pv_kwh += pv
        total_cost += cost
        total_om_cost += om_cost
        total_carbon_t += carbon_t

        schedule.append({
            "hour": h,
            "period": period,
            "period_name": TARIFF[period]["name"],
            "price": price,
            "elec_load_kw": round(load, 2),
            "cooling_load_kw": round(cool, 2),
            "heat_load_kw": round(heat, 2),
            "pv_power_kw": round(pv, 2),
            "battery_power_kw": round(battery_power, 2),
            "battery_action": action,
            "soc_pct": round(soc / config["battery_capacity_kwh"] * 100, 1),
            "grid_import_kw": round(grid_import, 2),
            "grid_export_kw": round(grid_export, 2),
            "cost_yuan": round(cost, 2),
            "carbon_t": round(carbon_t, 4),
        })

    summary = {
        "total_grid_import_kwh": round(total_grid_kwh, 2),
        "total_pv_kwh": round(total_pv_kwh, 2),
        "total_battery_charge_kwh": round(total_battery_charge, 2),
        "total_battery_discharge_kwh": round(total_battery_discharge, 2),
        "total_cost_yuan": round(total_cost + total_om_cost, 2),
        "total_om_cost_yuan": round(total_om_cost, 2),
        "total_carbon_t": round(total_carbon_t, 4),
        "pv_self_consumption_rate_pct": round(
            (total_pv_kwh - sum(s["grid_export_kw"] for s in schedule)) /
            max(1, total_pv_kwh) * 100, 2
        ),
        "final_soc_pct": round(soc / config["battery_capacity_kwh"] * 100, 1),
        "need_valley_charge": need_valley_charge,
    }
    return schedule, summary


def _baseline_schedule(load_curve, cooling_curve, heat_curve, pv_curve, config):
    """
    计算无储能优化的基线方案（仅电网 + 光伏）
    用于对比优化前后的效果
    """
    schedule = []
    total_grid_kwh = 0
    total_pv_kwh = 0
    total_cost = 0
    total_carbon_t = 0

    for h in range(24):
        load = load_curve[h]
        pv = pv_curve[h]
        period = _get_period(h)
        price = TARIFF[period]["price"]

        grid_import = max(0, load - pv)
        grid_export = max(0, pv - load)
        grid_export = min(grid_export, config["grid_export_limit_kw"])

        cost = grid_import * price - grid_export * price * 0.5
        carbon_t = grid_import * config["carbon_factor"] / 1000

        total_grid_kwh += grid_import
        total_pv_kwh += pv
        total_cost += cost
        total_carbon_t += carbon_t

        schedule.append({
            "hour": h,
            "period": period,
            "price": price,
            "elec_load_kw": round(load, 2),
            "pv_power_kw": round(pv, 2),
            "battery_power_kw": 0,
            "grid_import_kw": round(grid_import, 2),
            "grid_export_kw": round(grid_export, 2),
            "cost_yuan": round(cost, 2),
            "carbon_t": round(carbon_t, 4),
        })

    summary = {
        "total_grid_import_kwh": round(total_grid_kwh, 2),
        "total_pv_kwh": round(total_pv_kwh, 2),
        "total_cost_yuan": round(total_cost, 2),
        "total_carbon_t": round(total_carbon_t, 4),
    }
    return schedule, summary


@router.get("/api/multi_energy/overview")
async def multi_energy_overview():
    """
    多能系统概览
    - 当前各能源流量（电/冷/热）
    - 耦合效率（电→冷 COP、电→热效率）
    - 当前小时峰谷电价时段
    """
    try:
        now = datetime.datetime.now()
        hour = now.hour
        period = _get_period(hour)
        price = TARIFF[period]["price"]

        # DB 查询下沉到线程池，避免阻塞事件循环
        current = await asyncio.to_thread(_fetch_current_load)
        pv_now = await asyncio.to_thread(_fetch_pv_current)
        capacity = await asyncio.to_thread(_fetch_devices_total_capacity)

        # 计算耦合流量
        elec_load = current["elec"]
        cooling_load = current["cooling"]
        heat_load = current["heat"]
        cop = current["cop"] if current["cop"] > 0 else SYSTEM_CONFIG["chiller_cop"]

        # 用于制冷的电量估算：cooling_load / cop
        elec_for_cooling = cooling_load / cop if cop > 0 else 0
        # 用于制热的电量估算：heat_load / boiler_efficiency
        elec_for_heating = heat_load / SYSTEM_CONFIG["boiler_efficiency"]
        # 其他用电
        elec_other = max(0, elec_load - elec_for_cooling - elec_for_heating)

        # 电网与光伏分流
        grid_import = max(0, elec_load - pv_now)
        pv_self_consumption = min(pv_now, elec_load)

        # 耦合效率
        coupling_efficiency = {
            "cooling_cop": round(cop, 2),
            "heating_efficiency": SYSTEM_CONFIG["boiler_efficiency"],
            "pv_utilization_pct": round(pv_self_consumption / max(1, pv_now) * 100, 1) if pv_now > 0 else 0,
            "renewable_ratio_pct": round(pv_self_consumption / max(1, elec_load) * 100, 1) if elec_load > 0 else 0,
        }

        return {
            "status": "success",
            "data": {
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "current_hour": hour,
                "period": period,
                "period_name": TARIFF[period]["name"],
                "price": price,
                "energy_flow": {
                    "electricity": {
                        "total_load_kw": round(elec_load, 2),
                        "grid_import_kw": round(grid_import, 2),
                        "pv_generation_kw": round(pv_now, 2),
                        "pv_self_consumption_kw": round(pv_self_consumption, 2),
                        "breakdown": {
                            "for_cooling_kw": round(elec_for_cooling, 2),
                            "for_heating_kw": round(elec_for_heating, 2),
                            "other_kw": round(elec_other, 2),
                        },
                    },
                    "cooling": {
                        "load_kw": round(cooling_load, 2),
                        "supply_kw": round(cooling_load, 2),  # 假定供需平衡
                        "source": "电制冷冷水机组",
                        "cop": round(cop, 2),
                    },
                    "heat": {
                        "load_kw": round(heat_load, 2),
                        "supply_kw": round(heat_load, 2),
                        "source": "电锅炉",
                        "efficiency": SYSTEM_CONFIG["boiler_efficiency"],
                    },
                },
                "coupling_efficiency": coupling_efficiency,
                "capacity": capacity,
                "config": {
                    "chiller_cop": SYSTEM_CONFIG["chiller_cop"],
                    "boiler_efficiency": SYSTEM_CONFIG["boiler_efficiency"],
                    "pv_capacity_kw": SYSTEM_CONFIG["pv_capacity_kw"],
                    "battery_capacity_kwh": SYSTEM_CONFIG["battery_capacity_kwh"],
                    "battery_power_kw": SYSTEM_CONFIG["battery_power_kw"],
                    "carbon_factor": SYSTEM_CONFIG["carbon_factor"],
                },
                "tariff": {
                    "current_period": period,
                    "current_price": price,
                    "table": [
                        {"period": k, "name": v["name"], "price": v["price"],
                         "hours": sorted(PEAK_HOURS) if k == "peak"
                         else sorted(VALLEY_HOURS) if k == "valley"
                         else sorted(set(range(24)) - PEAK_HOURS - VALLEY_HOURS)}
                        for k, v in TARIFF.items()
                    ],
                },
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "多能系统概览查询")


@router.get("/api/multi_energy/optimize")
async def multi_energy_optimize():
    """
    最优调度策略（24h 逐时段电/冷/热调度方案）
    - 基于峰谷电价时段做储能调度优化
    - 最小化总成本 = 电费 + 运维成本 - 售电收入
    """
    try:
        # DB 查询下沉到线程池，避免阻塞事件循环
        load_curve = await asyncio.to_thread(_fetch_hourly_load_profile)
        loads = await asyncio.to_thread(_fetch_cooling_heat_load)
        cooling_curve = loads["cooling"]
        heat_curve = loads["heat"]
        pv_curve = await asyncio.to_thread(_fetch_pv_generation_24h)

        schedule, summary = _optimize_schedule(
            load_curve, cooling_curve, heat_curve, pv_curve, SYSTEM_CONFIG
        )

        return {
            "status": "success",
            "data": {
                "schedule": schedule,
                "summary": summary,
                "config": {
                    "battery_capacity_kwh": SYSTEM_CONFIG["battery_capacity_kwh"],
                    "battery_power_kw": SYSTEM_CONFIG["battery_power_kw"],
                    "battery_soc_range": [
                        SYSTEM_CONFIG["battery_soc_min"],
                        SYSTEM_CONFIG["battery_soc_max"],
                    ],
                    "pv_capacity_kw": SYSTEM_CONFIG["pv_capacity_kw"],
                    "grid_export_limit_kw": SYSTEM_CONFIG["grid_export_limit_kw"],
                },
                "strategy": "光伏富余优先充电（免费电力）→ 峰电时段放电抵消电网购电 → 谷电补电仅当光伏不足且后续峰电有缺口；保证 SOC 日终回归初值",
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "多能系统调度优化")


@router.get("/api/multi_energy/comparison")
@cache_response(ttl=120)  # 优化前后对比计算量大，缓存 2 分钟
async def multi_energy_comparison():
    """
    优化前后对比
    - 基线方案：仅电网 + 光伏，无储能调度
    - 优化方案：含储能削峰填谷
    - 对比维度：能耗、成本、碳排放
    """
    try:
        # DB 查询下沉到线程池，避免阻塞事件循环
        load_curve = await asyncio.to_thread(_fetch_hourly_load_profile)
        loads = await asyncio.to_thread(_fetch_cooling_heat_load)
        cooling_curve = loads["cooling"]
        heat_curve = loads["heat"]
        pv_curve = await asyncio.to_thread(_fetch_pv_generation_24h)

        # 基线方案
        baseline_schedule, baseline_summary = _baseline_schedule(
            load_curve, cooling_curve, heat_curve, pv_curve, SYSTEM_CONFIG
        )
        # 优化方案
        opt_schedule, opt_summary = _optimize_schedule(
            load_curve, cooling_curve, heat_curve, pv_curve, SYSTEM_CONFIG
        )

        # 逐时段成本对比
        hourly_compare = []
        for h in range(24):
            b = baseline_schedule[h]
            o = opt_schedule[h]
            hourly_compare.append({
                "hour": h,
                "period": b["period"],
                "baseline_cost": b["cost_yuan"],
                "optimized_cost": o["cost_yuan"],
                "saving": round(b["cost_yuan"] - o["cost_yuan"], 2),
                "baseline_grid": b["grid_import_kw"],
                "optimized_grid": o["grid_import_kw"],
                "battery_power": o["battery_power_kw"],
            })

        # 汇总对比
        cost_saving = baseline_summary["total_cost_yuan"] - opt_summary["total_cost_yuan"]
        cost_saving_rate = cost_saving / max(1, baseline_summary["total_cost_yuan"]) * 100
        grid_reduction = baseline_summary["total_grid_import_kwh"] - opt_summary["total_grid_import_kwh"]
        grid_reduction_rate = grid_reduction / max(1, baseline_summary["total_grid_import_kwh"]) * 100
        carbon_reduction = baseline_summary["total_carbon_t"] - opt_summary["total_carbon_t"]
        carbon_reduction_rate = carbon_reduction / max(1, baseline_summary["total_carbon_t"]) * 100
        peak_shaving_kw = round(
            max(b["grid_import_kw"] for b in baseline_schedule) -
            max(o["grid_import_kw"] for o in opt_schedule), 2
        )

        return {
            "status": "success",
            "data": {
                "baseline": baseline_summary,
                "optimized": opt_summary,
                "comparison": {
                    "cost_saving_yuan": round(cost_saving, 2),
                    "cost_saving_rate_pct": round(cost_saving_rate, 2),
                    "grid_reduction_kwh": round(grid_reduction, 2),
                    "grid_reduction_rate_pct": round(grid_reduction_rate, 2),
                    "carbon_reduction_t": round(carbon_reduction, 4),
                    "carbon_reduction_rate_pct": round(carbon_reduction_rate, 2),
                    "peak_shaving_kw": peak_shaving_kw,
                },
                "hourly_comparison": hourly_compare,
                "conclusion": _build_conclusion(
                    cost_saving, carbon_reduction, grid_reduction,
                    peak_shaving=peak_shaving_kw
                ),
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "多能系统优化对比")


def _build_conclusion(cost_saving: float, carbon_reduction: float,
                      grid_reduction: float, peak_shaving: float = 0) -> str:
    """生成对比结论（区分经济性与能源性收益）"""
    parts = []
    if cost_saving > 0:
        parts.append(f"✅ 日节省电费 {cost_saving:.2f} 元（年化预计 {cost_saving * 365:.0f} 元）")
    else:
        parts.append(f"⚠️ 日电费增加 {-cost_saving:.2f} 元（光伏富余售电收益下降，但提升能源自给率）")
    if carbon_reduction > 0:
        parts.append(f"日减排 CO₂ {carbon_reduction:.4f} 吨（年化 {carbon_reduction * 365:.2f} 吨）")
    if grid_reduction > 0:
        parts.append(f"日减少电网购电 {grid_reduction:.2f} kWh（提升自给率）")
    if peak_shaving > 0:
        parts.append(f"削峰能力 {peak_shaving:.2f} kW")
    if cost_saving <= 0 and (carbon_reduction > 0 or grid_reduction > 0):
        parts.append("建议结合需求响应补贴与容量电价机制进一步提升经济性")
    return "；".join(parts) + "。"
