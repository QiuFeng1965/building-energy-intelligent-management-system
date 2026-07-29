# -*- coding: utf-8 -*-
"""
数据库连接管理：连接池 + 重试 + 异常兜底
支持 SQLite（开发）和 PostgreSQL（生产）双模式
"""
import sqlite3
import logging
import time
import threading
from contextlib import contextmanager
from typing import Iterator

from app.core.config import DB_PATH, DB_TYPE, DATABASE_URL

logger = logging.getLogger(__name__)


class DBUnavailableError(Exception):
    """数据库不可用时抛出，由 FastAPI 全局异常处理器返回 503"""


# ===== PostgreSQL 模式 =====
if DB_TYPE == "postgres" and DATABASE_URL:
    try:
        import psycopg2
        from psycopg2 import pool as psycopg2_pool
        # 创建连接池（生产环境复用连接，提升性能）
        # 注意：psycopg2 ThreadedConnectionPool 原生不支持 pool_recycle/pool_pre_ping，
        # 建议在生产环境通过外层调度定期重建连接池（建议 pool_recycle=1800 秒），
        # 避免长连接因数据库侧 idle timeout 被动断开后首次请求失败。
        # 下文 get_conn 中的 SELECT 1 健康检查等价于 pool_pre_ping，取出连接前探测可用性。
        _pg_pool = psycopg2_pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DATABASE_URL
        )
        logger.info("PostgreSQL 连接池已初始化")

        @contextmanager
        def get_conn(max_retries: int = 2, retry_delay: float = 0.5) -> Iterator:
            """PostgreSQL 连接上下文管理器（从连接池获取）"""
            last_exc = None
            for attempt in range(max_retries + 1):
                conn = None
                try:
                    conn = _pg_pool.getconn()
                    # autocommit=False，使用事务
                    # 健康检查
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                    try:
                        yield conn
                    finally:
                        if conn:
                            _pg_pool.putconn(conn)
                    return
                except (psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                    last_exc = e
                    logger.warning(f"PG 连接失败 attempt={attempt+1}/{max_retries+1}: {e}")
                    if conn:
                        try:
                            _pg_pool.putconn(conn, close=True)
                        except Exception:
                            pass
                    if attempt < max_retries:
                        time.sleep(retry_delay * (attempt + 1))
            raise DBUnavailableError(f"PostgreSQL 连续 {max_retries+1} 次不可用: {last_exc}")

    except ImportError:
        logger.error("psycopg2 未安装，回退到 SQLite 模式")
        DB_TYPE = "sqlite"


# ===== SQLite 模式（默认/开发环境） =====
if DB_TYPE != "postgres" or not DATABASE_URL:

    _sqlite_local = threading.local()

    def _get_sqlite_conn():
        """线程级连接复用 — 同一线程内不重复建连"""
        conn = getattr(_sqlite_local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA synchronous=NORMAL;")  # WAL 模式下 NORMAL 更快
            _sqlite_local.conn = conn
        return conn

    @contextmanager
    def get_conn(max_retries: int = 2, retry_delay: float = 0.5) -> Iterator[sqlite3.Connection]:
        """
        SQLite 连接上下文管理器，统一连接获取/重试/超时。
        配合 asyncio.to_thread 使用以避免阻塞事件循环。
        线程级连接复用：同一线程内不重复建连，退出时不 close（复用），
        commit/rollback 仍由 with 块内代码管理。
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            conn = None
            try:
                conn = _get_sqlite_conn()
                conn.execute("SELECT 1").fetchone()  # 健康检查（连接复用前探测可用性）
                try:
                    yield conn
                finally:
                    # 不关闭连接（线程级复用）；commit/rollback 由 with 块内代码管理
                    pass
                return
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                last_exc = e
                logger.warning(f"DB 连接失败 attempt={attempt+1}/{max_retries+1}: {e}")
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    _sqlite_local.conn = None  # 清理坏连接，下次重连
                if attempt < max_retries:
                    time.sleep(retry_delay * (attempt + 1))
        raise DBUnavailableError(f"数据库连续 {max_retries+1} 次不可用: {last_exc}")


def run_in_thread(func):
    """装饰器：把同步 DB 函数丢到线程池，避免阻塞 async 事件循环。"""
    from functools import wraps
    import asyncio

    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper
