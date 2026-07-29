# -*- coding: utf-8 -*-
"""
AI Agent 自动化决策流路由
- /api/agent/decision  : 调用大模型获取可执行 Action（带断路器保护）
- /api/agent/execute   : 执行 Action（带安全拦截 + 幂等性）
- /api/agent/actions   : 查询待执行/已执行 Action 列表

设计要点：
1. 复用 ai_service.ai_client 调用 LLM
2. 工具 Schema 来自 agent_tools.AGENT_TOOLS
3. 安全拦截层：sanitize_tool_call 在 decision 和 execute 阶段双重校验
4. 幂等性：@idempotent 装饰器基于 X-Idempotency-Key 防重放
5. 断路器：LLM 调用经 llm_breaker 保护，OPEN 时降级返回
6. 高危操作 need_human_confirm=True 时不立即执行，写入待确认队列
"""
import json
import uuid
import logging
import datetime
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.database import get_conn
from app.core.rate_limit import limiter
from app.core.idempotency import idempotent
from app.core.circuit_breaker import llm_breaker, CircuitOpenError
from app.services.ai_service import ai_client
from app.core.config import AI_API_KEY, MODEL_TEXT
from app.services.agent_tools import (
    AGENT_TOOLS,
    SafetyViolationError,
    sanitize_tool_call,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ================= Pydantic 模型 =================

class DecisionRequest(BaseModel):
    device_id: str
    alarm_context: dict  # 含 rul_days, cop, fault_code, current_power_pct 等


class ExecuteRequest(BaseModel):
    action_id: str
    confirmed_by: Optional[str] = None  # 高危操作人工确认人


# ================= Action 持久化表 =================

_ACTION_DDL = """
CREATE TABLE IF NOT EXISTS sys_agent_actions (
    action_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    decision_reason TEXT,
    need_human_confirm INTEGER DEFAULT 0,
    confirm_reasons_json TEXT,
    status TEXT DEFAULT 'PENDING',  -- PENDING / EXECUTED / REJECTED / FAILED / NO_ACTION
    confirmed_by TEXT,
    executed_at TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_actions_device ON sys_agent_actions(device_id);
CREATE INDEX IF NOT EXISTS idx_agent_actions_status ON sys_agent_actions(status);
"""


def _ensure_table():
    try:
        with get_conn() as conn:
            conn.executescript(_ACTION_DDL)
            conn.commit()
    except Exception as e:
        logger.warning(f"初始化 sys_agent_actions 表失败: {e}")


# ================= LLM 调用（带断路器） =================

async def _call_llm_with_tools(messages: list, tools: list) -> dict:
    """
    调用 LLM 获取 Function Call 决策
    - 断路器 llm_breaker 保护
    - 返回 {tool_name, args, decision_reason} 或降级结果
    """
    if not AI_API_KEY:
        return {
            "tool_name": None,
            "args": None,
            "decision_reason": "AI_API_KEY 未配置，跳过 LLM 决策"
        }

    async def _do_call():
        resp = await ai_client.chat.completions.create(
            model=MODEL_TEXT,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=800,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            return {
                "tool_name": call.function.name,
                "args": json.loads(call.function.arguments),
                "decision_reason": msg.content or ""
            }
        return {
            "tool_name": None,
            "args": None,
            "decision_reason": msg.content or "LLM 未触发工具调用"
        }

    try:
        return await llm_breaker.call(_do_call)
    except CircuitOpenError as e:
        logger.warning(f"LLM 断路器开启，降级响应: {e}")
        return {
            "tool_name": None,
            "args": None,
            "decision_reason": "LLM 服务暂不可用（断路器开启），请稍后重试或人工决策"
        }


# ================= 桩函数（Stub Functions） =================

def _stub_adjust_device_power(args: dict) -> dict:
    """
    实际下发功率调节指令的桩函数
    - 真实场景：通过 Modbus/BACnet/MQTT 下发到边缘网关
    - 桩实现：写入工单表形成审计轨迹
    """
    device_id = args["device_id"]
    power_pct = args["power_pct"]
    order_id = f"PWR-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO fact_work_orders "
                "(order_id, device_id, anomaly_time, diagnosis_title, maintenance_action, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'PENDING', ?)",
                (order_id, device_id, now_str,
                 f"AI 功率调节至 {power_pct}%",
                 f"adjust_device_power: {power_pct}%", now_str)
            )
            conn.commit()
    except Exception as e:
        logger.exception(f"功率调节桩函数写入失败: {e}")

    return {
        "executed": True,
        "order_id": order_id,
        "device_id": device_id,
        "applied_power_pct": power_pct,
        "message": f"已下发功率 {power_pct}% 到设备 {device_id}",
        "transport": "stub_modbus_tcp",
    }


def _stub_dispatch_workorder(args: dict) -> dict:
    """
    实际派发工单的桩函数
    - 真实场景：写入工单系统 + 触发短信/钉钉通知
    - 桩实现：写入 fact_work_orders 表
    """
    device_id = args["device_id"]
    title = args["title"]
    description = args["description"]
    priority = args["priority"]
    parts_list = args.get("parts_list", [])
    order_id = f"WO-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO fact_work_orders "
                "(order_id, device_id, anomaly_time, diagnosis_title, maintenance_action, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, device_id, now_str, title,
                 f"{description} | 优先级:{priority} | 备件:{','.join(parts_list)}",
                 "IN_PROGRESS" if priority == "P0" else "PENDING", now_str)
            )
            conn.commit()
    except Exception as e:
        logger.exception(f"工单派发桩函数写入失败: {e}")

    return {
        "executed": True,
        "order_id": order_id,
        "device_id": device_id,
        "priority": priority,
        "message": f"工单 {order_id} 已派发，优先级 {priority}",
        "notification_sent": priority == "P0",
    }


