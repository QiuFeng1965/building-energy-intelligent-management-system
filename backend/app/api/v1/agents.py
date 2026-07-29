# -*- coding: utf-8 -*-
"""
多智能体协作路由
- /api/agents/workflow：多智能体协作编排（诊断 Agent → 根因 Agent → 维保 Agent → 报表 Agent）
- /api/agents/list：可用智能体清单
- /api/agents/execute/{task_id}：执行编排任务（流式输出）

设计要点：
1. 采用 LangGraph 风格的有向无环图（DAG）编排
2. 每个智能体有明确职责：感知、诊断、决策、执行
3. 智能体之间通过共享状态（Blackboard 模式）传递信息
4. 复用现有 chat.py 的 LLM 调用能力
"""
import json
import logging
import asyncio
import datetime
from typing import Optional, Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.database import get_conn
from app.core.rate_limit import limiter
from app.core.config import AI_API_KEY, AI_BASE_URL, MODEL_TEXT

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 智能体定义 =====
AGENTS_REGISTRY = {
    "diagnostician": {
        "name": "诊断智能体",
        "role": "感知设备运行状态，识别异常模式",
        "icon": "🔍",
        "inputs": ["device_id", "time_range"],
        "outputs": ["anomaly_summary", "key_metrics"],
        "system_prompt": "你是一位资深的暖通空调系统诊断专家。基于设备运行数据，精准识别异常模式，输出结构化诊断结果。",
    },
    "root_cause_analyst": {
        "name": "根因分析智能体",
        "role": "对异常做根因归因，输出可能的故障链",
        "icon": "🧠",
        "inputs": ["anomaly_summary"],
        "outputs": ["root_causes", "fault_chain"],
        "system_prompt": "你是设备故障根因分析专家。基于诊断结果，使用 5-Why 分析法和故障树，输出最可能的根因链。",
    },
    "maintenance_planner": {
        "name": "维保决策智能体",
        "role": "根据根因制定维保工单与备件清单",
        "icon": "🛠️",
        "inputs": ["root_causes"],
        "outputs": ["work_order", "parts_list", "priority"],
        "system_prompt": "你是设备维保调度专家。根据根因分析，制定具体的维保方案，包括工单优先级、所需备件、人员安排。",
    },
    "report_generator": {
        "name": "报表生成智能体",
        "role": "汇总整个工作流，生成结构化报告",
        "icon": "📊",
        "inputs": ["anomaly_summary", "root_causes", "work_order"],
        "outputs": ["final_report"],
        "system_prompt": "你是技术报告撰写专家。将诊断、根因、维保方案汇总为结构化的诊断报告，包含执行摘要、详细分析、建议措施。",
    },
}

# ===== 工作流定义（DAG）=====
WORKFLOW_GRAPH = {
    "nodes": ["diagnostician", "root_cause_analyst", "maintenance_planner", "report_generator"],
    "edges": [
        {"from": "diagnostician", "to": "root_cause_analyst"},
        {"from": "root_cause_analyst", "to": "maintenance_planner"},
        {"from": "maintenance_planner", "to": "report_generator"},
    ],
}


class WorkflowRequest(BaseModel):
    """工作流执行请求"""
    task: str = "诊断并处理近期异常设备"
    device_id: Optional[str] = None
    context: Optional[dict] = None


