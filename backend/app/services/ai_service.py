# -*- coding: utf-8 -*-
"""
AI / LLM 服务层
- 初始化 AsyncOpenAI 客户端
- 提供 Tool Calling 所需的本地函数：设备查询/控制、SQL 沙箱执行、天气、故障手册、报告触发
"""
import os
import json
import logging
import datetime
import asyncio

import pandas as pd
import sqlglot
import httpx
from sqlglot.expressions import Select
from openai import AsyncOpenAI

from app.core.config import (
    AI_API_KEY,
    AI_BASE_URL,
    MODEL_TEXT,
    MODEL_VISION,
    LLM_TIMEOUT,
    LLM_TOTAL_TIMEOUT,
    LLM_FALLBACK_REPLY,
)
from app.core.database import get_conn

logger = logging.getLogger(__name__)

# 初始化 AI 客户端（密钥与 base_url 来自配置中心，设置超时避免无限挂起）
ai_client = AsyncOpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
    timeout=LLM_TIMEOUT,        # 单次请求超时（秒）
    max_retries=2,              # SDK 内部重试次数（含首次共 3 次）
)

# 天气 API 异步客户端（替代同步 urllib，避免阻塞事件循环）
_weather_client = httpx.AsyncClient(timeout=3.0, limits=httpx.Limits(max_connections=50))


def get_device_status(device_name: str) -> str:
    """【巡检员工具】查询设备最新真实状态（从 fact_energy_records 最新一条记录）"""
    logger.info(f"⚙️ [巡检] 查询设备状态: {device_name}")
    try:
        with get_conn() as conn:
            # 模糊匹配设备名，取最近一条记录
            df = pd.read_sql(
                "SELECT device_name, run_status, cop, elec_consumption, "
                "supply_temp, return_temp, fault_code, monitor_time "
                "FROM fact_energy_records "
                "WHERE device_name LIKE ? "
                "ORDER BY monitor_time DESC LIMIT 1",
                conn, params=[f"%{device_name}%"]
            )
        if df.empty:
            return f"⚠️ 未在数据库中找到设备「{device_name}」的任何记录，请确认设备名称。"

        row = df.iloc[0]
        status_map = {
            "NORMAL": "🟢 正常运行",
            "ABNORMAL": "🟡 异常",
            "WARNING": "🟠 预警",
            "CRITICAL": "🔴 危急",
            "ALARM": "🔴 告警"
        }
        status_text = status_map.get(str(row['run_status']), str(row['run_status']))
        result = (
            f"📊 设备「{row['device_name']}」实时状态快照（采集时间 {row['monitor_time']}）：\n"
            f"- 运行状态：{status_text}\n"
            f"- 实时 COP：{row['cop']}\n"
            f"- 瞬时功耗：{row['elec_consumption']} kWh\n"
            f"- 供水温度：{row['supply_temp']}℃ / 回水温度：{row['return_temp']}℃\n"
        )
        if row['fault_code']:
            result += f"- ⚠️ 故障代码：{row['fault_code']}\n"
        return result
    except Exception as e:
        logger.exception(f"查询设备状态失败: {e}")
        return f"🔥 查询设备状态时数据库异常: {e}"


def control_device(target: str, action: str) -> str:
    """【控制员工具】向设备下发控制指令（写入 fact_work_orders 工单表，形成审计轨迹）"""
    logger.info(f"⚙️ [控制] 目标={target}, 动作={action}")
    try:
        with get_conn() as conn:
            # 查找目标设备（dim_devices 实际列名）
            df = pd.read_sql(
                "SELECT device_id, device_name FROM dim_devices "
                "WHERE device_name LIKE ? LIMIT 1",
                conn, params=[f"%{target}%"]
            )
            if df.empty:
                return f"⚠️ 未找到设备「{target}」，无法下发指令。请确认设备名称。"

            device = df.iloc[0]
            # 生成工单号
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            order_id = f"WO-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            # 写入工单表（列名与 fact_work_orders 实际 schema 对齐）
            conn.execute(
                "INSERT INTO fact_work_orders "
                "(order_id, device_id, anomaly_time, diagnosis_title, maintenance_action, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'PENDING', ?)",
                (
                    order_id,
                    device['device_id'],
                    now_str,
                    f"AI 下发控制指令: {action}",
                    action,
                    now_str,
                )
            )
            conn.commit()

            # 记录审计日志（高危操作）
            try:
                from app.api.v1.admin import write_audit_log
                write_audit_log(
                    user="ai_agent",
                    action="设备控制指令下发",
                    detail=f"设备: {device['device_name']}, 指令: {action}, 工单: {order_id}",
                    risk_level="high",
                )
            except Exception:
                pass  # 审计日志失败不影响主流程

        return (
            f"✅【指令已下发】已对设备「{device['device_name']}」({device['device_id']}) "
            f"执行「{action}」操作。\n"
            f"工单号：{order_id}\n"
            f"状态：PENDING（等待现场执行）\n"
            f"工单已写入审计轨迹表，可在管理后台查询。"
        )
    except Exception as e:
        logger.exception(f"控制设备失败: {e}")
        return "🔥 设备控制指令下发失败，请稍后重试"


