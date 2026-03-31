"""
Admin-only API routes (plugin hot-reload, operational hooks).
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_admin_user
from app.core.config import settings
from app.core.plugin_hot_reload import reload_plugin_packages
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter()


@router.post(
    "/plugins/reload",
    response_model=ResponseBase,
    summary="热重载指标/因子插件（管理员）",
)
async def hot_reload_plugins(_admin: User = Depends(get_admin_user)):
    """
    Unload plugin modules, clear registry entries for builtins/custom packages,
    and rescan filesystem (same as startup registration).

    Controlled by ``PLUGIN_HOT_RELOAD_ENABLED`` in settings / environment.
    """
    if not settings.PLUGIN_HOT_RELOAD_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Plugin hot reload is disabled (PLUGIN_HOT_RELOAD_ENABLED=false)",
        )
    stats = reload_plugin_packages()
    return ResponseBase(data=stats)
