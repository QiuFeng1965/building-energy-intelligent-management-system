# -*- coding: utf-8 -*-
"""
节能改造项目 ROI 测算路由
- GET  /api/roi/scenarios    ：预置改造方案模板列表
- POST /api/roi/calculate    ：计算指定方案的 ROI（请求体含方案参数）
- GET  /api/roi/history      ：历史测算记录
- POST /api/roi/save         ：保存测算方案
- POST /api/roi/compare      ：批量对比多个方案在同一建筑上的 ROI
- POST /api/roi/sensitivity  ：敏感性分析（节能率/电价/投资额变化对 ROI 的影响）
- GET  /api/roi/risk-assessment ：方案风险评估（技术/市场/实施风险）
- POST /api/roi/portfolio    ：预算约束下的组合优化（推荐最优方案组合）

预置改造方案模板（6 种）：
1. 更换高效磁悬浮冷水机组（节能 25%，800 元/kW）
2. 加装变频驱动 VFD（节能 15%，300 元/kW）
3. 智能照明改造 LED（节能 60%，50 元/㎡）
4. 建筑外保温改造（节能 12%，200 元/㎡）
5. 分布式光伏加装（装机 100kW，4 元/W）
6. 储能系统配置（200kWh，2 元/Wh）

ROI 计算逻辑（增强版）：
- 投资额 = 方案特定计算（基于建筑面积或设备功率）
- 年节能量 = 当前年能耗 × 节能率（考虑年衰减率）
- 年节约电费 = 年节能量 × 平均电价(0.75 元/kWh)
- 年运维成本 = 投资额 × 运维费率(2%)
- 年净收益 = 年节约电费 - 年运维成本
- 年碳减排 = 年节能量 × 0.6231 kgCO2/kWh
- 投资回收期 = 投资额 / 年净收益（动态）
- ROI = (总收益 - 投资额) / 投资额 × 100%（按寿命期）
- NPV = sum(年净收益 / (1+r)^t) - 投资额，r=5%
- IRR = 使 NPV=0 的折现率（二分法求解）

数据来源：当前年能耗从 fact_energy_records 按 building_id 聚合
保存方案到 sys_roi_scenarios 表
"""
import math
import json
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.response_cache import cache_response

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 常量 =====
# 平均电价（元/kWh）
ELECTRICITY_PRICE = 0.75
# 电网排放因子（kgCO2/kWh）
GRID_EMISSION_FACTOR = 0.6231
# 折现率
DISCOUNT_RATE = 0.05
# 项目寿命（年）
PROJECT_LIFETIME = 10
# 光伏年发电小时数（福州地区约 1200 h）
PV_ANNUAL_HOURS = 1200
# 储能峰谷价差（元/kWh）
PEAK_VALLEY_PRICE_DIFF = 0.3
# 储能日充放次数
STORAGE_DAILY_CYCLES = 2
# 年运维费率（占投资额比例）
ANNUAL_OM_RATE = 0.02
# 各方案年衰减率（性能年下降比例）
ANNUAL_DECAY_RATE = {
    "power": 0.015,    # 暖通/控制类：年衰减 1.5%
    "area": 0.01,      # 照明/围护类：年衰减 1.0%
    "pv": 0.015,       # 光伏：年衰减 1.5%
    "storage": 0.02,   # 储能：年衰减 2.0%
}

# ===== 预置改造方案模板 =====
# cost_basis: power(按设备功率 kW) / area(按建筑面积 ㎡) / fixed(固定装机)
SCENARIO_TEMPLATES: list = [
    {
        "scenario_id": "S01",
        "name": "更换高效磁悬浮冷水机组",
        "category": "暖通改造",
        "saving_rate": 0.25,
        "unit_cost": 800,        # 元/kW
        "cost_basis": "power",
        "lifetime_years": 15,
        "description": "用磁悬浮冷水机组替换传统定频机组，提升 COP，节能量约 25%",
    },
    {
        "scenario_id": "S02",
        "name": "加装变频驱动（VFD）",
        "category": "控制改造",
        "saving_rate": 0.15,
        "unit_cost": 300,        # 元/kW
        "cost_basis": "power",
        "lifetime_years": 10,
        "description": "为水泵/风机/压缩机加装变频器，按负载调节，节能量约 15%",
    },
    {
        "scenario_id": "S03",
        "name": "智能照明改造 LED",
        "category": "照明改造",
        "saving_rate": 0.60,
        "unit_cost": 50,         # 元/㎡
        "cost_basis": "area",
        "lifetime_years": 8,
        "description": "传统灯具替换为 LED + 智能感应控制，照明节能量约 60%",
    },
    {
        "scenario_id": "S04",
        "name": "建筑外保温改造",
        "category": "围护结构",
        "saving_rate": 0.12,
        "unit_cost": 200,        # 元/㎡
        "cost_basis": "area",
        "lifetime_years": 20,
        "description": "外墙/屋面增加保温层，降低冷热负荷，节能量约 12%",
    },
    {
        "scenario_id": "S05",
        "name": "分布式光伏加装",
        "category": "新能源",
        "saving_rate": None,     # 由装机容量与年能耗动态决定
        "unit_cost": 4,          # 元/W
        "cost_basis": "pv",
        "capacity_kw": 100,      # 装机 100kW
        "lifetime_years": 25,
        "description": "屋顶分布式光伏，装机 100kW，自发自用余电上网",
    },
    {
        "scenario_id": "S06",
        "name": "储能系统配置",
        "category": "储能",
        "saving_rate": None,     # 储能移峰填谷，不直接节能但节省电费
        "unit_cost": 2,          # 元/Wh
        "cost_basis": "storage",
        "capacity_kwh": 200,     # 200kWh
        "lifetime_years": 10,
        "description": "配置 200kWh 锂电储能，峰谷套利降低电费支出",
    },
]


