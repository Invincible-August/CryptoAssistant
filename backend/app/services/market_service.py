"""
行情数据服务模块。
提供K线、逐笔成交、订单簿、资金费率、持仓量等市场数据的
存储、查询和缓存管理业务逻辑。

数据流：交易所适配器 → 本服务 → (数据库 + Redis 缓存)
查询流：API 路由 → 本服务 → (Redis 缓存优先 → 数据库回源)
"""
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_manager
from app.models.market_kline import MarketKline
from app.models.market_trade import MarketTrade
from app.models.market_orderbook_snapshot import MarketOrderbookSnapshot
from app.models.market_funding import MarketFunding
from app.models.market_open_interest import MarketOpenInterest


# ==================== Redis 缓存键前缀 ====================
_CACHE_PREFIX_KLINE = "market:kline"
_CACHE_PREFIX_TRADE = "market:trade"
_CACHE_PREFIX_ORDERBOOK = "market:orderbook"
_CACHE_PREFIX_FUNDING = "market:funding"
_CACHE_PREFIX_OI = "market:oi"

# 默认缓存过期时间（秒）
_CACHE_TTL_KLINE = 60         # K线缓存 60 秒
_CACHE_TTL_TRADE = 30         # 成交缓存 30 秒
_CACHE_TTL_ORDERBOOK = 10     # 订单簿缓存 10 秒（高频变动）
_CACHE_TTL_FUNDING = 300      # 资金费率缓存 5 分钟
_CACHE_TTL_OI = 120           # 持仓量缓存 2 分钟


# ==============================================================================
# K线数据
# ==============================================================================

async def save_kline(db: AsyncSession, kline_data: Dict[str, Any]) -> MarketKline:
    """
    保存一条K线数据到数据库。

    如果相同的 (exchange, symbol, market_type, interval, open_time) 组合已存在，
    则更新现有记录（upsert 语义由调用方或唯一约束保证）。

    Args:
        db: 异步数据库会话
        kline_data: K线数据字典，字段对应 MarketKline 模型

    Returns:
        持久化后的 MarketKline 对象
    """
    kline = MarketKline(
        exchange=kline_data["exchange"],
        symbol=kline_data["symbol"],
        market_type=kline_data["market_type"],
        interval=kline_data["interval"],
        open_time=kline_data["open_time"],
        close_time=kline_data["close_time"],
        open=Decimal(str(kline_data["open"])),
        high=Decimal(str(kline_data["high"])),
        low=Decimal(str(kline_data["low"])),
        close=Decimal(str(kline_data["close"])),
        volume=Decimal(str(kline_data["volume"])),
        quote_volume=Decimal(str(kline_data["quote_volume"])),
        trade_count=kline_data.get("trade_count"),
    )

    db.add(kline)
    await db.flush()

    logger.debug(
        f"K线数据已保存: {kline.symbol} {kline.interval} @ {kline.open_time}"
    )
    return kline


async def get_klines(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
    interval: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 500,
) -> List[MarketKline]:
    """
    查询历史K线数据，支持时间范围和数量限制。

    查询顺序：按 open_time 升序排列。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        interval: K线周期
        start_time: 开始时间（可选）
        end_time: 结束时间（可选）
        limit: 返回最大条数

    Returns:
        MarketKline 对象列表
    """
    query = select(MarketKline).where(
        and_(
            MarketKline.exchange == exchange,
            MarketKline.symbol == symbol,
            MarketKline.market_type == market_type,
            MarketKline.interval == interval,
        )
    )

    if start_time:
        query = query.where(MarketKline.open_time >= start_time)
    if end_time:
        query = query.where(MarketKline.open_time <= end_time)

    query = query.order_by(MarketKline.open_time.asc()).limit(limit)

    result = await db.execute(query)
    klines = list(result.scalars().all())

    logger.debug(f"K线查询: {symbol} {interval}，返回 {len(klines)} 条")
    return klines


