"""
Alembic 迁移环境配置文件。

负责加载数据库连接、导入所有模型，并配置在线/离线迁移模式。
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 将 backend 目录添加到 Python 路径，以便正确导入应用模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 从 .env 文件加载环境变量（优先使用项目根目录的 .env）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Alembic 配置对象，可用于访问 alembic.ini 中的值
config = context.config

# 从环境变量中读取数据库连接地址，覆盖 alembic.ini 中的默认值
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# 配置日志（基于 alembic.ini 中的 [loggers] 部分）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ===== 导入所有模型，确保 Alembic 能检测到 schema 变更 =====
# SQLAlchemy 的 DeclarativeBase 只有在模型类被 import 时才会把表注册进 metadata。
# 使用 `import app.models` 触发 `app/models/__init__.py` 中的全量导入，避免漏表导致
# `alembic revision --autogenerate` 误报“删除未导入的表”。
# noqa: F401 — 副作用 import，静态检查器可能报未使用，此处必须保留。
from app.core.database import Base
import app.models  # noqa: F401  # side-effect: registers all ORM tables on Base.metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    离线模式：仅生成 SQL 脚本，不实际连接数据库。
    适用于需要审核 SQL 或在无法直连数据库的环境中执行迁移。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Execute migrations with the given connection.

    在已建立的数据库连接上执行迁移操作。
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    在线模式（异步）：创建异步数据库引擎并执行迁移。
    这是本项目的默认迁移方式，因为我们使用 asyncpg 作为数据库驱动。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    在线模式入口：启动异步事件循环并执行迁移。
    """
    asyncio.run(run_async_migrations())


# 根据当前模式选择执行方式
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