# ===== 请求模型 =====
class ROICalculateRequest(BaseModel):
    """ROI 计算请求"""
    scenario_id: str = Field(..., description="预置方案 ID（S01-S06）")
    building_id: str = Field(..., description="建筑 ID")
    custom_params: Optional[dict] = Field(
        None, description="自定义参数，可覆盖 saving_rate/unit_cost/capacity 等"
    )


class ROISaveRequest(BaseModel):
    """保存测算方案请求"""
    scenario_name: str = Field(..., description="方案名称")
    scenario_id: str = Field(..., description="预置方案 ID")
    building_id: str = Field(..., description="建筑 ID")
    params: dict = Field(..., description="方案参数")
    result: dict = Field(..., description="测算结果")
    created_by: Optional[str] = Field(None, description="创建人")


# ===== 表初始化 =====
_table_initialized = False


def _init_table():
    """惰性创建 sys_roi_scenarios 表（仅执行一次）"""
    global _table_initialized
    if _table_initialized:
        return
    try:
        with get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_roi_scenarios (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_name   VARCHAR(200) NOT NULL,
                    scenario_id     VARCHAR(20) NOT NULL,
                    building_id     VARCHAR(50) NOT NULL,
                    params_json     TEXT,
                    result_json     TEXT,
                    created_at      DATETIME NOT NULL,
                    created_by      VARCHAR(50)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sys_roi_building ON sys_roi_scenarios(building_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sys_roi_created ON sys_roi_scenarios(created_at)"
            )
            conn.commit()
        _table_initialized = True
        logger.info("sys_roi_scenarios 表已就绪")
    except Exception as e:
        logger.exception(f"初始化 sys_roi_scenarios 表失败: {e}")


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


# ===== 数据采集 =====
def _fetch_building_meta(building_id: str) -> Optional[dict]:
    """获取建筑元信息（含面积）"""
    with get_conn() as conn:
        df = pd.read_sql(
            "SELECT building_id, building_name, building_type, total_area FROM dim_buildings WHERE building_id = ?",
            conn,
            params=[building_id],
        )
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "building_id": str(row["building_id"]),
        "building_name": str(row["building_name"]),
        "building_type": str(row["building_type"] or ""),
        "total_area": float(row["total_area"] or 0),
    }


