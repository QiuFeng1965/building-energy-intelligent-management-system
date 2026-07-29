# -*- coding: utf-8 -*-
"""
AI Agent Function Calling 工具定义
- 适配 OpenAI / DeepSeek / GPT 兼容的 Function Calling 协议
- 内置安全规则：参数边界、极端值拦截、高危操作人工确认
- 工具清单：
  1. adjust_device_power  — 调节设备功率
  2. dispatch_workorder   — 派发工单
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ================= 工具 Schema 定义（OpenAI Function Calling 格式） =================

ADJUST_DEVICE_POWER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "adjust_device_power",
        "description": (
            "调节目标设备的运行功率百分比。当 RUL 告警或 COP 严重偏离时调用。"
            "功率取值范围 0-100，10 以下视为停机，90 以上视为满载。"
            "极端值（<10 或 >90）将被安全拦截层强制要求人工二次确认。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "目标设备 ID（来自 dim_devices.device_id）"
                },
                "power_pct": {
                    "type": "number",
                    "description": "目标功率百分比，范围 [0, 100]",
                    "minimum": 0,
                    "maximum": 100
                },
                "reason": {
                    "type": "string",
                    "description": "调节原因（必须包含 RUL 或 COP 等量化依据）"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "紧急程度"
                }
            },
            "required": ["device_id", "power_pct", "reason", "urgency"]
        }
    }
}

DISPATCH_WORKORDER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "dispatch_workorder",
        "description": (
            "向现场维保团队派发工单。当设备故障确诊或 RUL<7 天时调用。"
            "工单优先级 P0 将自动升级并触发短信通知。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "故障设备 ID"},
                "title": {"type": "string", "description": "工单标题（不超过 50 字）"},
                "description": {"type": "string", "description": "故障详细描述与建议处理步骤"},
                "priority": {
                    "type": "string",
                    "enum": ["P0", "P1", "P2", "P3"],
                    "description": "P0=紧急 P1=高 P2=中 P3=低"
                },
                "parts_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "所需备件清单（可为空）"
                },
                "expected_downtime_hours": {
                    "type": "number",
                    "description": "预计停机时长（小时）",
                    "minimum": 0
                }
            },
            "required": ["device_id", "title", "description", "priority"]
        }
    }
}


# 全量工具清单（注入 LLM 的 tools 参数）
AGENT_TOOLS = [ADJUST_DEVICE_POWER_SCHEMA, DISPATCH_WORKORDER_SCHEMA]

# 工具名 → Schema 映射，便于按名查找
TOOL_REGISTRY = {t["function"]["name"]: t for t in AGENT_TOOLS}


# ================= 安全规则 =================

class SafetyViolationError(Exception):
    """安全拦截层抛出的违规异常"""
    def __init__(self, rule: str, detail: str, severity: str = "high"):
        self.rule = rule
        self.detail = detail
        self.severity = severity
        super().__init__(f"[安全拦截] {rule}: {detail}")


# 极端参数阈值
POWER_EXTREME_LOW = 10      # < 10% 视为停机
POWER_EXTREME_HIGH = 90     # > 90% 视为满载
POWER_SINGLE_STEP_MAX = 30  # 单次调节幅度上限（防剧烈波动损坏设备）


def validate_adjust_device_power(args: dict, current_power_pct: Optional[float] = None) -> dict:
    """
    adjust_device_power 安全校验
    - 参数边界
    - 极端值标记需人工确认
    - 单次调节幅度限制
    - reason 必须量化
    返回 sanitize 后的 args（含 need_human_confirm 标志）
    """
    device_id = args.get("device_id")
    power_pct = args.get("power_pct")
    reason = args.get("reason", "")
    urgency = args.get("urgency", "medium")

    if not device_id or not isinstance(device_id, str):
        raise SafetyViolationError("参数缺失", "device_id 必须为非空字符串")

    if power_pct is None or not isinstance(power_pct, (int, float)):
        raise SafetyViolationError("参数类型错误", "power_pct 必须为数字")
    power_pct = float(power_pct)

    # 硬边界：超出 0-100 直接拒绝（疑似大模型幻觉）
    if power_pct < 0 or power_pct > 100:
        raise SafetyViolationError(
            "参数越界",
            f"power_pct={power_pct} 超出 [0,100] 硬边界，疑似大模型幻觉",
            severity="critical"
        )

    need_human_confirm = False
    human_confirm_reasons = []

    # 极端值拦截：标记人工确认
    if power_pct < POWER_EXTREME_LOW:
        need_human_confirm = True
        human_confirm_reasons.append(f"功率 {power_pct}% 低于停机阈值 {POWER_EXTREME_LOW}%")
    if power_pct > POWER_EXTREME_HIGH:
        need_human_confirm = True
        human_confirm_reasons.append(f"功率 {power_pct}% 高于满载阈值 {POWER_EXTREME_HIGH}%")

    # 单次调节幅度限制（防剧烈波动损坏设备）
    if current_power_pct is not None:
        delta = abs(power_pct - current_power_pct)
        if delta > POWER_SINGLE_STEP_MAX:
            need_human_confirm = True
            human_confirm_reasons.append(
                f"单次调节幅度 {delta:.1f}% 超过 {POWER_SINGLE_STEP_MAX}% 限制"
            )

    # reason 必须包含量化依据（RUL/COP/温度等关键词），防止 LLM 编造
    quantified_keywords = ["rul", "cop", "温度", "电流", "振动", "压力", "故障", "告警"]
    if not any(kw.lower() in reason.lower() for kw in quantified_keywords):
        raise SafetyViolationError(
            "依据不足",
            f"reason 必须包含量化依据（{quantified_keywords}），当前: {reason}"
        )

    return {
        "device_id": device_id,
        "power_pct": power_pct,
        "reason": reason,
        "urgency": urgency,
        "need_human_confirm": need_human_confirm,
        "human_confirm_reasons": human_confirm_reasons,
    }


def validate_dispatch_workorder(args: dict) -> dict:
    """
    dispatch_workorder 安全校验
    - 标题长度
    - P0 工单必须含备件清单或停机时长
    """
    device_id = args.get("device_id")
    title = args.get("title", "")
    description = args.get("description", "")
    priority = args.get("priority", "P2")
    parts_list = args.get("parts_list", [])
    expected_downtime_hours = args.get("expected_downtime_hours")

    if not device_id:
        raise SafetyViolationError("参数缺失", "device_id 必填")
    if not title or len(title) > 50:
        raise SafetyViolationError("标题校验", f"标题长度必须在 1-50 字之间，当前: {len(title)}")
    if priority not in {"P0", "P1", "P2", "P3"}:
        raise SafetyViolationError("优先级非法", f"priority={priority} 不在合法枚举内")

    need_human_confirm = False
    human_confirm_reasons = []

    # P0 工单必须有备件清单或预计停机时长
    if priority == "P0":
        if not parts_list and expected_downtime_hours is None:
            need_human_confirm = True
            human_confirm_reasons.append("P0 工单需提供备件清单或预计停机时长以供确认")

    return {
        "device_id": device_id,
        "title": title,
        "description": description,
        "priority": priority,
        "parts_list": parts_list,
        "expected_downtime_hours": expected_downtime_hours,
        "need_human_confirm": need_human_confirm,
        "human_confirm_reasons": human_confirm_reasons,
    }


# 工具名 → 校验器映射
VALIDATORS = {
    "adjust_device_power": validate_adjust_device_power,
    "dispatch_workorder": validate_dispatch_workorder,
}


def sanitize_tool_call(tool_name: str, args: dict, context: Optional[dict] = None) -> dict:
    """
    工具调用统一安全入口
    - context 可携带 current_power_pct 等运行时上下文
    返回 sanitize 后的参数字典
    """
    validator = VALIDATORS.get(tool_name)
    if not validator:
        raise SafetyViolationError("未知工具", f"工具 {tool_name} 未在注册表中")

    if tool_name == "adjust_device_power":
        current_power = (context or {}).get("current_power_pct")
        return validator(args, current_power=current_power)
    return validator(args)
