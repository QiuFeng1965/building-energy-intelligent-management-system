# -*- coding: utf-8 -*-
"""
异常检测与根因分析（RCA）路由
- /api/anomaly/detect：基于 Isolation Forest 的时序异常检测
- /api/anomaly/root_cause/{device_id}：基于 SHAP 的根因归因分析
- /api/anomaly/recent：最近 24h 异常事件列表

设计要点：
1. 复用 fact_energy_records 真实数据，无需额外采集
2. Isolation Forest 模型按 building_type 分组缓存（1h TTL）
3. SHAP 解释器对异常样本做特征归因，输出根因链
4. 全程异步（asyncio.to_thread），不阻塞事件循环
"""
import asyncio
import time
import json
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request
from slowapi.errors import RateLimitExceeded

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== Isolation Forest 模型缓存 =====
# 结构：{"building_type": {"model": if, "fitted_at": ts, "features": [...]}}
_IF_CACHE: dict = {}
_IF_CACHE_TTL = 3600  # 1 小时


# ===== 特征工程：从原始记录构造异常检测特征 =====
ANOMALY_FEATURES = [
    "elec_consumption", "cop", "supply_temp", "return_temp",
    "delta_temp", "system_pressure_diff", "current_unbalance",
    "condensing_water_temp", "loading_rate",
]


def _fetch_recent_records(hours: int = 24, building_type: Optional[str] = None) -> pd.DataFrame:
    """从数据库取最近 N 小时的运行记录"""
    try:
        with get_conn() as conn:
            sql = """
                SELECT monitor_time, device_id, device_name, building_type, param_type,
                       elec_consumption, cop, supply_temp, return_temp, delta_temp,
                       system_pressure_diff, current_unbalance, condensing_water_temp,
                       loading_rate, run_status, fault_code
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', ?)
            """
            params = [f"-{hours} hours"]
            if building_type and building_type != "ALL":
                sql += " AND building_type = ?"
                params.append(building_type)
            sql += " ORDER BY monitor_time DESC LIMIT 5000"
            df = pd.read_sql(sql, conn, params=params)
        return df
    except Exception as e:
        logger.exception(f"获取近 {hours}h 记录失败: {e}")
        return pd.DataFrame()


def _train_isolation_forest(df: pd.DataFrame):
    """训练 Isolation Forest，返回模型实例"""
    from sklearn.ensemble import IsolationForest

    # 取最近 7 天的正常样本作为训练集
    feature_df = df[ANOMALY_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0)
    if len(feature_df) < 50:
        # 样本不足，使用默认配置
        model = IsolationForest(
            n_estimators=80, contamination=0.05,
            random_state=42, n_jobs=-1
        )
    else:
        # 只用正常状态数据训练，让异常更显著
        normal_mask = df["run_status"] == "NORMAL"
        train_df = feature_df[normal_mask] if normal_mask.sum() >= 50 else feature_df
        model = IsolationForest(
            n_estimators=100, contamination=0.05,
            random_state=42, n_jobs=-1
        )
        model.fit(train_df)
    return model


def _get_or_train_model(building_type: str, df: pd.DataFrame):
    """按 building_type 获取缓存模型或重新训练"""
    cache_key = building_type or "ALL"
    cached = _IF_CACHE.get(cache_key)
    now = time.time()
    if cached and (now - cached["fitted_at"]) < _IF_CACHE_TTL:
        return cached["model"], "cached"
    model = _train_isolation_forest(df)
    _IF_CACHE[cache_key] = {"model": model, "fitted_at": now}
    # 清理过期缓存
    for k in list(_IF_CACHE.keys()):
        if (now - _IF_CACHE[k]["fitted_at"]) > _IF_CACHE_TTL * 2:
            del _IF_CACHE[k]
    return model, "freshly_trained"