@router.get("/api/agents/list")
def list_agents():
    """可用智能体清单"""
    return {
        "status": "success",
        "data": {
            "agents": [
                {
                    "id": aid,
                    "name": a["name"],
                    "role": a["role"],
                    "icon": a["icon"],
                    "inputs": a["inputs"],
                    "outputs": a["outputs"],
                }
                for aid, a in AGENTS_REGISTRY.items()
            ],
            "workflow": WORKFLOW_GRAPH,
        },
    }


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json={
                    "model": MODEL_TEXT,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.warning(f"LLM 调用失败 {resp.status_code}: {resp.text[:200]}")
            return f"[LLM 不可用，降级响应] {system_prompt[:50]}..."
    except Exception as e:
        logger.exception(f"Agent LLM 调用失败: {e}")
        return "[LLM 异常]，请稍后重试"


async def _fetch_device_context(device_id: Optional[str]) -> str:
    """从数据库获取设备上下文"""
    try:
        import pandas as pd
        with get_conn() as conn:
            if device_id:
                df = pd.read_sql(
                    "SELECT * FROM fact_energy_records WHERE device_id = ? ORDER BY monitor_time DESC LIMIT 20",
                    conn,
                    params=[device_id],
                )
            else:
                df = pd.read_sql(
                    "SELECT device_id, device_name, run_status, cop, elec_consumption, monitor_time "
                    "FROM fact_energy_records WHERE run_status != 'NORMAL' ORDER BY monitor_time DESC LIMIT 10",
                    conn,
                )
        if df.empty:
            return "近期无异常设备"
        return df.to_string(index=False)
    except Exception as e:
        logger.exception(f"Agent 数据获取失败: {e}")
        return "数据获取失败，请稍后重试"


@router.post("/api/agents/workflow")
@limiter.limit("5/minute")
async def execute_workflow(request: Request, req: WorkflowRequest):
    """
    执行多智能体协作工作流（流式 SSE 输出）
    - 接收任务描述和设备 ID
    - 按顺序执行 4 个智能体
    - 每个智能体完成后流式推送结果
    """
    async def event_stream():
        workflow_id = f"wf_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shared_state = {
            "task": req.task,
            "device_id": req.device_id,
            "context": req.context or {},
            "started_at": datetime.datetime.now().isoformat(),
            "workflow_id": workflow_id,
        }

        # 推送工作流开始
        yield f"data: {json.dumps({'status': 'workflow_start', 'workflow_id': workflow_id, 'agents': list(AGENTS_REGISTRY.keys())}, ensure_ascii=False)}\n\n"

        # 按顺序执行每个智能体
        for agent_id in WORKFLOW_GRAPH["nodes"]:
            agent = AGENTS_REGISTRY[agent_id]
            yield f"data: {json.dumps({'status': 'agent_start', 'agent_id': agent_id, 'agent_name': agent['name'], 'icon': agent['icon']}, ensure_ascii=False)}\n\n"

            # 构造智能体输入
            if agent_id == "diagnostician":
                device_context = await _fetch_device_context(req.device_id)
                user_prompt = f"任务：{req.task}\n\n设备运行数据：\n{device_context}\n\n请诊断当前设备状态，识别异常模式。"
            elif agent_id == "root_cause_analyst":
                anomaly_summary = shared_state.get("diagnostician_output", "无诊断结果")
                user_prompt = f"基于以下诊断结果，进行根因分析：\n{anomaly_summary}"
            elif agent_id == "maintenance_planner":
                root_causes = shared_state.get("root_cause_analyst_output", "无根因分析")
                user_prompt = f"基于以下根因分析，制定维保方案：\n{root_causes}"
            elif agent_id == "report_generator":
                user_prompt = f"汇总以下工作流结果，生成最终报告：\n\n诊断：{shared_state.get('diagnostician_output', '')}\n\n根因：{shared_state.get('root_cause_analyst_output', '')}\n\n维保：{shared_state.get('maintenance_planner_output', '')}"
            else:
                user_prompt = "执行任务"

            # 调用 LLM
            output = await _call_llm(agent["system_prompt"], user_prompt)
            shared_state[f"{agent_id}_output"] = output

            yield f"data: {json.dumps({'status': 'agent_complete', 'agent_id': agent_id, 'agent_name': agent['name'], 'output': output}, ensure_ascii=False)}\n\n"

            # 短暂暂停，让前端能感知到流程
            await asyncio.sleep(0.3)

        # 推送工作流结束
        yield f"data: {json.dumps({'status': 'workflow_complete', 'workflow_id': workflow_id, 'completed_at': datetime.datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
