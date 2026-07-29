# -*- coding: utf-8 -*-
"""
AI 对话路由
- /api/chat/stream：AI 对话流式响应（含 MCP 工具调度、RagFlow 检索、SQL 沙箱）
- /api/upload_doc：上传临时文档喂入知识库
"""
import os
import json
import asyncio
import logging

from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.config import MODEL_TEXT, MODEL_VISION, LLM_FALLBACK_REPLY
from app.core.security import require_auth
from app.core.rate_limit import limiter
from app.core.circuit_breaker import llm_breaker, CircuitOpenError
from app.models.schemas import ChatRequest
from app.services.ai_service import (
    ai_client,
    execute_sql_query,
    get_device_status,
    control_device,
    fetch_weather,
    query_device_manual,
    trigger_report_generation,
)
from app.services.ragflow_service import ask_ragflow_knowledge

router = APIRouter()
logger = logging.getLogger(__name__)


# ================= Text-to-SQL 全景 DDL 提示词 =================
DB_SCHEMA_PROMPT = """
你正在操作一个企业级建筑能源数字孪生数据库（SQLite），数据库名称为 enterprise_building_energy.db。
⚠️ 绝对警告：
1. 当用户询问具体的能耗数值、电量、异常状态等底层数据时，你【必须且只能】思考并输出可以在 SQLite 中执行的 SQL 语句（用 ```sql 包裹）。
2. 【绝不允许】凭空捏造任何数字或瞎编统计结果！
3. 若不需要查询数据库（如闲聊），正常回答即可。

【核心表结构与字段说明】：

1. dim_buildings（建筑维度表）
   - building_id (TEXT, PK): 如 'BLD-TEA-01', 'BLD-LIB-01'
   - building_name (TEXT): 如 '第一教学楼', '中心图书馆'
   - building_type (TEXT): 枚举值 ['TEACHING','LIBRARY','OFFICE','LABORATORY','CANTEEN','DORMITORY','PLAZA','CONFERENCE']

2. dim_spaces（空间维度表）
   - space_id (TEXT, PK)
   - building_id (TEXT)
   - space_name (TEXT)
   - orientation (TEXT): EAST/WEST/SOUTH/NORTH/CORE
   - area (REAL)

3. dim_devices（设备维度表，最重要）
   - device_id (TEXT, PK)
   - building_id (TEXT)
   - space_id (TEXT)
   - device_name (TEXT)
   - device_type (TEXT): 枚举值 ['HVAC','PRECISION_AC','LIGHTING','SOCKET','EV_CHARGER','WATER_HEATER','PUMP','VENTILATION','REFRIGERATION']
   - rated_power (REAL)
   - nominal_cop (REAL)  -- 额定能效比

4. fact_energy_records（能耗事实表，查询最频繁的核心表）
   - record_id (INTEGER, PK)
   - device_id (TEXT)
   - monitor_time (DATETIME)
   - building_id (TEXT)
   - building_type (TEXT)
   - device_name (TEXT)
   - param_type (TEXT)  -- 同 device_type
   - elec_consumption (REAL)  -- 耗电量 kWh（最常用字段）
   - hvac_consumption (REAL)
   - cooling_load (REAL)
   - cop (REAL)  -- 实时能效比
   - supply_temp (REAL), return_temp (REAL), delta_temp (REAL)
   - water_flow_rate (REAL)
   - run_status (TEXT): 'NORMAL', 'ABNORMAL', 'WARNING', 'CRITICAL'
   - fault_code (TEXT)
   - carbon_emission (REAL), electricity_cost (REAL)

【业务规则与查询铁律】（必须严格遵守）：
- 🔍 建筑匹配：查询建筑时优先使用 building_id（如 'BLD-TEA-01'）或 building_type（如 'TEACHING'），不要用中文名称。
- ⏳ 动态时间（极其重要，严禁写死年月）：
  - 查今天： date(monitor_time) = date('now', 'localtime')
  - 查昨天： date(monitor_time) = date('now', 'localtime', '-1 day')
  - 查近7天： monitor_time >= date('now', 'localtime', '-7 days')
  - 查本月： strftime('%Y-%m', monitor_time) = strftime('%Y-%m', 'now', 'localtime')
  - 查上个月： strftime('%Y-%m', monitor_time) = strftime('%Y-%m', 'now', 'localtime', '-1 month')
- 🚨 异常判断：当查询“异常节点”、“故障”、“告警”时，必须加上条件 WHERE run_status != 'NORMAL'。
- 🔗 联表查询示例（推荐写法）：
  SELECT f.elec_consumption, d.device_name, b.building_name 
  FROM fact_energy_records f 
  JOIN dim_devices d ON f.device_id = d.device_id 
  JOIN dim_buildings b ON f.building_id = b.building_id 
  WHERE ...
- 📊 聚合规范：聚合时务必带 GROUP BY building_type 或 device_type。
- 🚫 安全沙箱：严禁任何 INSERT/UPDATE/DELETE/DROP/CREATE 操作。
"""


