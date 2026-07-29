# -*- coding: utf-8 -*-
"""
健康检查路由
- /health：liveness 探针，进程存活即返回 200
- /readiness：readiness 探针，DB 连通 + 关键表存在才返回 200
供 docker-compose / k8s 探针与负载均衡使用。
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.database import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """liveness：进程存活即 200，不查依赖（轻量）"""
    return {"status": "ok", "service": "qingyi-backend"}


@router.get("/readiness")
async def readiness():
    """readiness：校验 DB 连通 + 关键表存在，任一失败返回 503"""
    checks = {"db": "unknown", "core_tables": "unknown"}
    try:
        with get_conn() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM fact_energy_records")
            count = cur.fetchone()[0]
            checks["db"] = "ok"
            checks["core_tables"] = f"ok(rows={count})"
        return {"status": "ok", "checks": checks}
    except Exception as e:
        logger.exception(f"readiness 检查失败: {e}")
        checks["db"] = f"fail: {e}"
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks}
        )
