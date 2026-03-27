"""
系统配置API路由。
提供模块开关管理和系统配置查询接口。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_admin_user
from app.models.user import User
from app.models.module_config import ModuleConfig
from app.schemas.config import ModuleConfigUpdate
from app.schemas.common import ResponseBase
from app.core.config import settings

router = APIRouter()


@router.get("/modules", response_model=ResponseBase, summary="获取模块配置列表")
async def list_module_configs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """获取所有模块的启用状态和配置"""
    result = await db.execute(select(ModuleConfig))
    configs = result.scalars().all()

    data = [
        {
            "id": c.id,
            "module_name": c.module_name,
            "enabled": c.enabled,
            "config_json": c.config_json,
            "updated_at": str(c.updated_at) if c.updated_at else None,
        }
        for c in configs
    ]
    return ResponseBase(data=data)


@router.put("/modules/{module_name}", response_model=ResponseBase, summary="更新模块配置")
async def update_module_config(
    module_name: str,
    request: ModuleConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """更新指定模块的配置（管理员）"""
    result = await db.execute(
        select(ModuleConfig).where(ModuleConfig.module_name == module_name)
    )
    config = result.scalar_one_or_none()

    if config:
        config.enabled = request.enabled
        if request.config_json is not None:
            config.config_json = request.config_json
    else:
        config = ModuleConfig(
            module_name=module_name,
            enabled=request.enabled,
            config_json=request.config_json or {},
        )
        db.add(config)

    await db.flush()
    return ResponseBase(message=f"模块 {module_name} 配置已更新")


@router.get("/system", response_model=ResponseBase, summary="获取系统概览")
async def get_system_config(
    _admin: User = Depends(get_admin_user),
):
    """获取系统整体配置概览"""
    return ResponseBase(
        data={
            "app_name": settings.APP_NAME,
            "app_env": settings.APP_ENV,
            "module_ai_enabled": settings.MODULE_AI_ENABLED,
            "module_tradingview_enabled": settings.MODULE_TRADINGVIEW_ENABLED,
            "module_execution_enabled": settings.MODULE_EXECUTION_ENABLED,
            "module_backtest_enabled": settings.MODULE_BACKTEST_ENABLED,
            "binance_testnet": settings.BINANCE_TESTNET,
        }
    )
