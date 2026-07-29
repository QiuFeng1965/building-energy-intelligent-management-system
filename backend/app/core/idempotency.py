# -*- coding: utf-8 -*-
"""
接口幂等性装饰器
- 基于 X-Idempotency-Key 头实现防重放防并发
- 同一 key + 请求体 hash 在 TTL 内返回缓存响应
- 不同请求体同 key 返回 409 Conflict
"""
import hashlib
import json
import time
from functools import wraps
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

import logging

logger = logging.getLogger(__name__)

# 幂等记录表 DDL
_IDEMPOTENT_DDL = """
CREATE TABLE IF NOT EXISTS sys_idempotent_records (
    key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    response_body TEXT,
    status_code INTEGER,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idempotent_expires ON sys_idempotent_records(expires_at);
"""


def _init_table():
    """初始化幂等记录表（幂等操作）"""
    try:
        from app.core.database import get_conn
        with get_conn() as conn:
            conn.executescript(_IDEMPOTENT_DDL)
            conn.commit()
    except Exception as e:
        logger.warning(f"初始化幂等记录表失败（可能已存在）: {e}")


def idempotent(key_header: str = "X-Idempotency-Key", ttl: int = 300):
    """
    幂等性装饰器：
    - 客户端必须传 X-Idempotency-Key（UUID）
    - 同一 key + 请求体 hash 在 TTL 内返回缓存响应
    - 不同请求体同 key 返回 409 Conflict

    用法：
        @router.post("/api/workorders")
        @idempotent(key_header="X-Idempotency-Key", ttl=300)
        async def create_workorder(...):
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            key = request.headers.get(key_header)
            if not key:
                # 未传幂等键时直接执行（向后兼容）
                return await func(request, *args, **kwargs)

            # 请求体 hash（防同一 key 不同 body）
            body = await request.body()
            req_hash = hashlib.sha256(body).hexdigest()

            # 初始化表（首次调用）
            _init_table()

            from app.core.database import get_conn
            now = time.time()

            with get_conn() as conn:
                # 查历史记录
                row = conn.execute(
                    "SELECT request_hash, response_body, status_code FROM sys_idempotent_records "
                    "WHERE key = ? AND expires_at > ?",
                    [key, now]
                ).fetchone()

                if row:
                    if row["request_hash"] != req_hash:
                        raise HTTPException(
                            status_code=409,
                            detail="幂等键与请求体不匹配，可能存在冲突"
                        )
                    # 返回缓存响应
                    cached = json.loads(row["response_body"])
                    return JSONResponse(
                        status_code=row["status_code"],
                        content=cached,
                        headers={"Idempotent-Replay": "true"}
                    )

                # 执行原函数
                response = await func(request, *args, **kwargs)

                # 提取响应体和状态码
                if hasattr(response, "body"):
                    resp_body = response.body.decode("utf-8") if isinstance(response.body, bytes) else json.dumps(response.body)
                    status = response.status_code
                elif isinstance(response, dict):
                    resp_body = json.dumps(response, ensure_ascii=False, default=str)
                    status = 200
                else:
                    resp_body = json.dumps({"data": str(response)}, ensure_ascii=False, default=str)
                    status = 200

                # 缓存响应
                conn.execute(
                    "INSERT OR REPLACE INTO sys_idempotent_records "
                    "(key, request_hash, response_body, status_code, created_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [key, req_hash, resp_body, status, now, now + ttl]
                )
                # 清理过期记录（惰性清理）
                conn.execute("DELETE FROM sys_idempotent_records WHERE expires_at <= ?", [now])
                conn.commit()

            return response
        return wrapper
    return decorator
