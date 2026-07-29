# -*- coding: utf-8 -*-
"""
RUL（剩余使用寿命）领域模型
健康度评分算法、RUL 预测、维保建议 — 从路由层下沉到领域层
"""
from dataclasses import dataclass
from typing import Optional


# 健康度评分权重
HEALTH_WEIGHTS = {
    "cop_degradation": 0.30,   # COP 衰减度
    "stability":       0.20,   # 运行稳定性
    "loading_rate":    0.20,   # 负载率合理性
    "fault_freq":      0.15,   # 故障频率
    "delta_temp":      0.15,   # 温差异常度
}


@dataclass
class HealthScore:
    """
    设备健康度评分 — 领域值对象
    将评分算法内聚到领域层，路由层只需调用
    """
    cop_degradation: float
    stability: float
    loading_rate: float
    fault_freq: float
    delta_temp: float

    def compute(self) -> float:
        """计算综合健康度评分（0-100）"""
        score = (
            self.cop_degradation * HEALTH_WEIGHTS["cop_degradation"] +
            self.stability * HEALTH_WEIGHTS["stability"] +
            self.loading_rate * HEALTH_WEIGHTS["loading_rate"] +
            self.fault_freq * HEALTH_WEIGHTS["fault_freq"] +
            self.delta_temp * HEALTH_WEIGHTS["delta_temp"]
        )
        return round(max(0, min(100, score)), 1)

    @property
    def grade(self) -> str:
        """健康度等级"""
        score = self.compute()
        if score >= 85:
            return "优秀"
        elif score >= 70:
            return "良好"
        elif score >= 50:
            return "一般"
        elif score >= 30:
            return "警告"
        else:
            return "危险"


@dataclass
class RULPrediction:
    """
    RUL 预测结果 — 领域值对象
    """
    device_id: str
    health_score: float
    predicted_failure: str
    maintenance_action: str
    equipment_name: str = ""
    vibration_mm_s: float = 0.0
    status: str = ""

    @property
    def is_critical(self) -> bool:
        """是否为临界状态"""
        return self.health_score < 50