# 工具名 → 桩函数映射
TOOL_EXECUTORS = {
    "adjust_device_power": _stub_adjust_device_power,
    "dispatch_workorder": _stub_dispatch_workorder,
}


# ================= 路由 =================

@router.post("/api/agent/decision")
@limiter.limit("10/minute")
async def make_decision(request: Request, req: DecisionRequest):
    """
    阶段一：调用 LLM 获取可执行 Action
    - 不实际执行，仅生成并持久化 Action，等待 /execute 调用
    - 安全拦截在生成阶段就进行预校验，标记 need_human_confirm
    """
    _ensure_table()

    ctx = req.alarm_context
    system_prompt = (
        "你是擎翼数字中枢的设备维保决策智能体。基于 RUL 告警与设备运行上下文，"
        "选择最合适的工具进行决策。必须给出量化依据（RUL天数/COP值/温度等）。"
        "禁止在 reason 中编造未提供的数字。"
    )
    user_prompt = (
        f"设备ID: {req.device_id}\n"
        f"告警上下文: {json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
        f"请决策并调用合适的工具。"
    )

    llm_result = await _call_llm_with_tools(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=AGENT_TOOLS,
    )

    action_id = f"act_{uuid.uuid4().hex[:16]}"
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # LLM 未调用工具：记录降级结果
    if not llm_result["tool_name"]:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO sys_agent_actions "
                "(action_id, device_id, tool_name, args_json, decision_reason, status, created_at) "
                "VALUES (?, ?, '', '{}', ?, 'NO_ACTION', ?)",
                [action_id, req.device_id, llm_result["decision_reason"], now_str]
            )
            conn.commit()
        return {
            "status": "success",
            "data": {
                "action_id": action_id,
                "tool_name": None,
                "args": None,
                "decision_reason": llm_result["decision_reason"],
                "need_human_confirm": False,
            }
        }

    tool_name = llm_result["tool_name"]
    raw_args = llm_result["args"] or {}

    # 安全拦截层：预校验
    try:
        sanitized = sanitize_tool_call(tool_name, raw_args, context=ctx)
    except SafetyViolationError as e:
        logger.warning(f"安全拦截拒绝: {e}")
        return {
            "status": "error",
            "code": "SAFETY_VIOLATION",
            "message": str(e),
            "data": {
                "action_id": action_id,
                "tool_name": tool_name,
                "raw_args": raw_args,
                "violation_rule": e.rule,
                "severity": e.severity,
            }
        }

    # 持久化 Action（PENDING 状态）
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sys_agent_actions "
            "(action_id, device_id, tool_name, args_json, decision_reason, "
            "need_human_confirm, confirm_reasons_json, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)",
            [action_id, req.device_id, tool_name,
             json.dumps(sanitized, ensure_ascii=False),
             llm_result["decision_reason"],
             1 if sanitized.get("need_human_confirm") else 0,
             json.dumps(sanitized.get("human_confirm_reasons", []), ensure_ascii=False),
             now_str]
        )
        conn.commit()

    return {
        "status": "success",
        "data": {
            "action_id": action_id,
            "tool_name": tool_name,
            "args": sanitized,
            "decision_reason": llm_result["decision_reason"],
            "need_human_confirm": sanitized.get("need_human_confirm", False),
            "human_confirm_reasons": sanitized.get("human_confirm_reasons", []),
        }
    }


