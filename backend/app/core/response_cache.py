# -*- coding: utf-8 -*-
"""
API 响应缓存层
为只读 GET 接口提供短期内存缓存，减少重复 DB 查询压力。

特性：
- 基于 (path + sorted_query) 作为 key
- 支持 TTL 过期 + 随机抖动防雪崩
- 支持 singleflight 防击穿（同一 key 并发请求合并）
- 线程安全（threading.Lock 仅保护 dict 操作，回源不持锁）
- 容量上限：默认 4096 条，LRU 淘汰
"""
import time
import random
import threading
import asyncio
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional

import logging

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 30  # 秒
_DEFAULT_MAXSIZE = 4096  # 从 256 提升到 4096，避免热点 key 被 LRU 淘汰
_TTL_JITTER_RATIO = 0.2  # TTL 随机抖动比例 ±20%

# 全局缓存实例
_cache_lock = threading.Lock()  # 仅保护 dict 读写（μs 级），不保护回源计算
_cache: OrderedDict = OrderedDict()  # key -> (value, expire_ts)

# singleflight：per-key 异步锁，防止缓存击穿
_inflight_locks: dict[str, asyncio.Lock] = {}
_inflight_locks_guard = threading.Lock()  # 保护 _inflight_locks dict


def _make_key(path: str, query_params: Optional[dict] = None) -> str:
    """构造缓存 key：path + 排序后的 query"""
    if not query_params:
        return path
    sorted_items = sorted(query_params.items())
    qs = "&".join(f"{k}={v}" for k, v in sorted_items)
    return f"{path}?{qs}"


def _get_inflight_lock(key: str) -> asyncio.Lock:
    """获取 per-key 的异步锁（singleflight）"""
    with _inflight_locks_guard:
        if key not in _inflight_locks:
            _inflight_locks[key] = asyncio.Lock()
        return _inflight_locks[key]


def cache_response(ttl: int = _DEFAULT_TTL):
    """
    装饰器：为 FastAPI 路由函数添加内存缓存。
    仅适用于返回 dict/list 的 GET 接口。

    防雪崩：TTL ±20% 随机抖动，避免同一时刻批量过期
    防击穿：singleflight 机制，同一 key 并发请求只回源一次

    用法：
        @router.get("/summary")
        @cache_response(ttl=60)
        async def get_summary(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取 Request 对象（FastAPI 自动注入）
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            # 仅缓存 GET 请求
            if request is not None and request.method != "GET":
                return await func(*args, **kwargs)

            # 构造缓存 key
            if request is not None:
                key = _make_key(request.url.path, dict(request.query_params))
            else:
                key = f"{func.__qualname__}:{str(args)[:100]}:{str(sorted(kwargs.items()))[:200]}"

            # 1. 快速路径：命中直接返回（持锁仅 μs 级）
            now = time.time()
            with _cache_lock:
                if key in _cache:
                    value, expire_ts = _cache[key]
                    if expire_ts > now:
                        _cache.move_to_end(key)
                        logger.debug(f"缓存命中: {key}")
                        return value
                    else:
                        del _cache[key]

            # 2. singleflight：同一 key 并发请求合并
            inflight_lock = _get_inflight_lock(key)
            async with inflight_lock:
                # double-check：可能其他协程已经回源并写入缓存
                now = time.time()
                with _cache_lock:
                    if key in _cache:
                        value, expire_ts = _cache[key]
                        if expire_ts > now:
                            _cache.move_to_end(key)
                            return value
                        else:
                            del _cache[key]

                # 3. 回源计算（不持任何锁，不阻塞事件循环）
                value = await func(*args, **kwargs)

                # 4. 写入缓存 — TTL 随机抖动防雪崩
                jitter = random.uniform(1 - _TTL_JITTER_RATIO, 1 + _TTL_JITTER_RATIO)
                actual_ttl = max(1, int(ttl * jitter))
                with _cache_lock:
                    _cache[key] = (value, now + actual_ttl)
                    _cache.move_to_end(key)
                    while len(_cache) > _DEFAULT_MAXSIZE:
                        _cache.popitem(last=False)

            return value

        wrapper._cached = True
        wrapper._ttl = ttl
        return wrapper
    return decorator


def invalidate_cache(path_prefix: Optional[str] = None) -> int:
    """
    主动失效缓存。
    - 不传参数：清空所有缓存
    - 传 path_prefix：清除所有以该前缀开头的缓存
    返回被清除的条目数。
    """
    with _cache_lock:
        if path_prefix is None:
            n = len(_cache)
            _cache.clear()
            return n
        keys_to_remove = [k for k in _cache if k.startswith(path_prefix)]
        for k in keys_to_remove:
            _cache.pop(k, None)
        return len(keys_to_remove)


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    with _cache_lock:
        now = time.time()
        active = sum(1 for _, (_, exp) in _cache.items() if exp > now)
        expired = len(_cache) - active
        return {
            "total_entries": len(_cache),
            "active_entries": active,
            "expired_entries": expired,
            "max_size": _DEFAULT_MAXSIZE,
            "inflight_keys": len(_inflight_locks),
        }


async def warmup_cache(endpoints: list, client, headers: dict) -> int:
    """
    冷启动缓存预热
    - endpoints: 需要预热的接口列表 ["/api/dashboard/overview", ...]
    - client: httpx.AsyncClient 实例
    - headers: 请求头（含鉴权 token）
    返回成功预热数量
    """
    success = 0
    for ep in endpoints:
        try:
            resp = await client.get(ep, headers=headers, timeout=10.0)
            if resp.status_code < 500:
                success += 1
                logger.info(f"缓存预热成功: {ep}")
            else:
                logger.warning(f"缓存预热失败 {ep}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"缓存预热异常 {ep}: {e}")
    return success
