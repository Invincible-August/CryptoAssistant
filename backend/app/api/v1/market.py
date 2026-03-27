"""
行情数据API路由。
提供K线、成交、深度、资金费率、持仓量等数据查询接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.market_kline import MarketKline
from app.models.market_trade import MarketTrade
from app.models.market_orderbook_snapshot import MarketOrderbookSnapshot
from app.models.market_funding import MarketFunding
from app.models.market_open_interest import MarketOpenInterest
from app.schemas.common import ResponseBase

router = APIRouter()


@router.get("/klines", response_model=ResponseBase, summary="获取K线数据")
async def get_klines(
    symbol: str = Query(..., description="交易对"),
    interval: str = Query("1h", description="K线周期"),
    market_type: str = Query("spot", description="市场类型"),
    limit: int = Query(200, ge=1, le=1000, description="数量限制"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取历史K线数据"""
    result = await db.execute(
        select(MarketKline)
        .where(
            MarketKline.symbol == symbol,
            MarketKline.interval == interval,
            MarketKline.market_type == market_type,
        )
        .order_by(desc(MarketKline.open_time))
        .limit(limit)
    )
    klines = result.scalars().all()
    klines.reverse()

    data = [
        {
            "open_time": str(k.open_time),
            "open": float(k.open) if k.open else 0,
            "high": float(k.high) if k.high else 0,
            "low": float(k.low) if k.low else 0,
            "close": float(k.close) if k.close else 0,
            "volume": float(k.volume) if k.volume else 0,
            "quote_volume": float(k.quote_volume) if k.quote_volume else 0,
            "trade_count": k.trade_count or 0,
        }
        for k in klines
    ]
    return ResponseBase(data=data)


@router.get("/trades", response_model=ResponseBase, summary="获取逐笔成交")
async def get_trades(
    symbol: str = Query(...),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的逐笔成交数据"""
    result = await db.execute(
        select(MarketTrade)
        .where(MarketTrade.symbol == symbol)
        .order_by(desc(MarketTrade.event_time))
        .limit(limit)
    )
    trades = result.scalars().all()

    data = [
        {
            "trade_id": t.trade_id,
            "price": float(t.price) if t.price else 0,
            "quantity": float(t.quantity) if t.quantity else 0,
            "side": t.side,
            "event_time": str(t.event_time),
        }
        for t in trades
    ]
    return ResponseBase(data=data)


@router.get("/orderbook", response_model=ResponseBase, summary="获取订单簿")
async def get_orderbook(
    symbol: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最新的订单簿快照"""
    result = await db.execute(
        select(MarketOrderbookSnapshot)
        .where(MarketOrderbookSnapshot.symbol == symbol)
        .order_by(desc(MarketOrderbookSnapshot.snapshot_time))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        return ResponseBase(data={"bids": [], "asks": [], "message": "暂无数据"})

    return ResponseBase(
        data={
            "snapshot_time": str(snapshot.snapshot_time),
            "bids": snapshot.bids_json or [],
            "asks": snapshot.asks_json or [],
        }
    )


@router.get("/funding", response_model=ResponseBase, summary="获取资金费率")
async def get_funding(
    symbol: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的资金费率"""
    result = await db.execute(
        select(MarketFunding)
        .where(MarketFunding.symbol == symbol)
        .order_by(desc(MarketFunding.funding_time))
        .limit(limit)
    )
    fundings = result.scalars().all()

    data = [
        {
            "funding_rate": float(f.funding_rate) if f.funding_rate else 0,
            "funding_time": str(f.funding_time),
        }
        for f in fundings
    ]
    return ResponseBase(data=data)


@router.get("/oi", response_model=ResponseBase, summary="获取持仓量")
async def get_oi(
    symbol: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最近的持仓量数据"""
    result = await db.execute(
        select(MarketOpenInterest)
        .where(MarketOpenInterest.symbol == symbol)
        .order_by(desc(MarketOpenInterest.event_time))
        .limit(limit)
    )
    ois = result.scalars().all()

    data = [
        {
            "open_interest": float(o.open_interest) if o.open_interest else 0,
            "event_time": str(o.event_time),
        }
        for o in ois
    ]
    return ResponseBase(data=data)
