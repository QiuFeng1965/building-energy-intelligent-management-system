# -*- coding: utf-8 -*-
"""
统一配置中心
所有路径、密钥、常量集中管理，避免散落在各文件中。
"""
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ===== 路径常量（基于 __file__ 推导，不受工作目录影响）=====
# config.py 位于 app/core/config.py，向上回溯 3 层到 backend/
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
ASSETS_DIR = os.path.join(BACKEND_DIR, "assets")

# 数据库路径（SQLite 模式，开发环境）
DB_PATH = os.path.join(DATA_DIR, "enterprise_building_energy.db")
DB_PATH_LEGACY = os.path.join(DATA_DIR, "building_energy.db")

# RUL 预测模型路径
MODEL_PATH = os.path.join(DATA_DIR, "rul_prediction_model.pkl")

# ===== 数据库类型配置 =====
# 支持 sqlite（开发）和 postgres（生产）
# 生产环境通过 DATABASE_URL 环境变量切换到 PostgreSQL
DB_TYPE = os.environ.get("DB_TYPE", "sqlite")  # sqlite | postgres
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # postgresql+psycopg2://user:pass@host:5432/dbname

# ===== 加载 .env =====
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# ===== AI / LLM 配置 =====
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://opencode.ai/zen/v1")
MODEL_TEXT = os.environ.get("MODEL_TEXT", "gpt-5.2")
MODEL_VISION = os.environ.get("MODEL_VISION", "gpt-5.2")
LLM_TIMEOUT = 30.0
LLM_TOTAL_TIMEOUT = 120
LLM_FALLBACK_REPLY = "【系统提示】AI 服务暂时不可达，已为您切换至本地知识库降级响应。当前建筑综合能耗等级：B级，建议核查暖通系统设定温度。"

# ===== RagFlow 知识库 =====
RAGFLOW_API_URL = os.environ.get("RAGFLOW_API_URL", "http://192.168.244.1/api/v1")
RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "")
RAGFLOW_CHAT_ID = os.environ.get("RAGFLOW_CHAT_ID", "")

# ===== SMTP 邮件 =====
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", "")

# ===== JWT 鉴权 =====
# 安全铁律：JWT_SECRET 必须由 .env 提供，缺失或过短直接终止启动
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET 必须在 .env 中设置且长度≥32 字符，"
        "拒绝使用默认值以防 token 被伪造"
    )
JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = 8 * 3600

# ===== 管理员账户 =====
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
if not ADMIN_PASSWORD_HASH:
    # 开发环境兜底：使用开发者哈希（仅限本地开发，生产环境必须配置）
    _dev_hash = os.environ.get("DEV_ADMIN_PASSWORD_HASH")
    if _dev_hash:
        ADMIN_PASSWORD_HASH = _dev_hash
    else:
        # 生产环境强制要求配置 ADMIN_PASSWORD_HASH，缺失即终止启动
        _env = os.environ.get("ENV", "development").lower()
        if _env in ("production", "prod"):
            raise RuntimeError(
                "生产环境必须设置 ADMIN_PASSWORD_HASH 环境变量（bcrypt 哈希），"
                "拒绝使用默认弱口令启动。可在开发环境设置 ENV=development 允许兜底。"
            )
        # 仅开发环境允许 admin123 兜底
        import bcrypt
        ADMIN_PASSWORD_HASH = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        logger.warning("⚠️ 使用开发环境默认密码 admin123，生产环境必须设置 ADMIN_PASSWORD_HASH 环境变量！")

# ===== CORS（从环境变量读取，支持逗号分隔多域名）=====
# 优先读取 CORS_ORIGINS，回退到 FRONTEND_ORIGIN（向后兼容）
_raw_origins = os.environ.get(
    "CORS_ORIGINS",
    os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
)
CORS_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
# 生产环境 CORS 安全校验：禁止通配符 origin（与 allow_credentials=True 冲突）
_env_for_cors = os.environ.get("ENV", "development").lower()
if _env_for_cors in ("production", "prod"):
    if "*" in CORS_ORIGINS:
        raise RuntimeError(
            "生产环境禁止 CORS_ORIGINS=*（与 allow_credentials=True 冲突，"
            "会导致跨域凭据泄露）。请显式配置允许的前端域名。"
        )
    if any("localhost" in o or "127.0.0.1" in o for o in CORS_ORIGINS):
        logger.warning("⚠️ 生产环境 CORS_ORIGINS 包含 localhost，仅限调试，上线前请移除。")

# ===== 演示模式开关 =====
# 1=启用硬编码劫持（答辩演示用），0=走真实 LLM/RagFlow（生产用）
DEMO_MODE = os.environ.get("DEMO_MODE", "0") == "1"

# ===== API 版本号 =====
API_VERSION = os.environ.get("API_VERSION", "2.0.0")
API_VERSION_PREFIX = "/api/v1"  # URL 前缀保持 v1 向后兼容，版本号通过响应头传递
