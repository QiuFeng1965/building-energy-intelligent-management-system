# -*- coding: utf-8 -*-
"""
断路器模式实现
- CLOSED → 失败率超阈值 → OPEN
- OPEN → 经过 cooldown → HALF_OPEN
- HALF_OPEN → 1 次成功 → CLOSED；1 次失败 → OPEN
防止大模型 API 502 时级联故障，保护事件循环不被长耗时重试占满
"""
import time
import asyncio
from enum import Enum
from functools import wraps
from typing import Callable, Any

import logging

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """断路器开启时抛出，调用方应走降级路径"""
    def __init__(self, name: str, cooldown_remaining: float = 0):
        self.name = name
        self.cooldown_remaining = cooldown_remaining
        super().__init__(f"断路器 [{name}] 已开启，剩余冷却时间 {cooldown_remaining:.1f}s")


class CircuitBreaker:
    """
    异步断路器：
    - failure_threshold: 连续失败次数阈值（达到后 OPEN）
    - cooldown: OPEN 状态持续时间（秒）
    - half_open_max_calls: HALF_OPEN 状态最大试探调用数
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 15,
        cooldown: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_ts = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过断路器执行异步函数"""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_ts
                if elapsed > self.cooldown:
                    logger.info(f"断路器 [{self.name}] 从 OPEN → HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError(
                        self.name, self.cooldown - elapsed
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(self.name)
                self._half_open_calls += 1

        # 执行函数（不持锁，避免阻塞其他协程）
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    logger.info(f"断路器 [{self.name}] 从 HALF_OPEN → CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_ts = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"断路器 [{self.name}] HALF_OPEN 失败 → OPEN")
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"断路器 [{self.name}] CLOSED → OPEN "
                    f"(失败 {self._failure_count}/{self.failure_threshold})"
                )
                self._state = CircuitState.OPEN

    def get_stats(self) -> dict:
        """获取断路器状态（供监控接口使用）"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "cooldown": self.cooldown,
        }


# ===== 全局断路器实例 =====
llm_breaker = CircuitBreaker("LLM", failure_threshold=15, cooldown=30.0)
ragflow_breaker = CircuitBreaker("RagFlow", failure_threshold=10, cooldown=60.0)


def get_all_breaker_stats() -> list[dict]:
    """获取所有断路器状态"""
    return [llm_breaker.get_stats(), ragflow_breaker.get_stats()]
