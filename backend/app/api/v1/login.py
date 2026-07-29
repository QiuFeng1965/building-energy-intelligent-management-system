# -*- coding: utf-8 -*-
"""
登录路由
"""
from fastapi import APIRouter, HTTPException, Request

from app.core.security import LoginRequest, login
from app.core.rate_limit import limiter

router = APIRouter()


@router.post("/api/login")
@limiter.limit("5/minute")
async def login_api(request: Request, body: LoginRequest):
    """登录接口：使用 bcrypt 验证密码，签发 JWT token（限流 5 次/分钟）"""
    result = login(body.username, body.password)
    if result["status"] == "error":
        raise HTTPException(status_code=401, detail=result["message"])
    return result
