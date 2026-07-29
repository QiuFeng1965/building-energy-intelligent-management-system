# -*- coding: utf-8 -*-
"""
请求级中间件
- TraceMiddleware：为每个请求注入 trace_id（链路追踪）
- SecurityHeadersMiddleware：注入安全响应头（CSP / X-Frame-Options / X-Content-Type-Options 等）
- AuthMiddleware：统一 JWT 鉴权（白名单机制），避免路由遗漏鉴权
- 响应头回写 X-Trace-Id，便于前端/运维定位问题
"""
import os
import uuid
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.logging_config import trace_id_var, user_var

logger = logging.getLogger(__name__)


# ===== 鉴权白名单 =====
# 精确匹配：这些路径无需鉴权（登录、健康检查、前端遥测上报、公钥）
AUTH_WHITELIST_EXACT = {
    "/api/login",
    "/health",
    "/readiness",
    "/api/version",
    "/api/observability/web-vitals",
    "/api/observability/frontend-error",
    "/api/push/vapid_public_key",
}
# 前缀匹配：WebSocket handshake 单独处理、OpenAPI 文档
AUTH_WHITELIST_PREFIXES = (
    "/ws/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    统一鉴权中间件（白名单机制）。
    所有 /api/* 接口默认需要 JWT，白名单内路径放行。
    避免逐路由添加 dependencies 导致遗漏。

    设计要点：
    1. 放行 OPTIONS 预检请求（CORS）
    2. 放行非 /api 路径（静态资源、文档）
    3. 放行白名单路径
    4. 其余 /api/* 请求校验 Bearer JWT，无效则 401
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # 1. 放行 CORS 预检
        if method == "OPTIONS":
            return await call_next(request)

        # 2. 放行非 API 路径
        if not path.startswith("/api") and not path.startswith("/ws"):
            return await call_next(request)

        # 3. 白名单放行
        if path in AUTH_WHITELIST_EXACT:
            return await call_next(request)
        if any(path.startswith(p) for p in AUTH_WHITELIST_PREFIXES):
            return await call_next(request)

        # 4. JWT 校验
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "detail": "未提供认证凭证"},
            )
        token = auth[7:]
        try:
            # 延迟导入避免循环依赖
            from app.core.security import decode_token
            payload = decode_token(token)
            # 同步 user_var（TraceMiddleware 也做了，但中间件顺序不保证）
            user_var.set(payload.get("sub", "-"))
        except Exception as exc:
            status_code = getattr(exc, "status_code", 401)
            detail = getattr(exc, "detail", "无效凭证")
            return JSONResponse(
                status_code=status_code,
                content={"status": "error", "detail": detail},
            )

        return await call_next(request)


class TraceMiddleware(BaseHTTPMiddleware):
    """
    为每个 HTTP 请求生成唯一 trace_id，
    贯穿整个请求处理链路（含异步任务、子日志）。
    """

    async def dispatch(self, request: Request, call_next):
        # 优先复用上游传入的 trace_id（微服务链路追踪），否则生成新的
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        trace_id_var.set(trace_id)

        # 尝试从 JWT 提取用户名（不强制，失败则留空）
        try:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                # 延迟导入避免循环依赖
                from app.core.security import decode_token
                payload = decode_token(auth[7:])
                user_var.set(payload.get("sub", "-"))
        except Exception:
            # 未登录或 token 无效，用户字段留空
            pass

        # 计时
        start_ts = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            # 异常也要记录链路日志
            elapsed_ms = round((time.perf_counter() - start_ts) * 1000, 2)
            logger.error(
                "请求处理异常",
                extra={
                    "method": method,
                    "path": path,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                },
            )
            raise

        # 回写 trace_id 到响应头
        elapsed_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id

        # 注入 API 版本号到响应头（所有接口统一返回）
        from app.core.config import API_VERSION
        response.headers["X-API-Version"] = API_VERSION

        # 访问日志（结构化）
        logger.info(
            "请求完成",
            extra={
                "method": method,
                "path": path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    注入安全响应头，加固前端安全：
    - X-Content-Type-Options: nosniff 阻止 MIME 嗅探
    - X-Frame-Options: SAMEORIGIN 阻止点击劫持（只允许同源 iframe）
    - Referrer-Policy: strict-origin-when-cross-origin 控制 Referer 泄露
    - X-XSS-Protection: 1; mode=block 启用浏览器 XSS 过滤器（旧版浏览器）
    - Permissions-Policy: 限制摄像头/麦克风/地理位置等敏感权限
    - Strict-Transport-Security: 强制 HTTPS（仅 HTTPS 生效）
    - Content-Security-Policy: 限制资源加载来源（开发环境宽松，生产环境严格）
    """

    # 环境判定：生产环境收紧 CSP
    _is_production = os.environ.get("ENV", "development").lower() in ("production", "prod")

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 通用安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        # HSTS：仅 HTTPS 时生效，max-age=1年，含子域名
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # CSP：开发环境允许 unsafe-inline / unsafe-eval（Vue/Vite 需要），
        # 生产环境收紧：移除 unsafe-eval、限制 connect-src 仅同源 + 已知可信域名
        if self._is_production:
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' wss: https://api.open-meteo.com; "
                "media-src 'self' data: blob:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'self'"
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' ws: wss: http://localhost:* http://127.0.0.1:* https://api.open-meteo.com; "
                "media-src 'self' data: blob:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'self'"
            )
        response.headers["Content-Security-Policy"] = csp

        return response
