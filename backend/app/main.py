# -*- coding: utf-8 -*-
"""
应用入口（精简版）
职责：
1. 创建 FastAPI app（含 lifespan：启动 scheduler）
2. 配置 CORS
3. 注册全局异常处理器（DBUnavailableError → 503，Exception → 500）
4. 挂载所有路由
"""
import os
import logging
import threading
from collections import deque, defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import CORS_ORIGINS
from app.core.database import DBUnavailableError
from app.core.rate_limit import limiter
from app.core.logging_config import setup_logging, trace_id_var
from app.core.middleware import TraceMiddleware, SecurityHeadersMiddleware, AuthMiddleware
from app.services.email_service import generate_and_send_daily_report

# 挂载所有路由
from app.api.v1 import (
    login,
    dashboard,
    devices,
    spatial_twin,
    chat,
    energy,
    report,
    admin,
    websocket,
    health,
    export,
    workorders,
    # ===== 前沿功能模块 =====
    anomaly,         # 功能5：异常检测与根因分析
    carbon,          # 功能1：碳排放追踪与碳中和路径推演
    vpp,             # 功能2：虚拟电厂需求响应
    microgrid,       # 功能3：光储充一体化能量调度
    agents,          # 功能4：多智能体协作
    knowledge,       # 功能6：RAG 知识库增强（多模态+图谱）
    twin3d,          # 功能7：三维实时数字孪生
    ar,              # 功能8：AR 远程运维
    observability,   # 功能9：全链路可观测性
    edge,            # 功能10：边缘计算网关模拟器
    # ===== 能源管理与诊断模块 =====
    rul,             # 设备健康度评分 & RUL 预测
    benchmark,       # 能耗基准对标系统
    multi_energy,    # 多能耦合优化引擎
    # ===== 运营增强模块 =====
    alert_center,    # 智能告警中心 & 多渠道推送
    audit_report,    # 能源审计报告自动生成
    workorder_pro,   # 工单全生命周期管理增强
    # ===== ESG / ROI / 推送服务模块 =====
    esg_report,      # ESG 报告生成器（GRI/SASB）
    roi_calculator,  # 节能改造项目 ROI 测算
    push_service,    # 告警推送后端服务（Web Push / PWA）
    agent_service,   # AI Agent 自动化决策流（Function Calling + 安全拦截 + 幂等）
)

# 初始化结构化 JSON 日志（替代 basicConfig）
setup_logging(level="INFO")
logger = logging.getLogger(__name__)

# 按用户隔离的知识库队列（有界，防止内存膨胀；每个用户独立，避免跨用户泄露）
_user_knowledge_base: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
# 全局锁，保护并发操作（dict 结构变更、管理后台合并视图的原子操作）
_kb_lock = threading.Lock()


def get_user_knowledge_base(user: str) -> deque:
    """获取指定用户的知识库队列（线程安全）"""
    with _kb_lock:
        return _user_knowledge_base[user]


def get_all_knowledge_base() -> deque:
    """获取合并后的全部知识库（管理后台用，只读视图）"""
    with _kb_lock:
        merged = deque(maxlen=200)
        for user_kb in _user_knowledge_base.values():
            merged.extend(user_kb)
        return merged


def delete_knowledge_item_by_index(index: int) -> bool:
    """从合并后的全部知识库中按索引删除条目（线程安全，原子操作）。
    返回 True 表示删除成功，False 表示索引越界。
    """
    with _kb_lock:
        count = 0
        for user_kb in _user_knowledge_base.values():
            kb_len = len(user_kb)
            if index < count + kb_len:
                local_index = index - count
                items = list(user_kb)
                items.pop(local_index)
                user_kb.clear()
                user_kb.extend(items)
                return True
            count += kb_len
        return False

