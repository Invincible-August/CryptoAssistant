"""
实时监控API路由。
管理交易对监控列表和实时连接状态。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.symbol_watch import SymbolWatch
from app.schemas.monitor import SymbolWatchCreate, SymbolWatchUpdate, SymbolWatchResponse
from app.schemas.common import ResponseBase

router = APIRouter()


@router.get("/watches", response_model=ResponseBase, summary="获取监控列表")
async def list_watches(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取所有正在监控的交易对"""
    result = await db.execute(select(SymbolWatch).order_by(SymbolWatch.id.desc()))
    watches = result.scalars().all()

    return ResponseBase(
        data=[SymbolWatchResponse.model_validate(w).model_dump() for w in watches]
    )


@router.post("/watches", response_model=ResponseBase, summary="添加监控")
async def add_watch(
    request: SymbolWatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加新的交易对监控"""
    watch = SymbolWatch(
        exchange=request.exchange,
        symbol=request.symbol,
        market_type=request.market_type,
        event_type=request.event_type or "all",
        watch_status="active",
        config_json=request.config_json or {},
        created_by=current_user.id,
    )
    db.add(watch)
    await db.flush()
    await db.refresh(watch)

    return ResponseBase(
        message="监控已添加",
        data=SymbolWatchResponse.model_validate(watch).model_dump(),
    )


@router.put("/watches/{watch_id}", response_model=ResponseBase, summary="更新监控")
async def update_watch(
    watch_id: int,
    request: SymbolWatchUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """更新监控配置"""
    result = await db.execute(select(SymbolWatch).where(SymbolWatch.id == watch_id))
    watch = result.scalar_one_or_none()
    if not watch:
        raise HTTPException(status_code=404, detail="监控不存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(watch, key, value)

    await db.flush()
    return ResponseBase(message="更新成功")


@router.delete("/watches/{watch_id}", response_model=ResponseBase, summary="删除监控")
async def delete_watch(
    watch_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """删除监控"""
    result = await db.execute(select(SymbolWatch).where(SymbolWatch.id == watch_id))
    watch = result.scalar_one_or_none()
    if not watch:
        raise HTTPException(status_code=404, detail="监控不存在")

    await db.delete(watch)
    return ResponseBase(message="监控已删除")


@router.get("/status", response_model=ResponseBase, summary="获取连接状态")
async def get_status(
    _user: User = Depends(get_current_user),
):
    """获取实时数据连接状态"""
    return ResponseBase(
        data={
            "ws_connected": False,
            "last_update_time": None,
            "message": "WebSocket连接管理将在数据源模块完全集成后可用",
        }
    )