def _shap_explain(model, sample_df: pd.DataFrame) -> list:
    """用 SHAP 解释异常样本的根因"""
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample_df)
        # 对每个样本，输出 top-3 贡献特征
        explanations = []
        for i in range(len(sample_df)):
            row_shap = shap_values[i]
            # 取绝对值最大的 3 个特征
            top_idx = row_shap.argsort()[-3:][::-1]
            causes = []
            for idx in top_idx:
                causes.append({
                    "feature": ANOMALY_FEATURES[idx],
                    "contribution": float(row_shap[idx]),
                    "current_value": float(sample_df.iloc[i][ANOMALY_FEATURES[idx]]),
                })
            explanations.append(causes)
        return explanations
    except ImportError:
        # SHAP 未安装时降级为基于规则的根因
        return _rule_based_explain(sample_df)
    except Exception as e:
        logger.warning(f"SHAP 解释失败，降级规则: {e}")
        return _rule_based_explain(sample_df)


def _rule_based_explain(sample_df: pd.DataFrame) -> list:
    """降级方案：基于阈值的规则归因"""
    results = []
    for _, row in sample_df.iterrows():
        causes = []
        if pd.notna(row["cop"]) and row["cop"] < 3.0:
            causes.append({"feature": "cop", "contribution": -0.5, "current_value": float(row["cop"])})
        if pd.notna(row["delta_temp"]) and (row["delta_temp"] < 3 or row["delta_temp"] > 8):
            causes.append({"feature": "delta_temp", "contribution": 0.3, "current_value": float(row["delta_temp"])})
        if pd.notna(row["current_unbalance"]) and row["current_unbalance"] > 5:
            causes.append({"feature": "current_unbalance", "contribution": 0.4, "current_value": float(row["current_unbalance"])})
        if pd.notna(row["system_pressure_diff"]) and abs(row["system_pressure_diff"]) > 0.3:
            causes.append({"feature": "system_pressure_diff", "contribution": 0.3, "current_value": float(row["system_pressure_diff"])})
        results.append(causes[:3])
    return results


# ===== 中文名映射 =====
_FEATURE_CN = {
    "elec_consumption": "耗电功率",
    "cop": "系统能效比",
    "supply_temp": "供水温度",
    "return_temp": "回水温度",
    "delta_temp": "供回水温差",
    "system_pressure_diff": "系统压差",
    "current_unbalance": "三相不平衡",
    "condensing_water_temp": "冷凝温度",
    "loading_rate": "负载率",
}


