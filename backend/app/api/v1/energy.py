# -*- coding: utf-8 -*-
"""
能耗预测路由
- /api/energy/forecast：基于 Prophet 的时序能耗预测（融合天气数据）

优化项：
1. 从数据库读取真实历史能耗（替代随机数）
2. Prophet 模型缓存（按小时 TTL，避免每次请求重训）
3. asyncio.to_thread 异步训练，不阻塞事件循环
4. slowapi 限流（防滥用）
5. Prophet 失败时降级为规则模型，响应中标记 data_source
"""
import math
import random
import datetime
import logging
import asyncio
import time

import httpx
import pandas as pd
from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_conn
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== Prophet 模型缓存 =====
# 结构：{"cache_key": {"model": Prophet, "fitted_at": timestamp, "df_history": DataFrame}}
# TTL：1 小时（3600 秒），超时后下次请求重新训练
_MODEL_CACHE: dict = {}
_MODEL_CACHE_TTL = 3600  # 秒


def _fetch_real_history(hours: int = 168) -> pd.DataFrame:
    """
    从数据库 fact_energy_records 取最近 N 小时的真实能耗数据。
    按小时聚合（SUM + AVG），返回 Prophet 所需的 ds/y/temperature 格式。
    """
    try:
        with get_conn() as conn:
            # 按小时聚合：总能耗 + 平均 COP + 记录数
            df = pd.read_sql(
                """
                SELECT
                    strftime('%Y-%m-%d %H:00:00', monitor_time) AS hour_bucket,
                    SUM(elec_consumption) AS y,
                    AVG(cop) AS avg_cop,
                    COUNT(*) AS record_count
                FROM fact_energy_records
                WHERE monitor_time >= datetime('now', 'localtime', ?)
                GROUP BY hour_bucket
                ORDER BY hour_bucket
                """,
                conn,
                params=[f"-{hours} hours"],
            )

        if df.empty:
            logger.warning("数据库中无足够历史能耗数据，将使用规则模型降级")
            return pd.DataFrame()

        df["ds"] = pd.to_datetime(df["hour_bucket"])
        # 能耗值取总和（每小时聚合后的 kWh）
        df["y"] = df["y"].fillna(0).astype(float)
        logger.info(f"从数据库加载 {len(df)} 小时真实能耗数据")
        return df[["ds", "y"]]
    except Exception as e:
        logger.exception(f"获取历史能耗数据失败: {e}")
        return pd.DataFrame()


def _generate_rule_based_history(hours: int = 168) -> pd.DataFrame:
    """降级方案：当数据库无数据时，用规则模型生成历史能耗"""
    now = datetime.datetime.now()
    dates = [now - datetime.timedelta(hours=i) for i in range(hours, 0, -1)]
    y_values = []
    for d in dates:
        hour = d.hour
        if 8 <= hour <= 20:
            base = 150 + max(0, (25 - 20) * 15)
        else:
            base = 100
        noise = random.uniform(-10, 10)
        y_values.append(base + noise)
    return pd.DataFrame({"ds": dates, "y": y_values})


def _train_prophet_model(df_history: pd.DataFrame, future_temps: list, hours_to_predict: int):
    """
    训练 Prophet 模型并预测。
    返回 (forecast_df, model) 或抛出异常。
    """
    from prophet import Prophet

    m = Prophet(daily_seasonality=True, weekly_seasonality=True)
    m.fit(df_history)

    future = m.make_future_dataframe(periods=hours_to_predict, freq="h")
    forecast = m.predict(future)
    return forecast, m


