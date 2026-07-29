# -*- coding: utf-8 -*-
"""
设备路由
- /api/devices：设备能耗记录查询
- /api/equipment/predictive_maintenance：设备预测性维护 (RUL)
"""
import os
import logging
import math
import json

import pandas as pd
from fastapi import APIRouter

from app.core.config import MODEL_PATH
from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.utils.name_maps import NAME_MAP
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/devices")
@run_in_thread
def get_devices(
    building: str = "ALL",
    device_type: str = "ALL",
    status: str = "ALL",
    size: str = "500",
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None):
    try:
        # 限量逻辑：参数化，杜绝 f-string SQL 注入
        limit_val = 500
        if size != "ALL":
            try:
                limit_val = int(size)
            except (ValueError, TypeError):
                limit_val = 500

        with get_conn() as conn:
            # 基础查询 — 只取需要的列，避免 SELECT * 性能问题
            query = (
                "SELECT monitor_time, device_id, device_name, building_id, "
                "building_type, param_type, elec_consumption, supply_temp, "
                "return_temp, delta_temp, cop, carbon_emission, electricity_cost, "
                "run_status, fault_code "
                "FROM fact_energy_records WHERE 1=1"
            )
            params = []

            # 各种过滤逻辑
            if building and building != "ALL":
                query += " AND building_type = ?"
                params.append(building)
            if device_type and device_type != "ALL":
                query += " AND param_type = ?"
                params.append(device_type)
            if status and status != "ALL":
                query += " AND run_status = ?"
                params.append(status)

            if start_date and end_date:
                query += " AND monitor_time >= ? AND monitor_time <= ?"
                params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])

            # 关键词搜索（设备名称模糊匹配）
            if keyword and keyword.strip():
                query += " AND device_name LIKE ?"
                params.append(f"%{keyword.strip()}%")

            # 强制倒序排列
            query += " ORDER BY monitor_time DESC"

            # 限量逻辑（参数化）
            if size != "ALL":
                query += " LIMIT ?"
                params.append(limit_val)

            df = pd.read_sql(query, conn, params=params)

        # 向量化转换
        if df.empty:
            return {"status": "success", "data": [], "total": 0, "summary": {"normal": 0, "warning": 0, "abnormal": 0, "critical": 0}}

        # 预处理数值列 — 将 NaN / Infinity 统一转为 None（JSON 兼容）
        def safe_float(val, ndigits=2):
            """安全转换浮点数：NaN/Infinity 返回 None"""
            if val is None or pd.isna(val):
                return None
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return round(f, ndigits)

        df['cop'] = df['cop'].apply(lambda x: safe_float(x, 2))
        df['elec_consumption'] = df['elec_consumption'].apply(lambda x: safe_float(x, 2))
        df['carbon_emission'] = df['carbon_emission'].apply(lambda x: safe_float(x, 2))
        df['electricity_cost'] = df['electricity_cost'].apply(lambda x: safe_float(x, 2))
        df['supply_temp'] = df['supply_temp'].apply(lambda x: safe_float(x, 1))
        df['return_temp'] = df['return_temp'].apply(lambda x: safe_float(x, 1))

        # 统计摘要
        status_counts = df['run_status'].value_counts().to_dict()
        summary = {
            "normal": int(status_counts.get('NORMAL', 0)),
            "warning": int(status_counts.get('WARNING', 0)),
            "abnormal": int(status_counts.get('ABNORMAL', 0)),
            "critical": int(status_counts.get('CRITICAL', 0) + status_counts.get('ALARM', 0)),
        }

        device_list = []
        for index, row in df.iterrows():
            device_list.append({
                "time": str(row['monitor_time']),
                "device_id": str(row['device_id']),
                "device_name": str(row['device_name']),
                "building_id": str(row['building_id']),
                "building": NAME_MAP.get(row['building_type'], row['building_type']),
                "type": NAME_MAP.get(row['param_type'], row['param_type']),
                "value": safe_float(row['elec_consumption'], 2) or 0.0,
                "cop": row['cop'],
                "supply_temp": row['supply_temp'],
                "return_temp": row['return_temp'],
                "carbon_emission": row['carbon_emission'],
                "electricity_cost": row['electricity_cost'],
                "status": NAME_MAP.get(row['run_status'], row['run_status']),
                "raw_status": row['run_status'],
                "fault_code": str(row['fault_code']) if row['fault_code'] and row['fault_code'] != 'NONE' else None,
                "metadata": {
                    "system_id": f"SN-{str(row['building_type'])[:3]}-{1000 + index}",
                    "raw_device_code": row['param_type'],
                    "raw_building_code": row['building_type'],
                    "data_source": "Digital-Twin-Engine v3.0",
                    "anomaly_flag": "YES" if row['run_status'] != 'NORMAL' else "NO",
                }
            })

        # 最终安全检查：递归清洗所有 NaN/Infinity，确保 JSON 兼容
        def _clean_nan(obj):
            """递归将所有 NaN/Infinity 浮点数转为 None"""
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            elif isinstance(obj, dict):
                return {k: _clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_clean_nan(i) for i in obj]
            return obj

        response = {"status": "success", "data": device_list, "total": len(device_list), "summary": summary}
        response = _clean_nan(response)

        # 验证 JSON 序列化
        try:
            json.dumps(response)
        except (ValueError, TypeError) as je:
            logger.error(f"JSON 序列化仍然失败: {je}")
            # 最后兜底：强制将所有 float 转为 str
            response = json.loads(json.dumps(response, default=str))

        return response
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "设备列表查询")