@router.get("/api/anomaly/detect")
@limiter.limit("20/minute")
async def detect_anomalies(
    request: Request,
    hours: int = 24,
    building_type: str = "ALL",
):
    """
    异常检测接口
    - 参数：hours=回看时长，building_type=建筑类型筛选
    - 返回：异常事件列表，含异常分数、根因链
    """
    df = await asyncio.to_thread(_fetch_recent_records, hours, building_type)
    if df.empty:
        return {"status": "success", "data": [], "total": 0, "message": "近时段无数据"}

    # 数值化
    feature_df = df[ANOMALY_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0)

    # 训练或取缓存模型
    bt_key = building_type if building_type != "ALL" else df["building_type"].iloc[0] if not df.empty else "ALL"
    model, model_status = await asyncio.to_thread(_get_or_train_model, bt_key, df)

    # 预测：1=正常，-1=异常
    predictions = await asyncio.to_thread(model.predict, feature_df)
    # 异常分数（越负越异常）
    scores = await asyncio.to_thread(model.decision_function, feature_df)

    df["is_anomaly"] = predictions
    df["anomaly_score"] = scores

    # 只保留异常样本
    anomaly_df = df[df["is_anomaly"] == -1].copy()
    if anomaly_df.empty:
        return {
            "status": "success",
            "data": [],
            "total": 0,
            "meta": {
                "model_status": model_status,
                "scanned": len(df),
                "anomaly_count": 0,
            },
        }

    # 取异常样本做 SHAP 归因
    anomaly_features = anomaly_df[ANOMALY_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0)
    explanations = await asyncio.to_thread(_shap_explain, model, anomaly_features)

    # 组装返回
    events = []
    for i, (_, row) in enumerate(anomaly_df.iterrows()):
        causes = explanations[i] if i < len(explanations) else []
        # 中文化根因
        causes_cn = [
            {
                "feature": c["feature"],
                "feature_cn": _FEATURE_CN.get(c["feature"], c["feature"]),
                "contribution": round(float(c["contribution"]), 4),
                "current_value": round(float(c["current_value"]), 2),
            }
            for c in causes
        ]
        # 安全转换：避免 NaN/Infinity 污染 JSON
        def _safe_float(v, ndigits=2):
            try:
                f = float(v)
                if math.isnan(f) or math.isinf(f):
                    return None
                return round(f, ndigits)
            except (TypeError, ValueError):
                return None
        import math
        events.append({
            "device_id": str(row["device_id"]),
            "device_name": str(row["device_name"]),
            "building_type": str(row["building_type"]),
            "param_type": str(row["param_type"]),
            "monitor_time": str(row["monitor_time"]),
            "anomaly_score": _safe_float(row["anomaly_score"], 4),
            "run_status": str(row["run_status"]),
            "fault_code": str(row["fault_code"]) if pd.notna(row["fault_code"]) else None,
            "key_metrics": {
                "cop": _safe_float(row["cop"], 2),
                "elec_consumption": _safe_float(row["elec_consumption"], 2),
                "delta_temp": _safe_float(row["delta_temp"], 2),
            },
            "root_causes": causes_cn,
            "suggestion": _generate_suggestion(causes_cn),
        })

    # 按异常分数排序（越负越严重，None 排到最后）
    events.sort(key=lambda x: (x["anomaly_score"] is None, x["anomaly_score"] if x["anomaly_score"] is not None else 0))

    return {
        "status": "success",
        "data": events[:100],  # 限制返回数量
        "total": len(events),
        "meta": {
            "model_status": model_status,
            "scanned": len(df),
            "anomaly_count": len(events),
            "anomaly_rate": round(len(events) / max(1, len(df)) * 100, 2),
        },
    }


def _generate_suggestion(causes: list) -> str:
    """根据根因特征生成处置建议"""
    if not causes:
        return "建议加强巡检频次"
    top = causes[0]
    f = top["feature"]
    v = top["current_value"]
    if f == "cop" and v < 3.0:
        return f"⚠️ COP={v} 严重偏低，建议立即检查制冷剂充注量与冷凝器结垢情况"
    if f == "cop" and v < 3.5:
        return f"COP={v} 略低于基准，建议两周内安排深度维保"
    if f == "delta_temp":
        if v < 3:
            return f"温差仅 {v}℃，疑似流量过大或负荷过低，建议调整水泵频率"
        return f"温差达 {v}℃，疑似换热不良，建议清洗换热器"
    if f == "current_unbalance" and v > 5:
        return f"三相不平衡 {v}%，建议核查接触器与电机绝缘"
    if f == "system_pressure_diff" and abs(v) > 0.3:
        return f"系统压差异常 {v}，建议检查水泵扬程与阀门开度"
    if f == "condensing_water_temp" and v > 35:
        return f"冷凝温度 {v}℃ 偏高，建议检查冷却塔风机与填料"
    if f == "loading_rate" and v < 30:
        return f"负载率仅 {v}%，建议停机或并入台数控制"
    return "建议结合运行工况综合研判"