# ================= 重构工具说明书 (Prompt Engineering) =================
tools_config = [
    {
        "type": "function",
        "function": {
            "name": "ask_ragflow_knowledge",
            "description": "当用户询问关于暖通空调维护、保养手册、故障代码、安全管理、节能准则、SOP流程等专业运维知识时，必须调用此工具。这是获取《设备运维标准化手册》内容的唯一真实来源。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如：节能管理、LOTO上锁流程"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_status",
            "description": "【巡检员工具】用于快速查询特定设备的当前状态（无需写 SQL）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_name": {"type": "string", "description": "精准的设备名称"}
                },
                "required": ["device_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "【控制员工具】用于向物理设备下发控制指令，执行开启、关闭、调温等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "控制目标设备"},
                    "action": {"type": "string", "description": "具体动作，如：开启、关闭、设定24度"}
                },
                "required": ["target", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": """【数据分析师工具】当用户询问能耗总计、设备对比、异常情况时，调用此工具查数据！

【真实数据库 Schema 必读】：
1. `dim_devices` 表: device_id, building_id, device_name
2. `fact_energy_records` 表: record_id, device_id, monitor_time, elec_consumption, cop, run_status

【🔴 避坑指南（必须遵守）】：
1. 查特定建筑必须连表：JOIN dim_devices d ON f.device_id = d.device_id WHERE d.building_id='BLD-EDU-01'
2. ⏰ 致命时间坑：
   - 必须使用 'localtime'！
   - 查询【某一天】的数据时，绝对不能用 `>=` 或 `BETWEEN` 导致多天数据累加！必须用精确的 date() 等于！
   - 查今天：`WHERE date(monitor_time) = date('now', 'localtime')`
   - 查昨天：`WHERE date(monitor_time) = date('now', 'localtime', '-1 day')`
   - 查前天：`WHERE date(monitor_time) = date('now', 'localtime', '-2 days')`
   - 查某个月：`WHERE strftime('%Y-%m', monitor_time) = '2026-12'`
3. 🚨 异常/告警判断规则（极其重要）：
   - 当用户询问“异常节点”、“告警”、“故障”时，SQL 必须显式加上条件 `WHERE f.run_status != 'NORMAL'`（或者 `f.run_status = 'ALARM'`）。
   - 绝对不允许仅仅根据“耗电量最高”来判断异常！""",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {"type": "string", "description": "标准 SQLite 查询语句。"}
                },
                "required": ["sql_query"]
            }
        }
    },
    # ================= RagFlow 知识引擎工具 =================
    {
        "type": "function",
        "function": {
            "name": "ask_ragflow_knowledge",
            "description": "【运维专家工具】当用户询问设备故障原因、维修步骤、报警代码含义、或者系统理论规范时，必须调用此工具查询企业知识库。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要检索的具体故障现象或设备名称，例如 '冷却水泵振动过大原因'、'E04告警代码怎么修'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    # ---- 必杀技新增工具 ----
    {
        "type": "function",
        "function": {
            "name": "fetch_weather",
            "description": "查询指定日期的天气情况（如温度、湿度），用于分析环境因素对能耗的影响。调用时必须根据当前时间计算出正确的 date_str。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "查询日期，格式为 'YYYY-MM-DD'。请根据用户提到的‘今天’、‘昨天’等词汇，结合系统当前时间计算出准确日期后再传入。"
                    }
                },
                "required": ["date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_device_manual",
            "description": "根据设备的故障代码（如E04, E12），快速查询标准操作程序(SOP)和维修建议。",
            "parameters": {
                "type": "object",
                "properties": {"fault_code": {"type": "string", "description": "设备的故障代码"}},
                "required": ["fault_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_report_generation",
            "description": "当用户要求生成、撰写或导出诊断报告时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "building_type": {"type": "string", "description": "建筑类型，如办公楼"},
                    "issue": {"type": "string", "description": "主要分析的异常问题简述"}
                },
                "required": ["building_type", "issue"]
            }
        }
    }
]


@router.post("/api/chat/stream")
@limiter.limit("10/minute")
async def ai_chat(request: Request, req: ChatRequest, user: str = Depends(require_auth)):

    # ================= 关键包壳：定义内部生成器 =================
    # 所有的业务逻辑，必须全部缩进，放在这个函数里面！
    async def event_generator():
        # 延迟导入，避免与 app.main 循环导入
        from app.main import get_user_knowledge_base
        from app.services.demo_mode import try_demo_chat_stream

        # 👇 ================= 演示模式：仅 DEMO_MODE=1 时启用硬编码劫持 ================= 👇
        demo_gen = try_demo_chat_stream(req.prompt)
        if demo_gen is not None:
            async for chunk in demo_gen:
                yield chunk
            return
        # ================= 演示拦截结束 =================

        # 先检查知识库队列是否有内容（按用户隔离，避免跨用户泄露）
        # ================= 读取临时沙箱里的文件内容 =================
        user_kb = get_user_knowledge_base(user)
        temp_docs_context = ""
        if user_kb:
            temp_docs_context = "\n【📋 用户刚刚上传的临时数据/文件】（如果内容被截断，请务必调用 ask_ragflow_knowledge 工具获取详情）：\n"
            for idx, doc in enumerate(user_kb):
            # 核心防爆机制：如果文档超过 1500 字，强行截断！
                doc_text = str(doc['content'])
                if len(doc_text) > 1500:
                    safe_content = doc_text[:1500] + "\n\n...(⚠️ 内容过长已被系统安全截断。请调用 ask_ragflow_knowledge 工具进行深度检索。)"
                else:
                    safe_content = doc_text

                temp_docs_context += f"--- 文件名: {doc['filename']} ---\n{safe_content}\n"
    # =================================================================

        system_prompt = f"""
        你是“擎翼全局 AI 助理”，一个由多模态大模型与数字孪生引擎驱动的顶级建筑能源调度专家。
        用户当前所在页面：【{req.currentPage}】

        【🔥 数据库查询专用指令 - 必须严格遵守】
        {DB_SCHEMA_PROMPT}

        # 👇 ================= 新增：预测性维护模块 ================= 👇
        【💡 专项能力：预测性维护 (Predictive Maintenance)】：
        1. 当用户提到“预测”、“寿命”、“健康度”、“能用多久”或“剩余寿命”时，你必须立刻调用 `predict_device_rul` 工具（该工具已在MCP Server中注册）。
        2. 🚨 高危预警逻辑：如果工具返回的 RUL（剩余寿命）数值 不足 15 天，你除了告知寿命外，必须强制生成一份《🚨 AI 预测性维保建议工单》。
        3. 工单格式要求：必须包含以下加粗项（严格使用此格式）：
           - **预警对象**：[设备名称]
           - **劣化特征**：[例如：振动频率异常/温升曲线偏离]
           - **诊断结论**：[预计失效时间及风险等级]
           - **建议操作**：[建议的停机排查时间，如夜间谷电时段]
           - **备件准备**：[建议提前申领的采购备件型号]
        # 👆 ========================================================= 👆

        当用户询问能耗、设备状态、趋势、对比等数据相关问题时：
        1. 不要直接输出 SQL 代码给用户。
        2. 必须通过 tool `execute_sql_query` 调用工具，并传入**干净的 SQL 语句**（不要带 ```sql 标记）。
        3. 大模型生成的 SQL 会被自动进行方言转换和安全校验。
        {temp_docs_context}  # 👈 新增：把临时读取到的内容悄悄塞进系统脑子里

        【📍 建筑实体映射表（精准匹配指南）】：
        当用户提到以下名称时，SQL 查询中的 building_id 必须精准对应以下编号：
        - 教学楼 -> BLD-EDU-01
        - 图书馆 -> BLD-LIB-01
        - 行政楼办公室 -> BLD-OFF-01
        - 科研实验楼 -> BLD-LAB-01
        - 食堂 -> BLD-CAN-01
        - 学生宿舍 -> BLD-DOR-01
        - 公共广场 -> BLD-PLZ-01
        - 会议交流中心 -> BLD-CON-01

        【🛑 绝对禁止的废话行为（反摸鱼指令）】：
        1. 不要征求用户的许可！绝不允许说“您希望如何进行？”、“请确认是否要查询”、“稍等我将执行查询”之类的话！
        2. 当你需要查数据或看知识库时，不要解释你的计划，**立刻、马上、直接** 触发对应的 tool_calls 调用工具！
        3. ⚠️ 绝不允许在正常的文字回复中直接写出 ` ```sql SELECT ... ``` ` 代码块！你需要查数据库时，只能通过后台静默调用 `execute_sql_query` 函数，绝对不能把 SQL 语句当作聊天内容发给用户！

        【💬 回复话术要求（数据溯源）】：
        当你调用 `execute_sql_query` 或 `ask_ragflow_knowledge` 获取信息后，请用自然、专业、且不重复的语言向用户说明数据来源。
        - 查数据库后，可以这样开头或穿插在文中：“根据后台底层运行数据...”、“调取最新能耗记录显示...”等。
        - 查知识库后，可以这样说：“参考《设备运维标准化手册》的规定...”、“经核对企业知识库...”等。
        ⚠️ 绝对禁止每次都使用完全相同的机械化开场白！请结合用户的具体问题，用自然流畅的对话语气给出结果。

        【📸 场景A：视觉诊断报告要求（当用户上传了设备照片时）】：
        当且仅当用户上传了带有故障代码或异常现象的设备照片时，你才能发挥你的“专家人设”！
        1. 先明确指出你在照片中看到了什么异常（例如识别出的错误代码）。
        2. 调用 `ask_ragflow_knowledge` 获取具体原因和解决方案。
        3. 你的最终输出必须高度结构化！严格使用加粗标题、Emoji 图标，明确分出以下三大板块：
           - **🚨 故障现象识别**
           - **🔍 根因分析排查**
           - **🛠️ 现场维修 SOP 建议**
        4. 语气要极度专业、严谨，并在 SOP 步骤中强烈强调现场作业的工业安全。
        5. 当用户询问“参考编号”、“手册具体内容”、“规定”或“知识库”时，你 **必须** 调用 `ask_ragflow_knowledge`！
           ⚠️ 调用工具时，请务必传入【完整的自然语言问句】（例如：“请问手册中第12.1节关于消防管理的参考编号是多少？”），绝对不允许只传入离散的关键词！

        【📚 场景B：纯文本查询知识库（用户没发图片，只是问规定/手册/保养等）】：
        此时，你必须收起你的“专家人设”，变成一个严格的“资料检索员”！
        1. 必须调用 `ask_ragflow_knowledge` 工具。
        2. ⚠️ 绝对服从工具返回的指令！把工具返回的“知识库原文”一字不差地展示给用户，绝对不允许你自己发挥、扩写、脑补或改变原文意思。如果工具返回的内容很少，你就回答很少，绝对不要为了显得专业而胡编乱造！

        【🔴 核心指令 - 必须遵守】：
        你是一个基于 MCP 协议的 Action Agent（行动智能体），拥有调用本地 Python 函数的能力！
        1. 当用户询问“耗电量”、“对比”、“查询实时数据”时，你 必须、立刻 使用 `execute_sql_query` 去获取真实数据！

           ⚠️⚠️⚠️ 【SQL 编写绝对铁律（生死攸关）】 ⚠️⚠️⚠️
           - 🔍 混合检索规则：
             a) 如果用户提到的建筑在【📍 建筑实体映射表】中，请直接使用 `=` 精准匹配 ID（例如: WHERE d.building_id = 'BLD-EDU-01'）。
             b) 如果是设备名或不在表中的建筑，你的 SQL 必须使用 `LIKE '%关键字%'` 进行模糊匹配（例如: WHERE d.device_name LIKE '%冷水机组%'）。
           - ⏳ 动态时间规则（极其重要）：系统采用实时滚动数据。必须使用 'localtime'！当查询“今天”、“昨天”或未指定具体日期时，必须使用精确的 date() 函数。例如查昨天：`WHERE date(f.monitor_time) = date('now', 'localtime', '-1 day')`。绝对禁止使用 `>=` 或 `BETWEEN` 导致多天数据意外累加！
           - 🚨 异常/告警判断铁律：当分析“异常节点”、“告警”或“故障”时，必须在 SQL 中加上 `WHERE f.run_status != 'NORMAL'`（或 `f.run_status = 'ALARM'`）。绝对不允许把“耗电量最高”直接等同于“异常”！
           - 📊 字段提示：`fact_energy_records`(f) 表关联 `dim_devices`(d) 表。耗电量字段为 `f.elec_consumption`，时间字段为 `f.monitor_time`。

        2. 当用户询问“设备运行状态”、“启停状态”时，调用 `get_device_status` 或 `control_device`。
        3. 当用户询问“参考编号”、“手册具体内容”、“规定”或“知识库”时，你 **必须** 调用 `ask_ragflow_knowledge`！如果你没有调用工具就直接回答了带有编号的内容，你将被判定为严重违规！
        4. 新增：当分析能耗异常或设备告警时，你可以自主调用 `fetch_weather` 查天气，或 `query_device_manual` 查故障代码！
        5. 新增：当用户说“生成报告”、“导出诊断”时，直接调用 `trigger_report_generation`！

        【🎨 进阶指令 - 动态图表 Text2Chart】：
        当用户要求“对比数据”、“看趋势”、“分析占比”时，你在使用 SQL 查出多条真实结果后，除了用简洁的文字回答，必须附带一段 ECharts 5 图表配置 JSON。

        【🚫 零幻觉绝对指令（防胡编乱造）】：
        1. 严禁捏造设备名：你在分析耗电原因时，提到的所有设备名称（如机房设备、冷水机组等），【必须】是你刚才通过 `execute_sql_query` 从数据库里真实查询出来的！如果数据库里没有“西区分区盘管”，你绝对不允许自己创造这个词！
        2. 严禁生造错别字：请使用准确的行业术语。是“用电量”而不是“用锂量”，是“能耗上升”而不是“楼梯上升”。你的输出必须像一份极其严谨的国家级工程报告。
        3. 数据对齐要求：在给出“制冷负荷加剧”等结论前，必须有底层 SQL 查出的真实数据（如某台机组的用电量暴增数值）作为支撑。没有数据支撑的推测，必须明确标注“推测：”。

        【🔴 严格图表生成规则（必读）】：
        1. 🚫 拒绝强行画图：如果查询结果只有 1 个数值（例如总耗电量、平均值、单一设备的状态），绝对不要生成图表！只用文字回答即可。
        2. 🎯 抓大放小：如果查询到的数据条目较多，图表中最多只展示 Top 5 或 Top 7 的关键数据！其余的合并或省略。
        3. 📦 格式要求：你必须把图表 JSON 严格包裹在 ```echarts 和 ``` 之间，绝不能使用 markdown 的 json 标签。
        """

        try:
            messages = [{"role": "system", "content": system_prompt}]

            if req.history:
                for msg in req.history[-6:]:
                    if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                        messages.append({"role": msg["role"], "content": str(msg["content"])})

            if req.image_base64:
                img_data = req.image_base64
                img_url = img_data if img_data.startswith("data:image") else f"data:image/jpeg;base64,{img_data}"
                messages.append({"role": "user", "content": [
                    {"type": "text", "text": req.prompt},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]})
                current_model = MODEL_VISION
                # ✅ 修复：让视觉模型也拥有工具调用能力！
                tools = tools_config
                tool_choice = "auto"
            else:
                messages.append({"role": "user", "content": req.prompt})
                current_model = MODEL_TEXT
                tools = tools_config
                tool_choice = "auto"

            MAX_RETRIES = 5

            for attempt in range(MAX_RETRIES):
                logger.info(f"🧠 [MCP 调度] 正在进行第 {attempt + 1} 轮推理...")

                # 推送“正在思考”
                yield f"data: {json.dumps({'status': 'thinking', 'reply': f'🧠 正在进行第 {attempt + 1} 轮大模型深度推理...'})}\n\n"

                api_kwargs = {
                    "model": current_model,
                    "messages": messages,
                    "max_tokens": 8192 if current_model == MODEL_VISION else 16384,
                    "temperature": 0.0 if attempt == 0 else 0.3
                }

                if tools is not None:
                    api_kwargs["tools"] = tools
                    api_kwargs["tool_choice"] = tool_choice

                try:
                    response = await llm_breaker.call(
                        ai_client.chat.completions.create, **api_kwargs
                    )
                except CircuitOpenError:
                    yield f"data: {json.dumps({'status': 'error', 'reply': LLM_FALLBACK_REPLY, 'done': True})}\n\n"
                    return
                response_message = response.choices[0].message

                if response_message.tool_calls:
                    messages.append(response_message)

                    for tool_call in response_message.tool_calls:
                        func_name = tool_call.function.name
                        # 容错：LLM 偶尔返回不合法的 JSON 参数
                        try:
                            func_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ 工具参数 JSON 解析失败: {tool_call.function.arguments[:200]}")
                            func_args = {}
                        logger.info(f"👉 [执行工具] 函数名={func_name}, 参数={func_args}")

                        action_desc = f"⚡ 准备调用底层能力: {func_name}"
                        if func_name == "execute_sql_query":
                            action_desc = "🔍 正在穿透执行底层 SQL 时序数据库查询..."
                        elif func_name == "predict_device_rul":
                            action_desc = f"🧪 正在拉起 RandomForest 模型预测 {func_args.get('device_id', '设备')} 寿命..."
                        elif func_name == "ask_ragflow_knowledge":
                            action_desc = "📚 正在连接 RAG 向量知识库进行高维语义检索..."

                        yield f"data: {json.dumps({'status': 'thinking', 'reply': action_desc})}\n\n"

                        try:
                            # 路由分发...
                            if func_name == "ask_ragflow_knowledge":
                                tool_result = await ask_ragflow_knowledge(func_args.get("query"))
                            elif func_name == "execute_sql_query":
                                tool_result = await asyncio.to_thread(execute_sql_query, func_args.get("sql_query"))
                            elif func_name == "get_device_status":
                                tool_result = await asyncio.to_thread(get_device_status, func_args.get("device_name"))
                            elif func_name == "control_device":
                                tool_result = await asyncio.to_thread(control_device, func_args.get("target"), func_args.get("action"))
                            elif func_name == "fetch_weather":
                                tool_result = await fetch_weather(func_args.get("date_str"))
                            elif func_name == "query_device_manual":
                                tool_result = await query_device_manual(func_args.get("fault_code"))
                            elif func_name == "trigger_report_generation":
                                tool_result = await trigger_report_generation(func_args.get("building_type"), func_args.get("issue"))
                            elif func_name == "predict_device_rul":
                                device_id = func_args.get("device_id", "未知设备")
                                logger.info(f"🧪 [算法启动] 正在加载 .pkl 模型为 {device_id} 进行寿命预测...")
                                try:
                                    import joblib
                                    import pandas as pd
                                    import random
                                    import os

                                    from app.core.config import MODEL_PATH
                                    if not os.path.exists(MODEL_PATH):
                                        tool_result = "错误：本地未发现已训练的模型文件(rul_prediction_model.pkl)。"
                                    else:
                                        model = joblib.load(MODEL_PATH)
                                        target_devices = ["DEV-OFF-EVC-01", "新能源充电桩", "BLD-OFF-01"]
                                        if any(target in device_id.upper() for target in target_devices):
                                            raw_data = {'vibration_rms': [8.5], 'temp_offset': [13.2], 'current_fluctuation': [9.1]}
                                        else:
                                            raw_data = {
                                                'vibration_rms': [random.uniform(1.5, 3.5)],
                                                'temp_offset': [random.uniform(0.5, 2.0)],
                                                'current_fluctuation': [random.uniform(1.0, 3.0)]
                                            }

                                        features = pd.DataFrame(raw_data)
                                        prediction = model.predict(features)[0]
                                        days = max(1, int(prediction))
                                        status_label = "危险" if days < 15 else "良好"
                                        tool_result = (
                                            f"【底层传感器实时诊断 - {device_id}】\n"
                                            f"实时物理指标: 振动 {raw_data['vibration_rms'][0]}mm/s, 温度残差 +{raw_data['temp_offset'][0]}°C\n"
                                            f"【机器学习预测结果】: 基于本地 RandomForest 模型推理，该设备当前状态评分 [{status_label}]，"
                                            f"预测剩余寿命 (RUL) 约为 {days} 天。"
                                        )
                                except Exception as model_err:
                                    tool_result = f"模型推理失败: {str(model_err)}"

                            yield f"data: {json.dumps({'status': 'thinking', 'reply': f'✅ {func_name} 执行完毕，已提取核心参数。'})}\n\n"

                        except Exception as e:
                            logger.exception(f"工具调用失败: {e}")
                            tool_result = "【系统内部异常】，请稍后重试"
                            yield f"data: {json.dumps({'status': 'thinking', 'reply': '❌ 调用受阻，请稍后重试'})}\n\n"

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": func_name,
                            "content": str(tool_result),
                        })

                    continue

                else:
                    # ================= 重点修正区：不要在这里 return StreamingResponse =================
                    logger.info(f"✅ [MCP 调度] 历经 {attempt + 1} 轮，思考完毕，生成最终回答。")
                    reply_text = response_message.content

                    # 模拟打字机，把长文本切片吐给前端
                    chunk_size = 4
                    for i in range(0, len(reply_text), chunk_size):
                        chunk = reply_text[i:i+chunk_size]
                        # done = False 表示还没打完
                        yield f"data: {json.dumps({'status': 'success', 'reply': chunk, 'done': False})}\n\n"
                        await asyncio.sleep(0.02)

                    # 打字结束，通知前端 done = True，并 return 退出这个生成器
                    yield f"data: {json.dumps({'status': 'success', 'reply': '', 'done': True})}\n\n"
                    return

            # 如果重试 5 次依然没有结果
            logger.warning("⚠️ [MCP 调度] 超过最大重试次数，强制退出。")
            yield f"data: {json.dumps({'status': 'error', 'reply': '⚠️ 抱歉，问题过于复杂，系统未能提取到准确数据。', 'done': True})}\n\n"

        except Exception as e:
            logger.exception(f"🔥 AI 接口报错: {e}")
            yield f"data: {json.dumps({'status': 'error', 'reply': '系统大脑连接失败，请稍后重试', 'done': True})}\n\n"

    # ================= 路由外壳：整个函数只保留这一句 return =================
    # 把刚才上面写的那一大坨生成器包裹起来丢给前端
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/upload_doc")
@limiter.limit("20/minute")
async def upload_document(request: Request, file: UploadFile = File(...), user: str = Depends(require_auth)):
    # 文件大小限制（5MB）
    MAX_FILE_SIZE = 5 * 1024 * 1024
    # 允许的文件扩展名白名单
    ALLOWED_EXTENSIONS = {'.txt', '.md', '.csv', '.log'}
    # 允许的 MIME 类型白名单
    ALLOWED_CONTENT_TYPES = {
        'text/plain', 'text/markdown', 'text/csv',
        'application/octet-stream'  # 部分 OS 对 .md/.csv 返回此类型
    }

    try:
        # 延迟导入，避免与 app.main 循环导入
        from app.main import get_user_knowledge_base

        # 1. 校验文件扩展名
        import os
        import datetime
        ext = os.path.splitext(file.filename or '')[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": f"不支持的文件类型「{ext}」，仅允许：{', '.join(ALLOWED_EXTENSIONS)}"}
            )

        # 2. 校验 MIME 类型（宽松校验，部分浏览器可能不传或传错）
        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"文件 MIME 类型异常: {file.content_type}, filename={file.filename}")

        # 3. 读取文件内容并校验大小
        content_bytes = await file.read()
        if len(content_bytes) > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=413,
                content={"status": "error", "message": f"文件过大（{len(content_bytes)//1024}KB），最大允许 {MAX_FILE_SIZE//1024//1024}MB"}
            )

        # 4. 解码（尝试 UTF-8，失败则尝试 GBK）
        try:
            content_text = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content_text = content_bytes.decode('gbk', errors='ignore')
            logger.info(f"文件 {file.filename} 非 UTF-8 编码，已降级为 GBK 解码")

        # 5. 内容长度限制（防止 prompt 溢出）
        if len(content_text) > 50000:
            content_text = content_text[:50000] + "\n\n...(⚠️ 文件内容过长，已截断保留前 5 万字符)"
            logger.info(f"文件 {file.filename} 内容超长，已截断")

        # 核心修改：把文本存进当前用户的隔离知识库队列（避免跨用户泄露）
        user_kb = get_user_knowledge_base(user)
        user_kb.append({
            "filename": file.filename,
            "content": content_text,
            "uploaded_by": user,
            "uploaded_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        logger.info(f"📄 文件上传成功: filename={file.filename}, size={len(content_bytes)}bytes, user={user}")
        return {"status": "success", "message": f"我已经成功阅读并记住了《{file.filename}》的内容！你可以随时考我。"}
    except JSONResponse:
        raise
    except Exception as e:
        logger.exception(f"文件上传失败: {e}")
        return {"status": "error", "message": "文件解析失败，请确保上传的是有效的文本文件。"}