# ================= Data Analyst Agent (数据分析智能体 - 核心沙箱) =================
def execute_sql_query(sql_query: str) -> str:
    logger.info(f"📊 [Data Analyst] 接收 SQL 任务: {sql_query[:400]}")  # 限制打印长度

    try:
        # ==================== SQL 清洗 + 方言转换 + 安全校验 ====================
        # 1. 清洗大模型可能输出的 markdown 代码块
        if "```sql" in sql_query:
            clean_sql = sql_query.split("```sql")[-1].split("```")[0].strip()
        elif "```" in sql_query:
            clean_sql = sql_query.split("```")[-2].strip()
        else:
            clean_sql = sql_query.strip()

        # 2. 使用 sqlglot 进行方言转换（转成标准 SQLite 语法）
        transpiled_sql = sqlglot.transpile(clean_sql, read=None, write="sqlite")[0]

        logger.debug(f"[SQL 转换] 最终执行语句: {transpiled_sql}")

        # 3. 解析 AST 并进行安全检查
        parsed_query = sqlglot.parse_one(transpiled_sql, read="sqlite")

        if not isinstance(parsed_query, Select):
            logger.warning("[沙箱拦截] 非 SELECT 语句")
            return "🚨 [系统拒绝] 严重违规！Data Analyst 仅拥有只读权限，禁止执行任何修改、删除或建表操作。"

        # 11 张专业表白名单
        allowed_tables = {
            "fact_work_orders", "sys_agent_memory", "fact_energy_records",
            "fact_environment_factors", "fact_new_energy", "fact_weather_forecasts",
            "dim_devices", "dim_spaces", "dim_buildings", "dim_tariffs", "dim_carbon_factors"
        }

        found_tables = {table.name.lower() for table in parsed_query.find_all(sqlglot.expressions.Table)}
        illegal_tables = found_tables - allowed_tables

        if illegal_tables:
            logger.warning(f"[沙箱拦截] 越权表: {illegal_tables}")
            return f"🚨 [系统拒绝] 越权访问！你只能查询以下表：{allowed_tables}。\n非法目标: {illegal_tables}。"

    except sqlglot.errors.ParseError as e:
        logger.exception(f"SQL 语法解析失败: {e}")
        return "⚠️ [SQL 语法错误] 大模型生成的 SQL 无法解析，请自我纠错。"
    except Exception as e:
        logger.exception(f"SQL 转换或校验异常: {e}")
        return "⚠️ [SQL 转换或校验异常] 请检查生成的语句是否正确。"

    # ==================== 执行查询阶段 ====================
    logger.info("[沙箱校验通过] 允许执行查询")

    try:
        with get_conn() as conn:
            df = pd.read_sql_query(transpiled_sql, conn)   # 用转换后的 transpiled_sql

        if df.empty:
            return "✅ 查询执行成功，但数据库中没有符合条件的数据记录。⚠️ 严厉警告：你必须直接如实告诉用户“底层数据库中没有该条件的数据”，【绝不允许】自行伪造、瞎编任何数字，否则将被判定为严重违规！"

        if len(df) > 30:
            df_truncated = df.head(30)
            return f"✅ 查询成功！(为防止记忆溢出，仅展示前 30 条核心数据): {df_truncated.to_json(orient='records', force_ascii=False)}"

        return f"✅ 查询成功，获取到真实底层数据: {df.to_json(orient='records', force_ascii=False)}"

    except Exception as e:
        logger.exception(f"数据库执行异常: {e}")
        return "🔥 数据库执行时报错，请根据数据库 Schema 重新生成 SQL。"