@router.post("/api/agent/execute")
@limiter.limit("20/minute")
@idempotent(key_header="X-Idempotency-Key", ttl=300)
async def execute_action(request: Request, req: ExecuteRequest):
    """
    阶段二：执行 Action
    - 幂等性：基于 X-Idempotency-Key 防重放
    - 安全拦截：执行前再次校验（防 decision 阶段后参数被篡改）
    - 高危操作必须传 confirmed_by
    """
    _ensure_table()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sys_agent_actions WHERE action_id = ?",
            [req.action_id]
        ).fetchone()

    if not row:
        return {"status": "error", "code": "NOT_FOUND", "message": f"Action {req.action_id} 不存在"}

    if row["status"] == "EXECUTED":
        return {"status": "success", "message": "Action 已执行过（幂等）", "data": {"action_id": req.action_id}}
    if row["status"] in ("REJECTED", "FAILED", "NO_ACTION"):
        return {"status": "error", "code": "INVALID_STATE", "message": f"Action 状态为 {row['status']}，不可执行"}

    # 高危操作必须人工确认
    need_confirm = bool(row["need_human_confirm"])
    if need_confirm and not req.confirmed_by:
        return {
            "status": "error",
            "code": "NEED_HUMAN_CONFIRM",
            "message": "此 Action 为高危操作，必须传 confirmed_by 字段人工确认",
            "data": {"confirm_reasons": json.loads(row["confirm_reasons_json"] or "[]")}
        }

    tool_name = row["tool_name"]
    args = json.loads(row["args_json"] or "{}")

    # 执行前二次安全校验（防参数被外部篡改）
    try:
        sanitize_tool_call(tool_name, args)
    except SafetyViolationError as e:
        with get_conn() as conn:
            conn.execute(
                "UPDATE sys_agent_actions SET status='REJECTED' WHERE action_id=?",
                [req.action_id]
            )
            conn.commit()
        return {"status": "error", "code": "SAFETY_VIOLATION", "message": str(e)}

    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return {"status": "error", "code": "NO_EXECUTOR", "message": f"工具 {tool_name} 无执行器"}

    try:
        result = executor(args)
    except Exception as e:
        logger.exception(f"Action 执行失败: {e}")
        with get_conn() as conn:
            conn.execute(
                "UPDATE sys_agent_actions SET status='FAILED', result_json=? WHERE action_id=?",
                [json.dumps({"error": str(e)}, ensure_ascii=False), req.action_id]
            )
            conn.commit()
        return {"status": "error", "code": "EXECUTE_FAILED", "message": str(e)}

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_conn() as conn:
        conn.execute(
            "UPDATE sys_agent_actions SET status='EXECUTED', confirmed_by=?, executed_at=?, result_json=? "
            "WHERE action_id=?",
            [req.confirmed_by, now_str, json.dumps(result, ensure_ascii=False), req.action_id]
        )
        conn.commit()

    return {
        "status": "success",
        "data": {
            "action_id": req.action_id,
            "tool_name": tool_name,
            "result": result,
            "executed_at": now_str,
        }
    }


@router.get("/api/agent/actions")
@limiter.limit("30/minute")
async def list_actions(request: Request, device_id: Optional[str] = None, status: Optional[str] = None):
    """查询 Action 列表"""
    _ensure_table()
    sql = ("SELECT action_id, device_id, tool_name, args_json, decision_reason, "
           "need_human_confirm, status, created_at, executed_at "
           "FROM sys_agent_actions WHERE 1=1")
    params = []
    if device_id:
        sql += " AND device_id = ?"
        params.append(device_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT 100"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return {
        "status": "success",
        "data": {
            "actions": [
                {
                    "action_id": r["action_id"],
                    "device_id": r["device_id"],
                    "tool_name": r["tool_name"],
                    "args": json.loads(r["args_json"] or "{}"),
                    "decision_reason": r["decision_reason"],
                    "need_human_confirm": bool(r["need_human_confirm"]),
                    "status": r["status"],
                    "created_at": r["created_at"],
                    "executed_at": r["executed_at"],
                }
                for r in rows
            ]
        }
    }