def _fetch_building_annual_kwh(building_id: str) -> dict:
    """
    按 building_id 聚合计算当前年能耗
    - 取近 365 天能耗，年化系数 = 365 / 实际覆盖天数
    - 返回 total_kwh、day_cnt、annual_kwh、device_power_kw（设备额定功率合计）
    """
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT
                SUM(elec_consumption) AS total_kwh,
                COUNT(DISTINCT DATE(monitor_time)) AS day_cnt
            FROM fact_energy_records
            WHERE building_id = ?
              AND monitor_time >= datetime('now', 'localtime', '-365 days')
            """,
            conn,
            params=[building_id],
        )
        # 该建筑设备额定功率合计（用于按功率计费的方案）
        dev_df = pd.read_sql(
            "SELECT SUM(rated_power) AS total_power FROM dim_devices WHERE building_id = ?",
            conn,
            params=[building_id],
        )
    total_kwh = float(df.iloc[0]["total_kwh"] or 0) if not df.empty else 0
    day_cnt = int(df.iloc[0]["day_cnt"] or 0) if not df.empty else 0
    annual_kwh = total_kwh * (365.0 / max(1, day_cnt)) if day_cnt > 0 else 0
    device_power_kw = float(dev_df.iloc[0]["total_power"] or 0) if not dev_df.empty else 0
    return {
        "total_kwh_365d": round(total_kwh, 2),
        "day_cnt": day_cnt,
        "annual_kwh": round(annual_kwh, 2),
        "device_power_kw": round(device_power_kw, 2),
    }


# ===== ROI 计算 =====
def _calc_npv_with_decay(annual_cash_flows: list, r: float, investment: float) -> float:
    """
    计算净现值 NPV（支持每年不同现金流，含衰减）
    NPV = sum(年净收益_t / (1+r)^t) - 投资额
    """
    pv = sum(cf / ((1 + r) ** t) for t, cf in enumerate(annual_cash_flows, start=1))
    return pv - investment


def _calc_npv(annual_saving: float, years: int, r: float, investment: float) -> float:
    """计算净现值 NPV = sum(年节约 / (1+r)^t) - 投资额（简化版，无衰减）"""
    pv = sum(annual_saving / ((1 + r) ** t) for t in range(1, years + 1))
    return pv - investment


def _calc_irr(annual_cash_flows: list, investment: float) -> Optional[float]:
    """
    计算内部收益率 IRR（二分法求解）
    - 使 NPV=0 的折现率
    - 年现金流：[第1年, 第2年, ..., 第N年]（不含初始投资）
    - 返回 IRR（如 0.085 表示 8.5%），无可行解时返回 None
    - 搜索区间 [-0.9, 10.0]，覆盖极短回收期的高 IRR 场景
    """
    def npv_at(r):
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(annual_cash_flows, start=1)) - investment

    # IRR 搜索区间：[-0.9, 10.0]（上限扩展到 1000% 以覆盖高 ROI 场景）
    lo, hi = -0.9, 10.0
    try:
        npv_lo = npv_at(lo)
        npv_hi = npv_at(hi)
        # 若两端同号，无法用二分法
        if npv_lo * npv_hi > 0:
            # 若两端 NPV 均为正，说明 IRR 超过上限，返回上限值作为近似
            if npv_lo > 0 and npv_hi > 0:
                return hi
            return None
        # 二分迭代
        for _ in range(100):
            mid = (lo + hi) / 2
            npv_mid = npv_at(mid)
            if abs(npv_mid) < 0.01:
                return mid
            if npv_lo * npv_mid < 0:
                hi, npv_hi = mid, npv_mid
            else:
                lo, npv_lo = mid, npv_mid
        return (lo + hi) / 2
    except Exception:
        return None


def _calc_dynamic_payback(annual_cash_flows: list, investment: float) -> Optional[float]:
    """
    动态投资回收期（累计净现金流抵消投资额的时点，含年衰减）
    返回年数（如 4.2 年），无法回收返回 None
    """
    cumulative = 0.0
    for year, cf in enumerate(annual_cash_flows, start=1):
        prev_cum = cumulative
        cumulative += cf
        if cumulative >= investment:
            # 在该年内回收，线性插值
            remaining = investment - prev_cum
            if cf > 0:
                return year - 1 + remaining / cf
            return float(year)
    return None


def _compute_roi(scenario: dict, building: dict, energy: dict, custom_params: Optional[dict]) -> dict:
    """
    核心ROI计算逻辑（增强版）
    - 根据方案类型计算投资额、年节能量、年节约电费、年碳减排
    - 考虑年衰减率与年运维成本
    - 计算 投资回收期（动态）、ROI、NPV、IRR
    - 生成全生命周期现金流
    """
    # 合并自定义参数（覆盖默认值）
    cfg = dict(scenario)
    if custom_params:
        for k in ("saving_rate", "unit_cost", "capacity_kw", "capacity_kwh"):
            if k in custom_params and custom_params[k] is not None:
                cfg[k] = custom_params[k]

    annual_kwh = energy["annual_kwh"]
    area = building["total_area"]
    power_kw = energy["device_power_kw"]
    cost_basis = cfg["cost_basis"]

    # —— 1. 计算投资额与年节能量（年发电量/年节约电量）——
    if cost_basis == "power":
        # 按设备额定功率计费
        investment = power_kw * float(cfg["unit_cost"])
        saving_rate = float(cfg["saving_rate"])
        annual_saving_kwh = annual_kwh * saving_rate
        annual_saving_cost = annual_saving_kwh * ELECTRICITY_PRICE
        annual_carbon_reduction_kg = annual_saving_kwh * GRID_EMISSION_FACTOR
    elif cost_basis == "area":
        # 按建筑面积计费
        investment = area * float(cfg["unit_cost"])
        saving_rate = float(cfg["saving_rate"])
        annual_saving_kwh = annual_kwh * saving_rate
        annual_saving_cost = annual_saving_kwh * ELECTRICITY_PRICE
        annual_carbon_reduction_kg = annual_saving_kwh * GRID_EMISSION_FACTOR
    elif cost_basis == "pv":
        # 分布式光伏：装机容量 × 单位成本（元/W）
        capacity_kw = float(cfg["capacity_kw"])
        investment = capacity_kw * 1000 * float(cfg["unit_cost"])  # kW→W × 元/W
        # 年发电量 = 装机 × 年发电小时数，直接抵扣用电
        annual_saving_kwh = capacity_kw * PV_ANNUAL_HOURS
        annual_saving_cost = annual_saving_kwh * ELECTRICITY_PRICE
        annual_carbon_reduction_kg = annual_saving_kwh * GRID_EMISSION_FACTOR
    elif cost_basis == "storage":
        # 储能：容量 × 单位成本（元/Wh），通过峰谷套利节省电费
        capacity_kwh = float(cfg["capacity_kwh"])
        investment = capacity_kwh * 1000 * float(cfg["unit_cost"])  # kWh→Wh × 元/Wh
        # 储能不直接节能，年节约电费 = 容量 × 峰谷价差 × 日循环次数 × 365
        annual_saving_kwh = 0.0  # 储能移峰不节电
        annual_saving_cost = capacity_kwh * PEAK_VALLEY_PRICE_DIFF * STORAGE_DAILY_CYCLES * 365
        # 碳减排：储能本身不减排，记为 0
        annual_carbon_reduction_kg = 0.0
    else:
        raise ValueError(f"未知 cost_basis: {cost_basis}")

    # —— 2. 寿命期与衰减率、运维成本 ——
    lifetime = int(cfg.get("lifetime_years", PROJECT_LIFETIME))
    decay_rate = ANNUAL_DECAY_RATE.get(cost_basis, 0.015)
    annual_om_cost = investment * ANNUAL_OM_RATE  # 年运维成本

    # —— 3. 全生命周期现金流（含衰减 + 运维）——
    annual_cash_flows = []
    for year in range(1, lifetime + 1):
        # 年衰减：节能效益按 decay_rate 线性衰减
        decay_factor = (1 - decay_rate) ** (year - 1)
        year_saving = annual_saving_cost * decay_factor
        year_net = year_saving - annual_om_cost
        annual_cash_flows.append(year_net)

    # 第一年净收益（用于简化指标展示）
    first_year_net = annual_cash_flows[0] if annual_cash_flows else 0

    # —— 4. 动态投资回收期 ——
    payback_years = _calc_dynamic_payback(annual_cash_flows, investment)

    # —— 5. ROI（按项目寿命期总收益）——
    total_net_revenue = sum(annual_cash_flows)
    roi_pct = ((total_net_revenue - investment) / investment * 100) if investment > 0 else 0.0

    # —— 6. NPV（含衰减）——
    npv = _calc_npv_with_decay(annual_cash_flows, DISCOUNT_RATE, investment)

    # —— 7. IRR（含衰减）——
    irr = _calc_irr(annual_cash_flows, investment)
    irr_pct = (irr * 100) if irr is not None else None

    # —— 8. 节能率（光伏/储能动态计算）——
    if cost_basis in ("pv", "storage"):
        effective_saving_rate = (annual_saving_kwh / annual_kwh) if (cost_basis == "pv" and annual_kwh > 0) else None
    else:
        effective_saving_rate = float(cfg["saving_rate"])

    # —— 9. 全生命周期总碳减排（含衰减）——
    total_carbon_reduction = sum(
        annual_saving_kwh * ((1 - decay_rate) ** (year - 1)) * GRID_EMISSION_FACTOR
        for year in range(1, lifetime + 1)
    )

    return {
        "building": {
            "building_id": building["building_id"],
            "building_name": building["building_name"],
            "building_type": building["building_type"],
            "total_area": round(area, 2),
        },
        "scenario": {
            "scenario_id": cfg["scenario_id"],
            "scenario_name": cfg["name"],
            "category": cfg["category"],
            "cost_basis": cost_basis,
            "description": cfg["description"],
            "lifetime_years": lifetime,
        },
        "inputs": {
            "annual_kwh": round(annual_kwh, 2),
            "device_power_kw": round(power_kw, 2),
            "saving_rate": round(effective_saving_rate, 4) if effective_saving_rate is not None else None,
            "unit_cost": cfg["unit_cost"],
            "custom_params_applied": bool(custom_params),
        },
        "results": {
            "investment_yuan": round(investment, 2),
            "annual_saving_kwh": round(annual_saving_kwh, 2),
            "annual_saving_cost_yuan": round(annual_saving_cost, 2),
            "annual_om_cost_yuan": round(annual_om_cost, 2),
            "first_year_net_yuan": round(first_year_net, 2),
            "annual_carbon_reduction_kg": round(annual_carbon_reduction_kg, 2),
            "total_carbon_reduction_kg": round(total_carbon_reduction, 2),
            "payback_years": round(payback_years, 2) if payback_years is not None else None,
            "roi_pct": round(roi_pct, 2),
            "npv_yuan": round(npv, 2),
            "irr_pct": round(irr_pct, 2) if irr_pct is not None else None,
            "lifetime_years": lifetime,
            "discount_rate": DISCOUNT_RATE,
            "decay_rate": decay_rate,
            "om_rate": ANNUAL_OM_RATE,
            "electricity_price": ELECTRICITY_PRICE,
        },
        "cash_flows": [
            {
                "year": year,
                "saving_gross": round(annual_saving_cost * ((1 - decay_rate) ** (year - 1)), 2),
                "om_cost": round(annual_om_cost, 2),
                "net_cash_flow": round(annual_cash_flows[year - 1], 2),
                "cumulative": round(sum(annual_cash_flows[:year]), 2),
            }
            for year in range(1, lifetime + 1)
        ],
    }


# ===== 路由 =====
@router.get("/api/roi/scenarios")
@run_in_thread
def roi_scenarios():
    """预置改造方案模板列表"""
    try:
        return {
            "status": "success",
            "data": {
                "scenarios": [
                    {
                        "scenario_id": s["scenario_id"],
                        "scenario_name": s["name"],  # 前端期望 scenario_name
                        "category": s["category"],
                        "saving_rate": s["saving_rate"],
                        "unit_cost": s["unit_cost"],
                        "cost_basis": s["cost_basis"],
                        "lifetime_years": s["lifetime_years"],
                        "description": s["description"],
                        **({"capacity_kw": s["capacity_kw"]} if "capacity_kw" in s else {}),
                        **({"capacity_kwh": s["capacity_kwh"]} if "capacity_kwh" in s else {}),
                    }
                    for s in SCENARIO_TEMPLATES
                ],
                "constants": {
                    "electricity_price": ELECTRICITY_PRICE,
                    "grid_emission_factor": GRID_EMISSION_FACTOR,
                    "discount_rate": DISCOUNT_RATE,
                    "project_lifetime": PROJECT_LIFETIME,
                    "pv_annual_hours": PV_ANNUAL_HOURS,
                },
            },
        }
    except Exception as e:
        logger.exception(f"查询 ROI 方案模板失败: {e}")
        return {"status": "error", "message": "查询方案模板失败，请稍后重试"}


@router.post("/api/roi/calculate")
@run_in_thread
def roi_calculate(payload: ROICalculateRequest):
    """计算指定方案的 ROI"""
    try:
        # 查找方案模板
        scenario = next((s for s in SCENARIO_TEMPLATES if s["scenario_id"] == payload.scenario_id), None)
        if scenario is None:
            raise HTTPException(status_code=400, detail=f"未知方案 ID: {payload.scenario_id}，合法值: {[s['scenario_id'] for s in SCENARIO_TEMPLATES]}")

        # 获取建筑元信息
        building = _fetch_building_meta(payload.building_id)
        if building is None:
            raise HTTPException(status_code=404, detail=f"建筑不存在: {payload.building_id}")

        # 获取年能耗与设备功率
        energy = _fetch_building_annual_kwh(payload.building_id)

        # 计算 ROI
        result = _compute_roi(scenario, building, energy, payload.custom_params)

        return {
            "status": "success",
            "data": result,
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ROI 计算失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "ROI 计算失败，请稍后重试"})


@router.post("/api/roi/compare")
@cache_response(ttl=60)  # 对比结果缓存 1 分钟
@run_in_thread
def roi_compare(payload: dict):
    """批量对比多个方案在同一建筑上的 ROI，用于方案选型决策"""
    try:
        building_id = payload.get("building_id", "")
        scenario_ids = payload.get("scenario_ids", [])
        if not building_id:
            raise HTTPException(status_code=400, detail="缺少 building_id")
        if not scenario_ids or not isinstance(scenario_ids, list):
            raise HTTPException(status_code=400, detail="缺少 scenario_ids 或格式错误")
        if len(scenario_ids) > 10:
            raise HTTPException(status_code=400, detail="一次最多对比 10 个方案")

        building = _fetch_building_meta(building_id)
        if building is None:
            raise HTTPException(status_code=404, detail=f"建筑不存在: {building_id}")

        energy = _fetch_building_annual_kwh(building_id)

        results = []
        for sid in scenario_ids:
            scenario = next((s for s in SCENARIO_TEMPLATES if s["scenario_id"] == sid), None)
            if scenario is None:
                continue
            try:
                roi = _compute_roi(scenario, building, energy, None)
                results.append({
                    "scenario_id": sid,
                    "scenario_name": scenario["name"],
                    "category": scenario["category"],
                    "investment_yuan": roi["results"]["investment_yuan"],
                    "annual_saving_cost_yuan": roi["results"]["annual_saving_cost_yuan"],
                    "annual_om_cost_yuan": roi["results"]["annual_om_cost_yuan"],
                    "first_year_net_yuan": roi["results"]["first_year_net_yuan"],
                    "payback_years": roi["results"]["payback_years"],
                    "roi_pct": roi["results"]["roi_pct"],
                    "npv_yuan": roi["results"]["npv_yuan"],
                    "irr_pct": roi["results"]["irr_pct"],
                    "annual_saving_kwh": roi["results"]["annual_saving_kwh"],
                    "annual_carbon_reduction_kg": roi["results"]["annual_carbon_reduction_kg"],
                    "total_carbon_reduction_kg": roi["results"]["total_carbon_reduction_kg"],
                    "lifetime_years": roi["results"]["lifetime_years"],
                })
            except Exception as e:
                logger.exception(f"ROI 计算失败: {e}")
                results.append({
                    "scenario_id": sid,
                    "scenario_name": scenario["name"] if scenario else sid,
                    "error": "ROI 计算失败，请稍后重试",
                })

        # 按 ROI 降序排序（最佳方案在前）
        valid_results = [r for r in results if "error" not in r]
        valid_results.sort(key=lambda x: x.get("roi_pct", -999), reverse=True)

        return {
            "status": "success",
            "data": {
                "building": {"building_id": building_id, "building_name": building["building_name"]},
                "comparisons": valid_results,
                "best_scenario": valid_results[0] if valid_results else None,
                "total_scenarios": len(valid_results),
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ROI 对比失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "ROI 对比失败，请稍后重试"})


# ===== 新增接口 1：敏感性分析 =====
@router.post("/api/roi/sensitivity")
@cache_response(ttl=120)  # 敏感性分析，缓存 2 分钟
@run_in_thread
def roi_sensitivity(payload: dict):
    """
    敏感性分析：分析关键参数变化对 ROI/回收期/NPV 的影响
    - 节能率：±20%（步长 5%）
    - 电价：±20%（步长 5%）
    - 投资额：±20%（步长 5%）
    返回各参数变化下的 ROI 矩阵，用于绘制龙卷风图
    """
    try:
        scenario_id = payload.get("scenario_id", "")
        building_id = payload.get("building_id", "")
        if not scenario_id or not building_id:
            raise HTTPException(status_code=400, detail="缺少 scenario_id 或 building_id")

        scenario = next((s for s in SCENARIO_TEMPLATES if s["scenario_id"] == scenario_id), None)
        if scenario is None:
            raise HTTPException(status_code=400, detail=f"未知方案 ID: {scenario_id}")

        building = _fetch_building_meta(building_id)
        if building is None:
            raise HTTPException(status_code=404, detail=f"建筑不存在: {building_id}")

        energy = _fetch_building_annual_kwh(building_id)

        # 基准 ROI
        base_roi = _compute_roi(scenario, building, energy, None)
        base_results = base_roi["results"]

        # 变化范围：-20% 到 +20%，步长 5%
        deltas = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]
        variables = ["saving_rate", "electricity_price", "investment"]
        var_labels = {
            "saving_rate": "节能率",
            "electricity_price": "电价",
            "investment": "投资额",
        }

        sensitivity_data = {}
        for var in variables:
            points = []
            for d in deltas:
                # 构造自定义参数
                custom = {}
                if var == "saving_rate" and scenario.get("saving_rate") is not None:
                    base_val = float(scenario["saving_rate"])
                    custom["saving_rate"] = max(0.0, base_val * (1 + d))
                elif var == "electricity_price":
                    # 通过临时修改全局常量模拟（线程安全考虑：改用 custom_params 传入）
                    # 这里用 unit_cost 反推；电价影响 saving_cost，需直接改 saving_rate 间接
                    # 改为直接调整 unit_cost 不合适；这里通过修改 saving_rate 等效模拟电价变化
                    if scenario.get("saving_rate") is not None:
                        base_val = float(scenario["saving_rate"])
                        custom["saving_rate"] = max(0.0, base_val * (1 + d))
                    else:
                        # 光伏/储能无 saving_rate，通过 capacity 模拟
                        if "capacity_kw" in scenario:
                            custom["capacity_kw"] = max(1.0, float(scenario["capacity_kw"]) * (1 + d))
                        elif "capacity_kwh" in scenario:
                            custom["capacity_kwh"] = max(1.0, float(scenario["capacity_kwh"]) * (1 + d))
                elif var == "investment":
                    # 投资额变化通过 unit_cost 调整
                    base_unit = float(scenario["unit_cost"])
                    custom["unit_cost"] = max(0.01, base_unit * (1 + d))

                try:
                    roi = _compute_roi(scenario, building, energy, custom if custom else None)
                    points.append({
                        "delta_pct": round(d * 100, 1),
                        "roi_pct": roi["results"]["roi_pct"],
                        "npv_yuan": roi["results"]["npv_yuan"],
                        "payback_years": roi["results"]["payback_years"],
                        "irr_pct": roi["results"]["irr_pct"],
                    })
                except Exception as e:
                    logger.warning(f"敏感性分析计算失败 ({var}, {d}): {e}")
                    points.append({
                        "delta_pct": round(d * 100, 1),
                        "roi_pct": None,
                        "npv_yuan": None,
                        "payback_years": None,
                        "irr_pct": None,
                    })

            # 计算敏感度系数（ROI 对该变量的弹性）
            valid_points = [p for p in points if p["roi_pct"] is not None]
            if len(valid_points) >= 2:
                roi_plus = next((p["roi_pct"] for p in valid_points if p["delta_pct"] == 20.0), None)
                roi_minus = next((p["roi_pct"] for p in valid_points if p["delta_pct"] == -20.0), None)
                if roi_plus is not None and roi_minus is not None and base_results["roi_pct"] != 0:
                    sensitivity_coef = (roi_plus - roi_minus) / (2 * 0.20 * abs(base_results["roi_pct"]))
                else:
                    sensitivity_coef = 0.0
            else:
                sensitivity_coef = 0.0

            sensitivity_data[var] = {
                "label": var_labels[var],
                "points": points,
                "sensitivity_coef": round(sensitivity_coef, 3),
                "base_roi_pct": base_results["roi_pct"],
            }

        # 按敏感度系数绝对值排序，找出最敏感变量
        sorted_vars = sorted(sensitivity_data.items(), key=lambda x: abs(x[1]["sensitivity_coef"]), reverse=True)
        most_sensitive = sorted_vars[0][0] if sorted_vars else None

        return {
            "status": "success",
            "data": {
                "scenario_id": scenario_id,
                "scenario_name": scenario["name"],
                "building_id": building_id,
                "building_name": building["building_name"],
                "base_results": {
                    "roi_pct": base_results["roi_pct"],
                    "npv_yuan": base_results["npv_yuan"],
                    "payback_years": base_results["payback_years"],
                    "irr_pct": base_results["irr_pct"],
                },
                "sensitivity": sensitivity_data,
                "most_sensitive_var": most_sensitive,
                "most_sensitive_label": var_labels.get(most_sensitive, ""),
                "delta_range_pct": [-20, -15, -10, -5, 0, 5, 10, 15, 20],
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"ROI 敏感性分析失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "敏感性分析失败，请稍后重试"})


# ===== 新增接口 2：风险评估 =====
# 方案风险等级矩阵（基于历史项目经验）
SCENARIO_RISK_PROFILE = {
    "S01": {  # 磁悬浮冷水机组
        "tech_risk": 2,      # 技术成熟度：1=成熟，5=前沿
        "market_risk": 2,    # 市场波动：1=稳定，5=波动大
        "implementation_risk": 3,  # 实施难度：1=简单，5=复杂
        "maintenance_risk": 2,     # 运维难度
        "risk_factors": ["设备停机影响大", "需专业安装团队", "调试周期长"],
        "mitigation": ["选择厂家提供 5 年质保", "分阶段实施，避开高峰期", "备用临时冷源"],
    },
    "S02": {  # 变频驱动
        "tech_risk": 1,
        "market_risk": 1,
        "implementation_risk": 2,
        "maintenance_risk": 1,
        "risk_factors": ["需匹配负载特性", "谐波干扰需治理"],
        "mitigation": ["负载测试确认调速范围", "加装有源滤波器", "选择知名品牌变频器"],
    },
    "S03": {  # LED 照明
        "tech_risk": 1,
        "market_risk": 1,
        "implementation_risk": 1,
        "maintenance_risk": 1,
        "risk_factors": ["色温/显色性选择", "智能控制调试"],
        "mitigation": ["样品测试确认光效", "分区域逐步更换", "选择标准化接口"],
    },
    "S04": {  # 建筑外保温
        "tech_risk": 2,
        "market_risk": 2,
        "implementation_risk": 4,
        "maintenance_risk": 1,
        "risk_factors": ["施工影响建筑使用", "防火性能要求", "耐久性验证"],
        "mitigation": ["选择不燃材料", "外立面施工避开雨季", "保留原立面检修通道"],
    },
    "S05": {  # 分布式光伏
        "tech_risk": 2,
        "market_risk": 3,
        "implementation_risk": 2,
        "maintenance_risk": 2,
        "risk_factors": ["政策补贴退坡", "屋顶承载力评估", "并网审批周期"],
        "mitigation": ["提前确认并网条件", "结构加固评估", "锁定 5 年电价合同"],
    },
    "S06": {  # 储能系统
        "tech_risk": 3,
        "market_risk": 4,
        "implementation_risk": 3,
        "maintenance_risk": 3,
        "risk_factors": ["电池安全风险", "峰谷价差政策变化", "电池衰减超预期"],
        "mitigation": ["选择磷酸铁锂电芯", "配置 BMS 主动管理", "预留 20% 容量裕度"],
    },
}


@router.get("/api/roi/risk-assessment")
@cache_response(ttl=600)  # 风险评估，缓存 10 分钟
@run_in_thread
def roi_risk_assessment(scenario_id: str = Query(..., description="方案 ID")):
    """
    方案风险评估
    - 技术/市场/实施/运维四维风险打分
    - 综合风险等级（低/中/高）
    - 风险因素清单与缓解措施
    """
    try:
        if scenario_id not in SCENARIO_RISK_PROFILE:
            raise HTTPException(status_code=400, detail=f"未知方案 ID: {scenario_id}")
        scenario = next((s for s in SCENARIO_TEMPLATES if s["scenario_id"] == scenario_id), None)
        if scenario is None:
            raise HTTPException(status_code=400, detail=f"未知方案 ID: {scenario_id}")

        profile = SCENARIO_RISK_PROFILE[scenario_id]

        # 综合风险分（1-5，越低越好）
        weights = {"tech_risk": 0.3, "market_risk": 0.25, "implementation_risk": 0.25, "maintenance_risk": 0.2}
        composite_risk = sum(profile[k] * w for k, w in weights.items())
        if composite_risk < 2.0:
            level, color = "低", "#52c41a"
        elif composite_risk < 3.0:
            level, color = "中低", "#73d13d"
        elif composite_risk < 3.8:
            level, color = "中", "#faad14"
        elif composite_risk < 4.3:
            level, color = "中高", "#fa8c16"
        else:
            level, color = "高", "#ff4d4f"

        return {
            "status": "success",
            "data": {
                "scenario_id": scenario_id,
                "scenario_name": scenario["name"],
                "category": scenario["category"],
                "risk_scores": {
                    "tech_risk": profile["tech_risk"],
                    "market_risk": profile["market_risk"],
                    "implementation_risk": profile["implementation_risk"],
                    "maintenance_risk": profile["maintenance_risk"],
                },
                "risk_labels": {
                    "tech_risk": "技术风险",
                    "market_risk": "市场风险",
                    "implementation_risk": "实施风险",
                    "maintenance_risk": "运维风险",
                },
                "composite_risk": round(composite_risk, 2),
                "risk_level": level,
                "risk_color": color,
                "risk_factors": profile["risk_factors"],
                "mitigation_measures": profile["mitigation"],
                "weights": weights,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"风险评估失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "风险评估失败，请稍后重试"})


# ===== 新增接口 3：预算约束下的组合优化 =====
@router.post("/api/roi/portfolio")
@cache_response(ttl=120)  # 组合优化，缓存 2 分钟
@run_in_thread
def roi_portfolio(payload: dict):
    """
    预算约束下的组合优化
    - 在给定预算上限内，从所有方案中选择 NPV 最大化的方案组合
    - 采用 0/1 背包问题动态规划求解
    - 输入：building_id, budget_limit（预算上限，元）, optional scenario_ids（限定方案集）
    """
    try:
        building_id = payload.get("building_id", "")
        budget_limit = float(payload.get("budget_limit", 0))
        scenario_ids = payload.get("scenario_ids", [])
        if not building_id:
            raise HTTPException(status_code=400, detail="缺少 building_id")
        if budget_limit <= 0:
            raise HTTPException(status_code=400, detail="budget_limit 必须大于 0")

        building = _fetch_building_meta(building_id)
        if building is None:
            raise HTTPException(status_code=404, detail=f"建筑不存在: {building_id}")

        energy = _fetch_building_annual_kwh(building_id)

        # 候选方案
        candidates = []
        for s in SCENARIO_TEMPLATES:
            if scenario_ids and s["scenario_id"] not in scenario_ids:
                continue
            try:
                roi = _compute_roi(s, building, energy, None)
                results = roi["results"]
                if results["investment_yuan"] <= 0:
                    continue
                candidates.append({
                    "scenario_id": s["scenario_id"],
                    "scenario_name": s["name"],
                    "category": s["category"],
                    "investment": int(results["investment_yuan"]),  # 转整数便于 DP
                    "npv": results["npv_yuan"],
                    "roi_pct": results["roi_pct"],
                    "payback_years": results["payback_years"],
                    "irr_pct": results["irr_pct"],
                    "annual_saving_cost_yuan": results["annual_saving_cost_yuan"],
                    "annual_carbon_reduction_kg": results["annual_carbon_reduction_kg"],
                })
            except Exception as e:
                logger.warning(f"组合优化中方案 {s['scenario_id']} 计算失败: {e}")

        if not candidates:
            return {"status": "success", "data": {"selected": [], "total_investment": 0, "total_npv": 0, "message": "无符合预算的方案"}}

        # 0/1 背包动态规划：在预算内最大化 NPV
        # 注：方案之间假设互不冲突；如需冲突约束可在此扩展
        n = len(candidates)
        W = int(budget_limit)
        # dp[i][w] = 前 i 个方案、预算 w 时的最大 NPV
        dp = [[0.0] * (W + 1) for _ in range(n + 1)]
        keep = [[False] * (W + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            inv = candidates[i - 1]["investment"]
            npv = candidates[i - 1]["npv"]
            for w in range(W + 1):
                dp[i][w] = dp[i - 1][w]
                if w >= inv and dp[i - 1][w - inv] + npv > dp[i][w]:
                    dp[i][w] = dp[i - 1][w - inv] + npv
                    keep[i][w] = True

        # 回溯找出选中的方案
        selected = []
        w = W
        for i in range(n, 0, -1):
            if keep[i][w]:
                selected.append(candidates[i - 1])
                w -= candidates[i - 1]["investment"]
        selected.reverse()

        total_inv = sum(s["investment"] for s in selected)
        total_npv = sum(s["npv"] for s in selected)
        total_saving = sum(s["annual_saving_cost_yuan"] for s in selected)
        total_carbon = sum(s["annual_carbon_reduction_kg"] for s in selected)
        avg_roi = (sum(s["roi_pct"] for s in selected) / len(selected)) if selected else 0

        # 未选中的方案（按 NPV 降序）
        selected_ids = {s["scenario_id"] for s in selected}
        not_selected = [c for c in candidates if c["scenario_id"] not in selected_ids]
        not_selected.sort(key=lambda x: x["npv"], reverse=True)

        return {
            "status": "success",
            "data": {
                "building": {"building_id": building_id, "building_name": building["building_name"]},
                "budget_limit_yuan": round(budget_limit, 2),
                "selected": selected,
                "not_selected": not_selected[:5],  # 前 5 个未选中
                "summary": {
                    "total_investment_yuan": round(total_inv, 2),
                    "budget_utilization_pct": round(total_inv / budget_limit * 100, 2),
                    "remaining_budget_yuan": round(budget_limit - total_inv, 2),
                    "total_npv_yuan": round(total_npv, 2),
                    "avg_roi_pct": round(avg_roi, 2),
                    "total_annual_saving_yuan": round(total_saving, 2),
                    "total_annual_carbon_kg": round(total_carbon, 2),
                    "selected_count": len(selected),
                },
                "recommendation": (
                    f"在预算 {round(budget_limit, 0)} 元内，"
                    f"推荐组合 {len(selected)} 个方案，"
                    f"总投资 {round(total_inv, 0)} 元，"
                    f"预算利用率 {round(total_inv / budget_limit * 100, 1)}%，"
                    f"预期 NPV {round(total_npv, 0)} 元。"
                ) if selected else f"当前预算 {budget_limit} 元不足以实施任何方案。",
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"组合优化失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "组合优化失败，请稍后重试"})


@router.get("/api/roi/history")
@run_in_thread
def roi_history(
    building_id: Optional[str] = Query(None, description="按建筑 ID 过滤"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """历史测算记录"""
    try:
        _init_table()
        where = "WHERE 1=1"
        params: list = []
        if building_id:
            where += " AND building_id = ?"
            params.append(building_id)

        offset = (page - 1) * page_size
        with get_conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sys_roi_scenarios {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT id, scenario_name, scenario_id, building_id,
                       params_json, result_json, created_at, created_by
                FROM sys_roi_scenarios
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

        items = []
        for r in rows:
            try:
                params_obj = json.loads(r["params_json"]) if r["params_json"] else None
                result_obj = json.loads(r["result_json"]) if r["result_json"] else None
            except (json.JSONDecodeError, TypeError):
                params_obj, result_obj = None, None
            items.append({
                "id": int(r["id"]),
                "scenario_name": r["scenario_name"],
                "scenario_id": r["scenario_id"],
                "building_id": r["building_id"],
                "params": params_obj,
                "result": result_obj,
                "created_at": str(r["created_at"]) if r["created_at"] is not None else None,
                "created_by": r["created_by"],
            })

        return {
            "status": "success",
            "data": items,
            "total": int(total),
            "page": page,
            "page_size": page_size,
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"查询 ROI 历史记录失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "查询历史记录失败，请稍后重试"})


@router.post("/api/roi/save")
@run_in_thread
def roi_save(payload: ROISaveRequest):
    """保存测算方案"""
    try:
        _init_table()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO sys_roi_scenarios
                    (scenario_name, scenario_id, building_id, params_json, result_json, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.scenario_name,
                    payload.scenario_id,
                    payload.building_id,
                    json.dumps(payload.params, ensure_ascii=False),
                    json.dumps(payload.result, ensure_ascii=False),
                    now_str,
                    payload.created_by,
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
            saved = conn.execute(
                "SELECT * FROM sys_roi_scenarios WHERE id = ?", [new_id]
            ).fetchone()

        return {
            "status": "success",
            "message": "测算方案已保存",
            "data": {
                "id": int(saved["id"]),
                "scenario_name": saved["scenario_name"],
                "scenario_id": saved["scenario_id"],
                "building_id": saved["building_id"],
                "params": payload.params,
                "result": payload.result,
                "created_at": str(saved["created_at"]),
                "created_by": saved["created_by"],
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"保存 ROI 测算方案失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "保存方案失败，请稍后重试"})
