# -*- coding: utf-8 -*-
"""
路由级异常统一处理工具
- 避免在 except Exception 中将内部错误信息直接返回给客户端
- 详细堆栈仅写入日志，客户端只收到通用提示
"""
import logging
from typing import Any, Optional
from fastapi.responses import JSONResponse


def handle_route_error(
    exc: Exception,
    logger: logging.Logger,
    action: str = "操作",
    extra_fields: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """
    路由级异常统一处理：
    - 记录完整堆栈到日志（含 trace_id）
    - 返回通用错误消息给客户端（不泄露内部信息）

    用法：
        try:
            ...
        except Exception as e:
            return handle_route_error(e, logger, "查询工单列表")

    如需在响应中保留额外字段（如 data: [] 以兼容前端）：
        return handle_route_error(e, logger, "查询设备", extra_fields={"data": []})
    """
    logger.exception(f"{action}失败: {exc}")
    content: dict[str, Any] = {
        "status": "error",
        "message": f"{action}失败，请稍后重试或联系管理员",
    }
    if extra_fields:
        content.update(extra_fields)
    return JSONResponse(
        status_code=500,
        content=content,
    )


def safe_error_dict(
    exc: Exception,
    logger: logging.Logger,
    action: str = "操作",
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    与 handle_route_error 等价的字典版本（仅记录日志，返回通用消息 dict）。
    适用于无法返回 JSONResponse 的场景（如被 try/except 包裹后还需要继续走 fastapi 默认序列化）。

    注意：返回 dict 时 HTTP 状态码为 200，前端依据 status 字段判断错误。
    生产环境推荐使用 handle_route_error（返回 500）。
    """
    logger.exception(f"{action}失败: {exc}")
    payload: dict[str, Any] = {
        "status": "error",
        "message": f"{action}失败，请稍后重试或联系管理员",
    }
    if extra_fields:
        payload.update(extra_fields)
    return payload