@router.get("/api/energy/forecast")
@limiter.limit("10/minute")
async def forecast_energy(request: Request, hours_to_predict: int = 24):
    """
    能耗预测接口
    - 限流：10 次/分钟
    - 数据源优先级：数据库真实数据 > 规则模型降级
    - 模型缓存：1 小时 TTL
    """
    import math
    import random
    import pandas as pd

    # 默认坐标（福州）
    lat, lon = 26.02, 119.20
    city_name = "福建省福州市闽侯县"

    # 尝试获取真实 IP 定位
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"

    try:
        if client_ip and client_ip not in ("127.0.0.1", "::1", "localhost"):
            async with httpx.AsyncClient(timeout=3.0) as client:
                geo_resp = await client.get(f"http://ip-api.com/json/{client_ip}?lang=zh-CN")
                if geo_resp.status_code == 200 and geo_resp.json().get("status") == "success":
                    geo = geo_resp.json()
                    lat, lon = geo.get("lat", lat), geo.get("lon", lon)
                    city_name = geo.get("city", city_name)
    except Exception as e:
        logger.warning(f"IP 定位跳过: {e}")

    # ---------------- 获取天气数据（失败则 Mock） ----------------
    forecast_days = max(1, (hours_to_predict // 24) + 1)
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m&past_days=7&forecast_days={forecast_days}&timezone=Asia%2FSingapore"
    )

    weather_data = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(weather_url)
            if resp.status_code == 200:
                weather_data = resp.json()
                logger.info("真实天气数据获取成功")
            else:
                logger.warning(f"天气 API 返回 {resp.status_code}，使用 Mock 数据")
    except Exception as e:
        logger.warning(f"天气 API 请求异常: {e}，使用 Mock 数据")

    # 天气降级：生成模拟温度
    if weather_data is None:
        total_hours = 168 + forecast_days * 24
        base_temp = 22
        api_times = []
        api_temps = []
        now = datetime.datetime.now()
        for i in range(total_hours):
            dt = now - datetime.timedelta(hours=168 - i)
            api_times.append(dt.strftime("%Y-%m-%dT%H:00:00"))
            hour_of_day = dt.hour
            daily_var = 8 * math.sin(math.pi * (hour_of_day - 14) / 12)
            noise = random.uniform(-1.5, 1.5)
            temp = base_temp + daily_var + noise
            api_temps.append(round(temp, 1))
        weather_data = {"hourly": {"time": api_times, "temperature_2m": api_temps}}
        logger.info("已启用模拟天气数据")

    api_times = weather_data["hourly"]["time"]
    api_temps = weather_data["hourly"]["temperature_2m"]
    api_temps = [
        api_temps[i] if api_temps[i] is not None else (api_temps[i - 1] if i > 0 else 20)
        for i in range(len(api_temps))
    ]

    future_temps = api_temps[168 : 168 + hours_to_predict]

    # ---------------- 获取历史能耗数据（真实 > 降级） ----------------
    data_source = "real_db"
    df_history = _fetch_real_history(hours=168)

    if df_history.empty:
        # 降级：规则模型生成
        df_history = _generate_rule_based_history(hours=168)
        data_source = "rule_based_degraded"
        logger.warning("历史能耗数据降级为规则模型")

    # ---------------- Prophet 训练（缓存 + 异步 + 降级） ----------------
    cache_key = f"prophet_v1_{datetime.datetime.now().strftime('%Y%m%d_%H')}"
    cached = _MODEL_CACHE.get(cache_key)
    forecast = None
    model_status = "cached"

    if cached and (time.time() - cached["fitted_at"]) < _MODEL_CACHE_TTL:
        # 命中缓存：用缓存的模型预测
        logger.info("命中 Prophet 模型缓存，跳过训练")
        try:
            cached_model = cached["model"]
            future = cached_model.make_future_dataframe(periods=hours_to_predict, freq="h")
            forecast = await asyncio.to_thread(cached_model.predict, future)
        except Exception as e:
            logger.exception(f"缓存模型预测失败: {e}")
            cached = None  # 失败则重新训练

    if forecast is None:
        model_status = "freshly_trained"
        try:
            # 异步训练 Prophet（不阻塞事件循环）
            forecast, model = await asyncio.to_thread(
                _train_prophet_model, df_history, future_temps, hours_to_predict
            )
            # 写入缓存
            _MODEL_CACHE[cache_key] = {
                "model": model,
                "fitted_at": time.time(),
                "df_history": df_history,
            }
            # 清理过期缓存
            _cleanup_expired_cache()
            logger.info("Prophet 模型训练完成并缓存")
        except Exception as e:
            # 最终降级：规则模型直接预测
            logger.exception(f"Prophet 训练失败，降级为规则模型: {e}")
            model_status = "rule_fallback"
            data_source = f"rule_fallback: {e}"
            forecast = _rule_based_forecast(df_history, future_temps, hours_to_predict)

    # ---------------- 组装返回数据 ----------------
    history_data = df_history.tail(24 * 3).copy()
    # 🌟 修复：为历史数据补齐温度字段，避免前端 item.temperature.toFixed 崩溃
    # 取与历史等长的过去天气温度（api_temps 前 168 小时为历史）
    history_len = len(history_data)
    past_temps = api_temps[-history_len:] if len(api_temps) >= history_len else api_temps
    if len(past_temps) < history_len:
        past_temps = [20.0] * (history_len - len(past_temps)) + list(past_temps)
    history_data["temperature"] = past_temps[-history_len:]
    history_data["ds"] = history_data["ds"].dt.strftime("%Y-%m-%d %H:%M:%S")

    forecast_tail = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(hours_to_predict).copy()
    forecast_tail["temperature"] = future_temps
    forecast_tail["ds"] = forecast_tail["ds"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "status": "success",
        "meta": {
            "location": city_name,
            "lat": lat,
            "lon": lon,
            "data_source": data_source,
            "model_status": model_status,
            "cache_ttl_seconds": _MODEL_CACHE_TTL,
        },
        "data": {
            "history": history_data.to_dict(orient="records"),
            "forecast": forecast_tail.to_dict(orient="records"),
        },
    }


def _rule_based_forecast(df_history: pd.DataFrame, future_temps: list, hours_to_predict: int):
    """最终降级：基于历史均值 + 温度修正的规则预测"""
    import pandas as pd

    history_mean = df_history["y"].mean()
    history_std = df_history["y"].std()

    now = datetime.datetime.now()
    future_dates = [now + datetime.timedelta(hours=i + 1) for i in range(hours_to_predict)]

    yhat = []
    yhat_lower = []
    yhat_upper = []
    for i, dt in enumerate(future_dates):
        hour = dt.hour
        temp = future_temps[i] if i < len(future_temps) else 22
        if 8 <= hour <= 20:
            base = history_mean * 1.2 + max(0, (temp - 20) * 5)
        else:
            base = history_mean * 0.7
        yhat.append(base)
        yhat_lower.append(base - history_std)
        yhat_upper.append(base + history_std)

    return pd.DataFrame(
        {
            "ds": future_dates,
            "yhat": yhat,
            "yhat_lower": yhat_lower,
            "yhat_upper": yhat_upper,
        }
    )


def _cleanup_expired_cache():
    """清理过期的模型缓存，防止内存泄漏"""
    now = time.time()
    expired_keys = [k for k, v in _MODEL_CACHE.items() if (now - v["fitted_at"]) > _MODEL_CACHE_TTL * 2]
    for k in expired_keys:
        del _MODEL_CACHE[k]
        logger.info(f"清理过期 Prophet 缓存: {k}")