# 初始化调度器
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 定时邮件推送：每天 17:30 发送当日能源与设备日报
    scheduler.add_job(
        generate_and_send_daily_report,  # 直接传入函数名，调度器会自动在后台线程执行
        'cron',
        hour=17,
        minute=30
    )
    scheduler.start()
    logger.info("⏰ 定时邮件推送服务已启动...")

    # 缓存预热 — 避免冷启动第一波流量击穿
    try:
        import httpx
        from app.core.config import API_VERSION
        from app.core.response_cache import warmup_cache

        warmup_endpoints = [
            "/api/dashboard/overview",
            "/api/rul/overview",
            "/api/carbon/overview",
            "/api/esg/overview",
            "/api/twin3d/model",
        ]
        # 内部预热请求（使用本地回环）
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            # 先登录获取 token
            login_resp = await client.post("/api/login", json={
                "username": os.environ.get("ADMIN_USERNAME", "admin"),
                "password": os.environ.get("DEV_ADMIN_PASSWORD_HASH", "admin123"),
            }, timeout=5.0)
            if login_resp.status_code == 200:
                token = login_resp.json().get("token")
                headers = {"Authorization": f"Bearer {token}"}
                count = await warmup_cache(warmup_endpoints, client, headers)
                logger.info(f"🔥 缓存预热完成：{count}/{len(warmup_endpoints)} 个接口已预热")
    except Exception as e:
        logger.warning(f"缓存预热失败（不影响启动）: {e}")

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

# ================= API 版本号接口 =================
@app.get("/api/version")
async def get_api_version():
    """返回当前 API 版本号与系统信息"""
    from app.core.config import API_VERSION
    from app.core.circuit_breaker import get_all_breaker_stats
    from app.core.response_cache import get_cache_stats
    return {
        "status": "success",
        "data": {
            "api_version": API_VERSION,
            "version_prefix": "/api/v1",
            "service": "qingyi-backend",
            "features": [
                "idempotency_key",           # 幂等性支持
                "circuit_breaker",            # 断路器保护
                "cache_singleflight",         # 缓存防击穿
                "cache_ttl_jitter",           # 缓存防雪崩
                "websocket_auth",             # WebSocket 鉴权
                "csp_environment_aware",      # CSP 环境感知
                "jwt_expiry_check",           # JWT 过期校验
            ],
            "circuit_breakers": get_all_breaker_stats(),
            "cache_stats": get_cache_stats(),
        }
    }

# ================= 限流 =================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id", "X-Idempotency-Key", "X-API-Version"],
    max_age=3600,
)

# ================= Gzip 压缩（最小 1KB 才压缩，避免小响应反噬） =================
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ================= 统一鉴权中间件（白名单机制，保护所有 /api/* 接口） =================
app.add_middleware(AuthMiddleware)

# ================= 安全响应头中间件 =================
app.add_middleware(SecurityHeadersMiddleware)

# ================= 链路追踪中间件（最外层，捕获所有请求） =================
app.add_middleware(TraceMiddleware)


# ================= 全局异常处理器 =================
@app.exception_handler(DBUnavailableError)
async def db_unavailable_handler(request: Request, exc: DBUnavailableError):
    logger.critical(
        "数据库不可达",
        extra={"path": request.url.path, "method": request.method, "error": str(exc)},
    )
    return JSONResponse(
        status_code=503,
        content={"status": "error", "code": "DB_UNAVAILABLE", "message": "数据服务暂时不可用，请稍后重试"}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "未捕获异常",
        extra={"path": request.url.path, "method": request.method, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}
    )


# ================= 注册路由 =================
app.include_router(login.router)
app.include_router(dashboard.router)
app.include_router(devices.router)
app.include_router(spatial_twin.router)
app.include_router(chat.router)
app.include_router(energy.router)
app.include_router(report.router)
app.include_router(admin.router)
app.include_router(websocket.router)
app.include_router(health.router)
app.include_router(export.router)
app.include_router(workorders.router)
# ===== 前沿功能模块路由 =====
app.include_router(anomaly.router)
app.include_router(carbon.router)
app.include_router(vpp.router)
app.include_router(microgrid.router)
app.include_router(agents.router)
app.include_router(knowledge.router)
app.include_router(twin3d.router)
app.include_router(ar.router)
app.include_router(observability.router)
app.include_router(edge.router)
# ===== 能源管理与诊断模块路由 =====
app.include_router(rul.router)
app.include_router(benchmark.router)
app.include_router(multi_energy.router)
# ===== 运营增强模块路由 =====
app.include_router(alert_center.router)
app.include_router(audit_report.router)
app.include_router(workorder_pro.router)
# ===== ESG / ROI / 推送服务模块路由 =====
app.include_router(esg_report.router)
app.include_router(roi_calculator.router)
app.include_router(push_service.router)
# ===== AI Agent 决策流模块路由 =====
app.include_router(agent_service.router)