@router.get("/api/anomaly/root_cause/{device_id}")
@limiter.limit("20/minute")
async def root_cause_analysis(
    request: Request,
    device_id: str,
    hours: int = 48,
):
    """
    针对单个设备的根因分析
    - 取该设备近 hours 小时所有记录
    - 对每条记录做异常检测 + SHAP 归因
    - 输出异常时间线和根因链
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT monitor_time, device_id, device_name, building_type, param_type,
                       elec_consumption, cop, supply_temp, return_temp, delta_temp,
                       system_pressure_diff, current_unbalance, condensing_water_temp,
                       loading_rate, run_status, fault_code
                FROM fact_energy_records
                WHERE device_id = ? AND monitor_time >= datetime('now', 'localtime', ?)
                ORDER BY monitor_time ASC
                """,
                conn,
                params=[device_id, f"-{hours} hours"],
            )
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "根因分析查询")

    if df.empty:
        return {"status": "success", "data": None, "message": "该设备近期无运行数据"}

    # 训练或取缓存
    bt = df["building_type"].iloc[0]
    model, model_status = await asyncio.to_thread(_get_or_train_model, bt, df)

    feature_df = df[ANOMALY_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0)
    predictions = await asyncio.to_thread(model.predict, feature_df)
    scores = await asyncio.to_thread(model.decision_function, feature_df)
    df["is_anomaly"] = predictions
    df["anomaly_score"] = scores

    # 对异常样本做 SHAP
    anomaly_mask = df["is_anomaly"] == -1
    if anomaly_mask.any():
        anomaly_features = feature_df[anomaly_mask]
        explanations = await asyncio.to_thread(_shap_explain, model, anomaly_features)
    else:
        explanations = []

    # 构造时间线
    timeline = []
    exp_idx = 0
    for i, (_, row) in enumerate(df.iterrows()):
        item = {
            "time": str(row["monitor_time"]),
            "is_anomaly": bool(row["is_anomaly"] == -1),
            "score": round(float(row["anomaly_score"]), 4),
            "cop": float(row["cop"]) if pd.notna(row["cop"]) else None,
            "elec_consumption": float(row["elec_consumption"]) if pd.notna(row["elec_consumption"]) else None,
            "run_status": str(row["run_status"]),
        }
        if item["is_anomaly"] and exp_idx < len(explanations):
            causes = explanations[exp_idx]
            exp_idx += 1
            item["root_causes"] = [
                {
                    "feature": c["feature"],
                    "feature_cn": _FEATURE_CN.get(c["feature"], c["feature"]),
                    "contribution": round(c["contribution"], 4),
                    "current_value": round(c["current_value"], 2),
                }
                for c in causes
            ]
        timeline.append(item)

    # 统计汇总
    anomaly_count = int(anomaly_mask.sum())
    summary = {
        "device_id": device_id,
        "device_name": str(df["device_name"].iloc[0]),
        "total_records": len(df),
        "anomaly_count": anomaly_count,
        "anomaly_rate": round(anomaly_count / max(1, len(df)) * 100, 2),
        "first_anomaly_time": str(df.loc[anomaly_mask, "monitor_time"].iloc[0]) if anomaly_count > 0 else None,
        "worst_score": round(float(df["anomaly_score"].min()), 4) if len(df) > 0 else None,
        "model_status": model_status,
    }

    return {
        "status": "success",
        "data": {
            "summary": summary,
            "timeline": timeline,
        },
    }


@router.get("/api/anomaly/recent")
@run_in_thread
def recent_anomalies(hours: int = 24, limit: int = 20):
    """最近异常事件列表（轻量版，仅返回 run_status != NORMAL 的记录）"""
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT monitor_time, device_id, device_name, building_type, param_type,
                       elec_consumption, cop, delta_temp, run_status, fault_code
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', ?)
                  AND run_status != 'NORMAL'
                ORDER BY monitor_time DESC
                LIMIT ?
                """,
                conn,
                params=[f"-{hours} hours", limit],
            )
        if df.empty:
            return {"status": "success", "data": [], "total": 0}
        # 清洗 NaN/Infinity（JSON 不兼容）
        df = df.replace([float('inf'), float('-inf')], None)
        df = df.where(pd.notnull(df), None)
        # 安全序列化
        records = json.loads(df.to_json(orient="records", date_format="iso"))
        return {
            "status": "success",
            "data": records,
            "total": len(records),
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "最近异常列表查询")