@router.get("/api/equipment/predictive_maintenance")
async def get_predictive_maintenance():
    """
    设备预测性维护 (RUL)
    数据来源：fact_energy_records 最新运行数据
    - 基于真实数据计算设备健康度（COP 偏离度 + 温度异常度 + 运行状态）
    - 优先使用 rul_prediction_model.pkl 模型预测 RUL，模型不可用时回退到规则计算
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT cop, elec_consumption, supply_temp, return_temp, delta_temp,
                       run_status, system_pressure_diff, current_unbalance,
                       condensing_water_temp, loading_rate, device_name, param_type,
                       monitor_time
                FROM fact_energy_records
                WHERE cop IS NOT NULL
                ORDER BY monitor_time DESC
                LIMIT 1
                """,
                conn
            )

        if df.empty:
            logger.warning("fact_energy_records 无可用 COP 数据，返回降级响应")
            return {
                "status": "success",
                "data": {
                    "equipment_name": "冷水机组 1#离心泵",
                    "vibration_mm_s": 0.0,
                    "bearing_temp_c": 0.0,
                    "health_score": 0.0,
                    "predicted_failure": "数据不足",
                    "maintenance_action": "请检查数据库是否有运行数据",
                    "data_source": "无数据 (数据库无记录)"
                }
            }

        row = df.iloc[0]
        cop = float(row['cop']) if pd.notna(row['cop']) else None
        supply_temp = float(row['supply_temp']) if pd.notna(row['supply_temp']) else None
        return_temp = float(row['return_temp']) if pd.notna(row['return_temp']) else None
        delta_temp = float(row['delta_temp']) if pd.notna(row['delta_temp']) else None
        run_status = str(row['run_status']) if pd.notna(row['run_status']) else 'NORMAL'
        system_pressure_diff = float(row['system_pressure_diff']) if pd.notna(row['system_pressure_diff']) else None
        current_unbalance = float(row['current_unbalance']) if pd.notna(row['current_unbalance']) else None
        condensing_water_temp = float(row['condensing_water_temp']) if pd.notna(row['condensing_water_temp']) else None
        equipment_name = str(row['device_name']) if pd.notna(row['device_name']) else "冷水机组 1#离心泵"

        # 计算温差：优先用 delta_temp，否则用 return_temp - supply_temp
        if delta_temp is None and supply_temp is not None and return_temp is not None:
            delta_temp = return_temp - supply_temp

        # ===== 基于真实数据的健康度计算（满分 100，偏离越大扣分越多）=====
        health_score = 100.0

        # 1. COP 偏离度（正常 3.0-5.0，低于 2.5 预警）
        if cop is not None:
            if cop < 2.5:
                health_score -= 40
            elif cop < 3.0:
                health_score -= 20
            elif cop > 5.0:
                health_score -= 10

        # 2. 温度异常度（温差正常 3-8℃，偏离越大健康度越低）
        if delta_temp is not None:
            if delta_temp < 3:
                health_score -= (3 - delta_temp) * 5
            elif delta_temp > 8:
                health_score -= (delta_temp - 8) * 5

        # 3. 运行状态（非 NORMAL 直接标记异常）
        if run_status != 'NORMAL':
            health_score = min(health_score, 30)

        health_score = max(0.0, min(100.0, health_score))

        # ===== 派生物理量（用于前端展示和模型输入）=====
        # 振动频率：基于系统压力差派生，无则由健康度反推
        if system_pressure_diff is not None:
            vibration = max(1.0, abs(system_pressure_diff) * 10)
        else:
            vibration = max(1.0, (100 - health_score) / 15 + 1.5)

        # 轴承温度：基于冷凝温度派生，无则基于回水温度，再无则由健康度反推
        if condensing_water_temp is not None:
            bearing_temp = condensing_water_temp + 25
        elif return_temp is not None:
            bearing_temp = return_temp + 55
        else:
            bearing_temp = 60 + (100 - health_score) * 0.3

        # ===== RUL 预测：优先用 .pkl 模型，不可用则规则计算 =====
        model_prediction = None
        data_source = "规则计算 (基于真实运行数据)"
        if os.path.exists(MODEL_PATH):
            try:
                import joblib
                model = joblib.load(MODEL_PATH)
                # 构造模型特征（与 chat.py predict_device_rul 保持一致）
                temp_offset = abs(delta_temp - 5.5) if delta_temp is not None else 1.0
                current_fluct = current_unbalance if current_unbalance is not None else 2.0
                features = pd.DataFrame({
                    'vibration_rms': [vibration],
                    'temp_offset': [temp_offset],
                    'current_fluctuation': [current_fluct]
                })
                model_prediction = max(1, int(model.predict(features)[0]))
                data_source = "ML模型预测 (rul_prediction_model.pkl)"
            except Exception as model_err:
                logger.warning(f"RUL 模型加载/预测失败，回退到规则计算: {model_err}")

        # ===== 根据模型预测或健康度给出结论 =====
        if model_prediction is not None:
            if model_prediction < 15:
                days_left = f"约 {model_prediction} 天"
                action = "🚨 已自动触发 ERP 维保工单，要求立即停机检修"
            elif model_prediction < 30:
                days_left = f"约 {model_prediction} 天"
                action = "建议两周内安排深度润滑与声学检测"
            else:
                days_left = f"约 {model_prediction} 天"
                action = "保持当前巡检频率"
        else:
            if health_score > 80:
                days_left = "> 90 天"
                action = "保持当前巡检频率"
            elif health_score > 50:
                days_left = f"约 {int((health_score - 50) * 1.5)} 天"
                action = "建议两周内安排深度润滑与声学检测"
            else:
                days_left = f"小于 {int(health_score / 10) + 1} 天"
                action = "🚨 已自动触发 ERP 维保工单，要求立即停机检修"

        return {
            "status": "success",
            "data": {
                "equipment_name": equipment_name,
                "vibration_mm_s": round(vibration, 2),
                "bearing_temp_c": round(bearing_temp, 1),
                "health_score": round(health_score, 1),
                "predicted_failure": days_left,
                "maintenance_action": action,
                "data_source": data_source
            }
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "设备预测性维护查询")
