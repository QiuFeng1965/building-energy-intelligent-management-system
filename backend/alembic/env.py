# -*- coding: utf-8 -*-
"""
Alembic 迁移环境
- 自动从 app.core.config 读取数据库路径（SQLite/PostgreSQL 双模式）
- 支持 autogenerate（需要 SQLAlchemy 模型）
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 把 backend 目录加入 sys.path，让 app.* 可导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# this is the Alembic Config object
config = context.config

# 从项目配置中心读取数据库 URL，覆盖 alembic.ini 的硬编码
from app.core.config import DB_PATH, DATABASE_URL, DB_TYPE

if DB_TYPE == "postgres" and DATABASE_URL:
    # SQLAlchemy 格式（DATABASE_URL 已为可被 SQLAlchemy 直接解析的连接串）
    sa_url = DATABASE_URL
else:
    sa_url = f"sqlite:///{DB_PATH}"

config.set_main_option("sqlalchemy.url", sa_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# 本项目使用原生 SQL 建表（见 alembic/versions/*.py），未定义 SQLAlchemy ORM 模型，
# 故 target_metadata 保持 None，alembic autogenerate 不可用，迁移需手写。
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 支持 ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 支持 ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
