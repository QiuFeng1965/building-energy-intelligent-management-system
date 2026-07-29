# -*- coding: utf-8 -*-
"""
工单领域模型 — 聚合根
状态机、状态流转规则、业务不变量内聚到领域层
"""
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Set


class WorkOrderStatus(str, Enum):
    """工单状态枚举"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# 状态流转规则表
_TRANSITIONS: dict[WorkOrderStatus, Set[WorkOrderStatus]] = {
    WorkOrderStatus.PENDING: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.REJECTED},
    WorkOrderStatus.IN_PROGRESS: {WorkOrderStatus.COMPLETED, WorkOrderStatus.PENDING},
    WorkOrderStatus.COMPLETED: {WorkOrderStatus.VERIFIED},
    WorkOrderStatus.VERIFIED: set(),   # 终态
    WorkOrderStatus.REJECTED: set(),   # 终态
}

# 状态中文标签
STATUS_LABELS = {
    WorkOrderStatus.PENDING: "待处理",
    WorkOrderStatus.IN_PROGRESS: "处理中",
    WorkOrderStatus.COMPLETED: "已完成",
    WorkOrderStatus.VERIFIED: "已验证",
    WorkOrderStatus.REJECTED: "已拒绝",
}


class InvalidTransitionError(Exception):
    """非法状态流转异常（领域异常，不依赖 HTTP 层）"""
    def __init__(self, current: WorkOrderStatus, target: WorkOrderStatus):
        self.current = current
        self.target = target
        allowed = _TRANSITIONS.get(current, set())
        super().__init__(
            f"非法状态流转: {current.value} → {target.value}，"
            f"当前状态仅可流转到 {sorted(s.value for s in allowed) or ['（终态，不可流转）']}"
        )


@dataclass
class WorkOrder:
    """
    工单聚合根 — 含状态机行为
    业务规则内聚：状态流转、completed_at 回填、退回清理
    """
    order_id: str
    device_id: str
    status: WorkOrderStatus
    diagnosis_title: str = ""
    rag_advice: str = ""
    maintenance_action: str = ""
    repair_cost: float = 0.0
    user_feedback: str = ""
    completed_at: Optional[str] = None
    created_at: str = ""

    def can_transition_to(self, target: WorkOrderStatus) -> bool:
        """检查是否可以流转到目标状态"""
        return target in _TRANSITIONS.get(self.status, set())

    def transition_to(self, target: WorkOrderStatus) -> None:
        """
        执行状态流转 — 领域行为，无 HTTP 依赖
        - 校验流转合法性
        - 流转到 COMPLETED 时回填 completed_at
        - 退回 PENDING 时清空 completed_at
        """
        if not self.can_transition_to(target):
            raise InvalidTransitionError(self.status, target)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 流转到 COMPLETED 时回填 completed_at（若尚未设置）
        if target == WorkOrderStatus.COMPLETED and not self.completed_at:
            self.completed_at = now

        # 退回 PENDING 时清空 completed_at（恢复待处理）
        if target == WorkOrderStatus.PENDING and self.completed_at:
            self.completed_at = None

        self.status = target

    @staticmethod
    def valid_statuses() -> set[str]:
        """所有合法状态值"""
        return {s.value for s in WorkOrderStatus}

    @staticmethod
    def label(status: WorkOrderStatus | str) -> str:
        """获取状态中文标签"""
        if isinstance(status, str):
            status = WorkOrderStatus(status)
        return STATUS_LABELS.get(status, status.value)