async def fetch_weather(date_str: str) -> str:
    """【必杀技1】气象多模态融合查询 - 调用 open-meteo 真实 API"""
    logger.info(f"🌤️ [天气] 查询日期: {date_str}")
    try:
        # 复用 energy.py 同款的 open-meteo 历史天气 API（福州 26.07°N 119.30°E）
        # open-meteo archive API
        url = (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude=26.07&longitude=119.30"
            f"&start_date={date_str}&end_date={date_str}"
            "&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean"
            "&timezone=Asia/Shanghai"
        )
        resp = await _weather_client.get(url, headers={"User-Agent": "Qingyi/1.0"})
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        t_max = daily.get("temperature_2m_max", [None])[0]
        t_min = daily.get("temperature_2m_min", [None])[0]
        humidity = daily.get("relative_humidity_2m_mean", [None])[0]

        if t_max is None:
            return f"⚠️ open-meteo 未返回 {date_str} 的天气数据（可能日期超出范围或未来日期）。"

        # 业务影响分析
        if t_max >= 35:
            impact = "极端高温预警，建筑制冷负荷极大，建议提前预冷并启动冰蓄冷。"
        elif t_max >= 30:
            impact = "高温天气，制冷设备高负荷运行，关注 COP 下降。"
        elif t_min <= 5:
            impact = "寒潮天气，供暖负荷极高，关注热泵效率。"
        else:
            impact = "气候温和，属于能耗低谷期，可安排设备保养。"

        return (
            f"📅 {date_str} 福州市真实气象记录（open-meteo）：\n"
            f"- 最高气温：{t_max}℃ / 最低气温：{t_min}℃\n"
            f"- 平均相对湿度：{humidity}%\n"
            f"- 业务影响：{impact}"
        )
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        logger.warning(f"天气 API 调用失败，降级到天文模型: {e}")
        # 降级：返回基础信息，但明确标注是降级
        return f"⚠️ {date_str} 天气查询失败（open-meteo 接口异常），请稍后重试或人工查询。"
    except Exception as e:
        logger.exception(f"天气查询失败: {e}")
        # 降级：返回基础信息，但明确标注是降级
        return f"⚠️ {date_str} 天气查询失败（open-meteo 接口异常），请稍后重试或人工查询。"


async def query_device_manual(fault_code: str) -> str:
    """【必杀技2】设备故障 SOP 专家级直达 - 调用 RagFlow 知识库"""
    logger.info(f"📖 [SOP] 查询故障代码: {fault_code}")
    try:
        # 延迟导入避免循环依赖
        from app.services.ragflow_service import ask_ragflow_knowledge
        result = await ask_ragflow_knowledge(f"故障代码 {fault_code} 维修SOP 排查步骤")
        return f"📋 故障代码「{fault_code}」标准运维手册：\n{result}"
    except Exception as e:
        logger.exception(f"故障手册查询失败: {e}")
        # 降级：返回最小化 SOP 提示
        return (
            f"⚠️ 知识库查询「{fault_code}」失败。\n"
            f"建议：1) 检查 RagFlow 服务连通性；2) 联系设备供应商获取 {fault_code} 详细维修文档。"
        )


async def trigger_report_generation(building_type: str, issue: str) -> str:
    """【必杀技3】触发后端生成周报 - 调用 report.py 的真实逻辑"""
    logger.info(f"📄 [报告] 触发生成: building_type={building_type}, issue={issue}")
    try:
        # 延迟导入 report 服务逻辑，避免循环依赖
        from app.services.report_service import generate_weekly_report_content
        report_content = await generate_weekly_report_content(building_type=building_type, issue=issue)
        return (
            f"✅【报告已生成】《{building_type}能耗诊断报告》\n"
            f"核心问题：{issue}\n"
            f"报告内容已生成如下：\n\n{report_content}"
        )
    except Exception as e:
        logger.exception(f"报告生成失败: {e}")
        return "🔥 报告生成失败，请稍后重试或联系管理员。"
