# -*- coding: utf-8 -*-
"""
结构化 JSON 日志配置 + trace_id 链路追踪
- 所有日志输出为 JSON 格式，便于 ELK/Loki 采集
- 每条日志自动携带 trace_id（请求级链路追踪）
- 同时输出到控制台和文件（按天轮转）
"""
import os
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from contextvars import ContextVar

from app.core.config import BACKEND_DIR

# 请求级 trace_id（ContextVar 天然支持 asyncio 任务隔离）
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
user_var: ContextVar[str] = ContextVar("user", default="-")

# 日志目录
LOG_DIR = os.path.join(BACKEND_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class JsonFormatter(logging.Formatter):
    """JSON 格式化器：每条日志输出为一个 JSON 对象"""

    # 标准日志级别映射（数值 → 大写字符串）
    LEVEL_NAMES = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARN",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "FATAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        # 时间戳（ISO 8601，带时区）
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # 基础字段
        log_entry = {
            "ts": ts,
            "level": self.LEVEL_NAMES.get(record.levelno, record.levelname),
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": trace_id_var.get(""),
            "user": user_var.get(""),
        }

        # 异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 额外字段（logger.info("...", extra={...}) 传入的字段）
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "taskName",
                "message",
            ) and not key.startswith("_"):
                try:
                    json.dumps(value, ensure_ascii=False)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """
    初始化全局日志配置。
    - 控制台：JSON 格式，便于开发期快速查看
    - 文件：按天轮转，保留 30 天，便于审计
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清空已有 handler（避免重复输出）
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = JsonFormatter()

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件 handler（按天轮转，保留 30 天）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "app.jsonl"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 降低第三方库日志噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
