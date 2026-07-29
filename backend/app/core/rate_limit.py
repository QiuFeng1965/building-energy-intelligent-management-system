# -*- coding: utf-8 -*-
"""
API 限流配置
使用 slowapi 实现 IP 级别限流，防止暴力破解和接口滥用
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 基于客户端 IP 的限流器
limiter = Limiter(key_func=get_remote_address)

# 限流规则
RATE_LIMITS = {
    "login": "5/minute",      # 登录：5 次/分钟（防暴力破解）
    "chat": "10/minute",      # AI 对话：10 次/分钟
    "upload": "20/minute",    # 文件上传：20 次/分钟
    "default": "60/minute",   # 默认：60 次/分钟
}
