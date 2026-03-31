"""
模块配置服务。
管理系统各功能模块（AI、TradingView、自动执行、回测等）的
启用状态和运行时配置。

模块启用判断优先级：
1. 环境变量 / .env 配置（如 MODULE_AI_ENABLED=True）
2. 数据库 module_configs 表中的记录
3. 默认为禁用
"""
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.module_config import ModuleConfig


# 环境变量中的模块开关映射：{模块名称: Settings 属性名}
_ENV_MODULE_MAP: Dict[str, str] = {
    "ai": "MODULE_AI_ENABLED",
    "execution": "MODULE_EXECUTION_ENABLED",
    "backtest": "MODULE_BACKTEST_ENABLED",
}


async def get_module_config(
    db: AsyncSession, module_name: str
) -> Optional[ModuleConfig]:
    """
    获取指定模块的配置信息。

    Args:
        db: 异步数据库会话
        module_name: 模块名称

    Returns:
        ModuleConfig 对象，不存在返回 None
    """
    stmt = select(ModuleConfig).where(
        ModuleConfig.module_name == module_name
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config:
        logger.debug(
            f"模块配置查询成功: {module_name} "
            f"(启用={config.enabled})"
        )
    else:
        logger.debug(f"模块配置不存在: {module_name}")

    return config


async def update_module_config(
    db: AsyncSession,
    module_name: str,
    enabled: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ModuleConfig:
    """
    更新模块配置（不存在则自动创建）。

    采用 upsert 语义：如果模块配置已存在则更新，不存在则新建。

    Args:
        db: 异步数据库会话
        module_name: 模块名称
        enabled: 是否启用（None 表示不修改）
        config: 运行时配置 JSON（None 表示不修改）

    Returns:
        更新后的 ModuleConfig 对象
    """
    stmt = select(ModuleConfig).where(
        ModuleConfig.module_name == module_name
    )
    result = await db.execute(stmt)
    module_config = result.scalar_one_or_none()

    if module_config is None:
        # 不存在则创建新记录
        module_config = ModuleConfig(
            module_name=module_name,
            enabled=enabled if enabled is not None else False,
            config_json=config,
        )
        db.add(module_config)
        logger.info(f"创建新模块配置: {module_name} (启用={module_config.enabled})")
    else:
        # 更新现有记录
        if enabled is not None:
            module_config.enabled = enabled
        if config is not None:
            module_config.config_json = config
        logger.info(
            f"模块配置已更新: {module_name} "
            f"(启用={module_config.enabled})"
        )

    await db.flush()
    return module_config


async def is_module_enabled(
    db: AsyncSession, module_name: str
) -> bool:
    """
    检查模块是否启用。

    判断优先级：
    1. 环境变量中的模块开关配置（最高优先级）
    2. 数据库中的模块配置记录
    3. 默认为禁用

    Args:
        db: 异步数据库会话
        module_name: 模块名称

    Returns:
        模块已启用返回 True，否则返回 False
    """
    # 优先级 1：检查环境变量配置
    env_attr = _ENV_MODULE_MAP.get(module_name)
    if env_attr:
        env_value = getattr(settings, env_attr, None)
        if env_value is not None:
            logger.debug(
                f"模块 {module_name} 状态来自环境变量: "
                f"{env_attr}={env_value}"
            )
            return bool(env_value)

    # 优先级 2：查数据库配置
    module_config = await get_module_config(db, module_name)
    if module_config is not None:
        logger.debug(
            f"模块 {module_name} 状态来自数据库: "
            f"enabled={module_config.enabled}"
        )
        return module_config.enabled

    # 优先级 3：默认禁用
    logger.debug(f"模块 {module_name} 无配置，默认禁用")
    return False


async def list_all_modules(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    列出所有已知模块的状态和配置。

    合并环境变量和数据库中的模块信息，返回统一的模块列表。

    Args:
        db: 异步数据库会话

    Returns:
        模块信息字典列表，每项包含 module_name / enabled / source / config
    """
    modules: List[Dict[str, Any]] = []

    # 从数据库获取所有已配置的模块
    stmt = select(ModuleConfig)
    result = await db.execute(stmt)
    db_configs = {
        config.module_name: config
        for config in result.scalars().all()
    }

    # 合并环境变量中声明的模块
    all_module_names = set(db_configs.keys()) | set(_ENV_MODULE_MAP.keys())

    for module_name in sorted(all_module_names):
        # 判断启用状态（沿用优先级逻辑）
        enabled = await is_module_enabled(db, module_name)

        # 确定配置来源
        db_config = db_configs.get(module_name)
        has_env = module_name in _ENV_MODULE_MAP
        source = "env+db" if (has_env and db_config) else ("env" if has_env else "db")

        modules.append({
            "module_name": module_name,
            "enabled": enabled,
            "source": source,
            "config": db_config.config_json if db_config else None,
            "updated_at": (
                str(db_config.updated_at) if db_config and db_config.updated_at
                else None
            ),
        })

    logger.debug(f"模块列表查询完成: 共 {len(modules)} 个模块")
    return modules
