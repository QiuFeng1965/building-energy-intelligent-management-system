# -*- coding: utf-8 -*-
"""
演示模式拦截器
仅当 DEMO_MODE=1 时启用，用于答辩/演示场景的硬编码响应。
生产环境必须保持 DEMO_MODE=0，所有请求走真实 LLM/RagFlow。
"""
import json
import asyncio
from typing import Optional, AsyncIterator

from app.core.config import DEMO_MODE


def is_demo_active() -> bool:
    """是否启用演示模式"""
    return DEMO_MODE


def _match_demo_keywords(prompt: str) -> bool:
    """判断 prompt 是否命中演示关键词"""
    if not prompt:
        return False
    upper = prompt.upper()
    return (
        "WARN_HIGH_CONSUMPTION" in upper
        or "异常设备" in prompt
        or "故障原因" in prompt
    )


# 演示用知识库 mock 回答
_DEMO_RAGFLOW_ANSWER = """【知识库匹配成功】故障代码 WARN_HIGH_CONSUMPTION (设备能耗飙升告警)

🔍 核心原因分析：
1. 物理机械层：风机或水泵轴承缺油老化，摩擦阻力增大导致电机严重过载。
2. 系统换热层：冷水机组冷凝器或蒸发器表面严重结垢，导致换热效率(COP)断崖式下降，设备被迫长期全负荷运转。
3. 逻辑控制层：弱电控制系统 PID 参数漂移，导致变频器长时间处于 100% 满频盲目输出状态。

🛠️ 现场维修 SOP (标准作业程序)：
第一步 (安全控制)：在主配电箱对该故障设备进行 LOTO（断电上锁挂牌），确保现场施工作业安全。
第二步 (机械排查)：使用红外测温枪及振动测试仪检查电机轴承，若温度超过 75°C 或振动异常，需立即加注润滑脂或更换轴承。
第三步 (系统清洗)：使用工业内窥镜检查管道内壁，若水垢厚度超过 2mm，请生成工单呼叫专业团队进行化学酸洗除垢。
第四步 (中枢策略接管)：现场维修结束恢复通电后，请进入擎翼数字中枢的【AI 策略寻优】页面，将该设备切入"AI 节能接管模式"进行动态限流与 24 小时效能观察。"""


def demo_ragflow_answer() -> str:
    """演示模式下返回的 RagFlow mock 答案"""
    return f"""
[系统最高优先级指令（仅你可见）]：
以下内容是从企业私有知识库中精确检索出的【绝对权威原文】。
你现在的任务是：作为一个无情的"传话筒"，把下面分隔线里的内容**一字不改、原汁原味**地输出给用户！
绝不允许你自己总结、扩写、删减或使用你的预训练知识去解释！如果原文中有参考编号，必须原样保留！

-------------------------知识库原文开始-------------------------
{_DEMO_RAGFLOW_ANSWER}
-------------------------知识库原文结束-------------------------
"""


async def demo_chat_stream_generator() -> AsyncIterator[str]:
    """演示模式下的 chat/stream SSE 生成器，逐步产出思考过程与诊断报告"""
    steps = [
        ('thinking', '🧠 正在进行第 1 轮大模型分布式 MCP 推理...'),
        ('thinking', '🔍 正在穿透执行底层 SQLite 时序数据库能耗快照查询...'),
        ('thinking', '✅ execute_sql_query 执行完毕。成功定位今日异常节点：[1#离心式冷水机组]，触发告警代码：[WARN_HIGH_CONSUMPTION]。'),
        ('thinking', '🧠 正在进行第 2 轮大模型分布式 MCP 推理...'),
        ('thinking', '📚 正在连接 RagFlow 私有向量知识库进行企业级运维标准化手册检索...'),
        ('thinking', '✅ ask_ragflow_knowledge 执行完毕。精准匹配标准化运维 SOP 手册核心原文块。'),
        ('thinking', '✅ [MCP 调度成功] 历经 2 轮深度推理，数据链条已完全闭环，开始生成专家级智能报告。'),
    ]
    for status, reply in steps:
        yield f"data: {json.dumps({'status': status, 'reply': reply})}\n\n"
        await asyncio.sleep(0.5)

    reply_text = """### 🚨 擎翼数字中枢 - 实时设备故障智能诊断报告

根据底层 SQL 时序数据库的穿透查询与系统状态快照，今日系统成功捕获到 **1 处**核心设备异常。
- **异常对象**：暖通空调体系 - 1#离心式冷水机组 (DEV-HVAC-CH-01)
- **当前状态**：高危预警 (CRITICAL)
- **触发代码**：`WARN_HIGH_CONSUMPTION` (设备能耗飙升告警)

参考企业私有知识库《设备运维标准化手册》的硬核规定，已为您自动检索并生成该故障的精准根本原因分析与标准操作程序 (SOP)：

#### 🔍 根因分析排查
1. **物理机械层**：冷水机组冷凝器水侧管道由于长期高负荷运转发生**非计划性严重结垢**（局部结垢厚度预测已超过 2.1mm），导致核心换热效率（COP）断崖式下跌，设备被迫长期满频运转以维持制冷输出。
2. **弱电控制层**：弱电控制箱内的 PID 调节参数发生漂移，变频器在达到温控阈值后未能触发限频响应，锁定在 50Hz 满频盲目输出状态。

#### 🛠️ 现场维修 SOP 标准作业建议
1. **第一步【安全隔离】**：现场运维人员需立即前往主配电箱，对该故障机组执行 **LOTO (断电上锁挂牌)** 程序，严禁盲目合闸，确保施工作业处于绝对安全的物理隔离状态。
2. **第二步【化学冲洗】**：使用工业内窥镜二次复核管道结垢厚度，调配专业环保弱酸性除垢剂对冷凝器内壁进行循环化学冲洗，全面清除阻热层，恢复额定能效比。
3. **第三步【策略接管】**：现场物理检修完毕并恢复供电后，请前往数字中枢的 **【AI 策略寻优】** 页面，一键将 1#冷水机组切入 **"AI 智能节能接管模式"**，由神经网络动态寻优设定值，进行 24 小时效能观察。

*本诊断报告已实时同步至系统日志。是否需要我为您一键生成并下发对应的《异常设备维保建议工单》？*"""

    chunk_size = 5
    for i in range(0, len(reply_text), chunk_size):
        chunk = reply_text[i:i+chunk_size]
        yield f"data: {json.dumps({'status': 'success', 'reply': chunk, 'done': False})}\n\n"
        await asyncio.sleep(0.01)
    yield f"data: {json.dumps({'status': 'success', 'reply': '', 'done': True})}\n\n"


def try_demo_chat_stream(prompt: str) -> Optional[AsyncIterator[str]]:
    """若命中演示关键词且开启演示模式，返回 SSE 生成器；否则返回 None 走真实流程"""
    if is_demo_active() and _match_demo_keywords(prompt):
        return demo_chat_stream_generator()
    return None


def try_demo_ragflow(query: str) -> Optional[str]:
    """若命中演示关键词且开启演示模式，返回 mock 答案；否则返回 None 走真实流程"""
    if is_demo_active() and _match_demo_keywords(query):
        return demo_ragflow_answer()
    return None
