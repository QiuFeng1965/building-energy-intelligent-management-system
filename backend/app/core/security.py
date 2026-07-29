# -*- coding: utf-8 -*-
"""
鉴权体系：JWT + bcrypt
"""
import time
import logging
import jwt
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXP_SECONDS, ADMIN_USERNAME, ADMIN_PASSWORD_HASH

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与 bcrypt 哈希是否匹配"""
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def issue_token(user: str) -> str:
    """签发 JWT token"""
    payload = {
        "sub": user,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXP_SECONDS
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并校验 JWT"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="凭证已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效凭证")


def require_auth(creds: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """路由依赖：要求有效 JWT，返回用户名"""
    if creds is None or creds.credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    payload = decode_token(creds.credentials)
    return payload.get("sub", "unknown")


def require_admin(user: str = Depends(require_auth)) -> str:
    """路由依赖：要求管理员权限"""
    if user != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def login(username: str, password: str) -> dict:
    """登录验证，返回标准响应"""
    if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD_HASH):
        token = issue_token(username)
        logger.info(f"用户 {username} 登录成功")
        return {
            "status": "success",
            "message": "登录成功！",
            "token": token,
            "username": username
        }
    logger.warning(f"登录失败: username={username}")
    return {
        "status": "error",
        "message": "用户名或密码错误"
    }
