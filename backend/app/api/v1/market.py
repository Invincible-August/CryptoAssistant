"""
行情数据API路由。
提供K线、成交、深度、资金费率、持仓量等数据查询接口。
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.market_import_task import MarketImportTask
from app.models.market_kline import MarketKline
from app.models.market_trade import MarketTrade
from app.models.market_orderbook_snapshot import MarketOrderbookSnapshot
from app.models.market_funding import MarketFunding
from app.models.market_open_interest import MarketOpenInterest
from app.schemas.common import ResponseBase
from app.services.market_data_provider import market_data_provider
from app.schemas.market_import import (
    MarketImportCreateRequest,
    MarketImportCreateResponse,
    MarketImportTaskResponse,
)
from app.services.market_import_service import schedule_market_import

router = APIRouter()


@router.post("/import", response_model=ResponseBase, summary="创建行情导入任务")
async def create_market_import(
    payload: MarketImportCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Persist a ``MarketImportTask`` and schedule a background import job.

    The worker reads task configuration from the database, marks status
    ``running``, pulls historical data per ``import_types``, and writes via
    ``market_service`` upsert helpers.
    """
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    task = MarketImportTask(
        name=payload.name,
        created_by=user.id,
        exchange=payload.exchange,
        market_type=payload.market_type,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        start_date=payload.start_date,
        end_date=payload.end_date,
        import_types=list(payload.import_types or []),
        status="pending",
        progress=0.0,
    )
    db.add(task)
    await db.flush()
    # Ensure the background worker can read this task via a new DB session.
    # `flush()` alone is not visible across sessions until `commit()`.
    await db.commit()
    schedule_market_import(task.id)
    return ResponseBase(
        data=MarketImportCreateResponse(task_id=task.id).model_dump(),
    )


@router.get(
    "/import/{task_id}",
    response_model=ResponseBase,
    summary="查询行情导入任务",
)
async def get_market_import(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Return a single market import task including status and ``result_json``."""
    result = await db.execute(
        select(MarketImportTask).where(MarketImportTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ResponseBase(
        data=MarketImportTaskResponse.model_validate(task).model_dump(),
    )


@router.get("/klines", response_model=ResponseBase, summary="获取K线数据")
async def get_klines(
    symbol: str = Query(..., description="交易对"),
    interval: str = Query("1h", description="K线周期"),
    exchange: str = Query("binance", description="交易所标识"),
    market_type: str = Query("spot", description="市场类型"),
    limit: int = Query(200, ge=1, le=1000, description="数量限制"),
    source_mode: str = Query(
        "cache",
        description="数据模式：cache=读缓存；live=实时拉取交易所并回写缓存",
    ),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取历史K线数据"""
    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    klines = await market_data_provider.get_klines(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        interval=interval,
        limit=limit,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
    )

    data = [
        {
            "open_time": str(k["open_time"]),
            "open": k["open"],
            "high": k["high"],
            "low": k["low"],
            "close": k["close"],
            "volume": k["volume"],
            "quote_volume": k.get("quote_volume", 0.0),
            "trade_count": k.get("trade_count", 0),
        }
        for k in klines
    ]
    return ResponseBase(data=data)


@router.get("/trades", response_model=ResponseBase, summary="获取逐笔成交")
async def get_trades(
    symbol: str = Query(...),
    exchange: str = Query("binance"),
    market_type: str = Query("spot"),
    limit: int = Query(100, ge=1, le=500),
    source_mode: str = Query("cache"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的逐笔成交数据"""
    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    trades = await market_data_provider.get_trades(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        limit=limit,
        source_mode=source_mode,
    )

    data = [
        {
            "trade_id": t["trade_id"],
            "price": t["price"],
            "quantity": t["quantity"],
            "side": t["side"],
            "event_time": str(t["event_time"]),
        }
        for t in trades
    ]
    return ResponseBase(data=data)


@router.get("/orderbook", response_model=ResponseBase, summary="获取订单簿")
async def get_orderbook(
    symbol: str = Query(...),
    exchange: str = Query("binance"),
    market_type: str = Query("spot"),
    source_mode: str = Query("cache"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最新的订单簿快照"""
    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    ob = await market_data_provider.get_orderbook(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
    )

    if not ob.get("bids") and not ob.get("asks"):
        return ResponseBase(
            data={"bids": [], "asks": [], "message": "暂无数据"}
        )

    return ResponseBase(
        data={
            "snapshot_time": ob.get("snapshot_time"),
            "bids": ob.get("bids", []),
            "asks": ob.get("asks", []),
        }
    )


@router.get("/funding", response_model=ResponseBase, summary="获取资金费率")
async def get_funding(
    symbol: str = Query(...),
    exchange: str = Query("binance"),
    source_mode: str = Query("cache"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的资金费率"""
    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    fr = await market_data_provider.get_funding_rate(
        db,
        exchange=exchange,
        symbol=symbol,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
    )
    return ResponseBase(data=[fr])


@router.get("/oi", response_model=ResponseBase, summary="获取持仓量")
async def get_oi(
    symbol: str = Query(...),
    exchange: str = Query("binance"),
    market_type: str = Query("spot"),
    source_mode: str = Query("cache"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的持仓量数据"""
    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    oi = await market_data_provider.get_open_interest(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
    )
    return ResponseBase(data=[oi])