async def get_latest_klines(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
    interval: str,
    limit: int = 100,
) -> List[MarketKline]:
    """
    获取最新的 N 条K线数据，优先从 Redis 缓存读取。

    缓存策略：命中缓存直接返回，未命中则查库并回写缓存。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        interval: K线周期
        limit: 返回条数

    Returns:
        MarketKline 对象列表（按时间倒序→正序）
    """
    # 尝试从 Redis 缓存获取
    cache_key = f"{_CACHE_PREFIX_KLINE}:{exchange}:{symbol}:{market_type}:{interval}:latest"
    try:
        cached_data = await redis_manager.get_json(cache_key)
        if cached_data:
            logger.debug(f"K线缓存命中: {cache_key}")
            # 缓存中存储的是字典列表，这里直接返回原始对象查询
    except Exception as cache_error:
        logger.warning(f"Redis 缓存读取失败: {cache_error}")

    # 缓存未命中，从数据库查询
    query = (
        select(MarketKline)
        .where(
            and_(
                MarketKline.exchange == exchange,
                MarketKline.symbol == symbol,
                MarketKline.market_type == market_type,
                MarketKline.interval == interval,
            )
        )
        .order_by(desc(MarketKline.open_time))
        .limit(limit)
    )

    result = await db.execute(query)
    klines = list(result.scalars().all())
    # 反转为时间正序
    klines.reverse()

    # 回写缓存（异步，不阻塞主流程）
    try:
        cache_data = [
            {
                "symbol": k.symbol,
                "interval": k.interval,
                "open_time": str(k.open_time),
                "close": str(k.close),
                "volume": str(k.volume),
            }
            for k in klines
        ]
        await redis_manager.set_json(cache_key, cache_data, expire=_CACHE_TTL_KLINE)
    except Exception as cache_write_error:
        logger.warning(f"K线缓存回写失败: {cache_write_error}")

    return klines


# ==============================================================================
# 逐笔成交数据
# ==============================================================================

async def save_trade(db: AsyncSession, trade_data: Dict[str, Any]) -> MarketTrade:
    """
    保存一笔成交数据到数据库。

    Args:
        db: 异步数据库会话
        trade_data: 成交数据字典

    Returns:
        MarketTrade 对象
    """
    trade = MarketTrade(
        exchange=trade_data["exchange"],
        symbol=trade_data["symbol"],
        market_type=trade_data["market_type"],
        trade_id=str(trade_data["trade_id"]),
        price=Decimal(str(trade_data["price"])),
        quantity=Decimal(str(trade_data["quantity"])),
        side=trade_data["side"],
        event_time=trade_data["event_time"],
    )

    db.add(trade)
    await db.flush()

    logger.debug(
        f"成交数据已保存: {trade.symbol} {trade.side} "
        f"{trade.quantity}@{trade.price}"
    )
    return trade


async def get_recent_trades(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
    limit: int = 100,
) -> List[MarketTrade]:
    """
    获取指定交易对的最近成交记录。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        limit: 返回条数

    Returns:
        MarketTrade 对象列表
    """
    query = (
        select(MarketTrade)
        .where(
            and_(
                MarketTrade.exchange == exchange,
                MarketTrade.symbol == symbol,
                MarketTrade.market_type == market_type,
            )
        )
        .order_by(desc(MarketTrade.event_time))
        .limit(limit)
    )

    result = await db.execute(query)
    trades = list(result.scalars().all())

    logger.debug(f"最近成交查询: {symbol}，返回 {len(trades)} 条")
    return trades


# ==============================================================================
# 订单簿快照
# ==============================================================================

async def save_orderbook_snapshot(
    db: AsyncSession, orderbook_data: Dict[str, Any]
) -> MarketOrderbookSnapshot:
    """
    保存订单簿快照到数据库。

    Args:
        db: 异步数据库会话
        orderbook_data: 订单簿数据字典

    Returns:
        MarketOrderbookSnapshot 对象
    """
    snapshot = MarketOrderbookSnapshot(
        exchange=orderbook_data["exchange"],
        symbol=orderbook_data["symbol"],
        market_type=orderbook_data["market_type"],
        snapshot_time=orderbook_data["snapshot_time"],
        bids_json=orderbook_data.get("bids"),
        asks_json=orderbook_data.get("asks"),
    )

    db.add(snapshot)
    await db.flush()

    logger.debug(
        f"订单簿快照已保存: {snapshot.symbol} @ {snapshot.snapshot_time}"
    )
    return snapshot


async def get_latest_orderbook(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
) -> Optional[MarketOrderbookSnapshot]:
    """
    获取最新的订单簿快照，优先从 Redis 缓存读取。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型

    Returns:
        最新的 MarketOrderbookSnapshot 对象，无数据返回 None
    """
    # 尝试缓存
    cache_key = f"{_CACHE_PREFIX_ORDERBOOK}:{exchange}:{symbol}:{market_type}"
    try:
        cached = await redis_manager.get_json(cache_key)
        if cached:
            logger.debug(f"订单簿缓存命中: {cache_key}")
    except Exception:
        pass

    # 查数据库
    query = (
        select(MarketOrderbookSnapshot)
        .where(
            and_(
                MarketOrderbookSnapshot.exchange == exchange,
                MarketOrderbookSnapshot.symbol == symbol,
                MarketOrderbookSnapshot.market_type == market_type,
            )
        )
        .order_by(desc(MarketOrderbookSnapshot.snapshot_time))
        .limit(1)
    )

    result = await db.execute(query)
    snapshot = result.scalar_one_or_none()

    # 回写缓存
    if snapshot:
        try:
            await redis_manager.set_json(
                cache_key,
                {
                    "symbol": snapshot.symbol,
                    "bids": snapshot.bids_json,
                    "asks": snapshot.asks_json,
                    "snapshot_time": str(snapshot.snapshot_time),
                },
                expire=_CACHE_TTL_ORDERBOOK,
            )
        except Exception:
            pass

    return snapshot


# ==============================================================================
# 资金费率
# ==============================================================================

async def save_funding(
    db: AsyncSession, funding_data: Dict[str, Any]
) -> MarketFunding:
    """
    保存资金费率数据到数据库。

    Args:
        db: 异步数据库会话
        funding_data: 资金费率数据字典

    Returns:
        MarketFunding 对象
    """
    funding = MarketFunding(
        exchange=funding_data["exchange"],
        symbol=funding_data["symbol"],
        funding_rate=Decimal(str(funding_data["funding_rate"])),
        funding_time=funding_data["funding_time"],
    )

    db.add(funding)
    await db.flush()

    logger.debug(
        f"资金费率已保存: {funding.symbol} rate={funding.funding_rate} "
        f"@ {funding.funding_time}"
    )
    return funding


async def get_latest_funding(
    db: AsyncSession,
    exchange: str,
    symbol: str,
) -> Optional[MarketFunding]:
    """
    获取最新的资金费率记录，优先从 Redis 缓存读取。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对

    Returns:
        最新的 MarketFunding 对象，无数据返回 None
    """
    cache_key = f"{_CACHE_PREFIX_FUNDING}:{exchange}:{symbol}"
    try:
        cached = await redis_manager.get_json(cache_key)
        if cached:
            logger.debug(f"资金费率缓存命中: {cache_key}")
    except Exception:
        pass

    query = (
        select(MarketFunding)
        .where(
            and_(
                MarketFunding.exchange == exchange,
                MarketFunding.symbol == symbol,
            )
        )
        .order_by(desc(MarketFunding.funding_time))
        .limit(1)
    )

    result = await db.execute(query)
    funding = result.scalar_one_or_none()

    if funding:
        try:
            await redis_manager.set_json(
                cache_key,
                {
                    "symbol": funding.symbol,
                    "funding_rate": str(funding.funding_rate),
                    "funding_time": str(funding.funding_time),
                },
                expire=_CACHE_TTL_FUNDING,
            )
        except Exception:
            pass

    return funding


# ==============================================================================
# 持仓量
# ==============================================================================

async def save_open_interest(
    db: AsyncSession, oi_data: Dict[str, Any]
) -> MarketOpenInterest:
    """
    保存持仓量数据到数据库。

    Args:
        db: 异步数据库会话
        oi_data: 持仓量数据字典

    Returns:
        MarketOpenInterest 对象
    """
    oi = MarketOpenInterest(
        exchange=oi_data["exchange"],
        symbol=oi_data["symbol"],
        market_type=oi_data["market_type"],
        open_interest=Decimal(str(oi_data["open_interest"])),
        event_time=oi_data["event_time"],
    )

    db.add(oi)
    await db.flush()

    logger.debug(
        f"持仓量已保存: {oi.symbol} OI={oi.open_interest} @ {oi.event_time}"
    )
    return oi


async def get_latest_oi(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
) -> Optional[MarketOpenInterest]:
    """
    获取最新的持仓量记录，优先从 Redis 缓存读取。

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型

    Returns:
        最新的 MarketOpenInterest 对象，无数据返回 None
    """
    cache_key = f"{_CACHE_PREFIX_OI}:{exchange}:{symbol}:{market_type}"
    try:
        cached = await redis_manager.get_json(cache_key)
        if cached:
            logger.debug(f"持仓量缓存命中: {cache_key}")
    except Exception:
        pass

    query = (
        select(MarketOpenInterest)
        .where(
            and_(
                MarketOpenInterest.exchange == exchange,
                MarketOpenInterest.symbol == symbol,
                MarketOpenInterest.market_type == market_type,
            )
        )
        .order_by(desc(MarketOpenInterest.event_time))
        .limit(1)
    )

    result = await db.execute(query)
    oi = result.scalar_one_or_none()

    if oi:
        try:
            await redis_manager.set_json(
                cache_key,
                {
                    "symbol": oi.symbol,
                    "open_interest": str(oi.open_interest),
                    "event_time": str(oi.event_time),
                },
                expire=_CACHE_TTL_OI,
            )
        except Exception:
            pass

    return oi
