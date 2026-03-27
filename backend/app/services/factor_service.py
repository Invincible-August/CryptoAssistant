"""
因子服务模块。
提供量化因子的注册列表、计算执行和结果查询的业务逻辑。

因子与指标的区别：
- 指标 (Indicator)：基于K线数据的技术分析工具（如 RSI、MACD）
- 因子 (Factor)：综合多维数据源的策略分析特征（如动量因子、资金流因子）

因子计算需要更丰富的数据上下文（K线 + 订单簿 + 持仓量 + 成交数据等）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.factors.registry import FactorRegistry
from app.models.factor_result import FactorResult
from app.models.market_kline import MarketKline
from app.models.market_orderbook_snapshot import MarketOrderbookSnapshot
from app.models.market_open_interest import MarketOpenInterest
from app.models.market_trade import MarketTrade


async def list_factors() -> List[Dict[str, Any]]:
    """
    列出所有已注册的量化因子及其元数据。

    从内存中的因子注册中心获取，不涉及数据库查询。

    Returns:
        因子元数据字典列表
    """
    factors = FactorRegistry.list_metadata()
    logger.debug(f"已注册因子总数: {len(factors)}")
    return factors


async def calculate_factor(
    db: AsyncSession,
    factor_key: str,
    exchange: str,
    symbol: str,
    market_type: str,
    timeframe: str,
    params: Optional[Dict[str, Any]] = None,
    kline_limit: int = 500,
) -> Dict[str, Any]:
    """
    计算指定因子并保存结果。

    完整流程：
    1. 从注册中心获取因子类
    2. 校验并补全参数
    3. 构建因子计算所需的多维度数据上下文
    4. 调用因子的 calculate 方法执行计算
    5. 对结果进行归一化处理
    6. 将最终结果持久化到 FactorResult 表

    Args:
        db: 异步数据库会话
        factor_key: 因子唯一标识（如 "momentum", "volume_flow"）
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        timeframe: 计算时间帧
        params: 因子计算参数（可选）
        kline_limit: K线数据加载条数

    Returns:
        包含因子计算结果的字典

    Raises:
        ValueError: 因子未注册或数据不足
    """
    # 从注册中心获取因子类
    factor_cls = FactorRegistry.get(factor_key)
    if factor_cls is None:
        raise ValueError(f"因子未注册: {factor_key}")

    # 校验参数
    validated_params = factor_cls.validate_params(params or {})

    # 构建因子计算所需的数据上下文
    context = await _build_factor_context(
        db, exchange, symbol, market_type, timeframe,
        factor_cls.input_type, kline_limit
    )

    logger.info(
        f"开始计算因子: {factor_key}，"
        f"交易对: {symbol}，时间帧: {timeframe}"
    )

    # 执行因子计算
    raw_result = factor_cls.calculate(context, validated_params)

    # 归一化处理（标准化评分等后处理）
    normalized_result = factor_cls.normalize(raw_result)

    # 持久化计算结果
    factor_result = FactorResult(
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        factor_key=factor_key,
        source=factor_cls.source,
        timeframe=timeframe,
        event_time=datetime.utcnow(),
        result_json=normalized_result,
    )

    db.add(factor_result)
    await db.flush()

    logger.info(f"因子计算完成并保存: {factor_key} ({symbol} {timeframe})")

    return {
        "factor_key": factor_key,
        "symbol": symbol,
        "timeframe": timeframe,
        "result": normalized_result,
    }


async def get_factor_results(
    db: AsyncSession,
    symbol: str,
    factor_key: str,
    exchange: str = "binance",
    market_type: str = "spot",
    timeframe: str = "1h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[FactorResult]:
    """
    查询因子计算结果的历史记录。

    Args:
        db: 异步数据库会话
        symbol: 交易对
        factor_key: 因子唯一标识
        exchange: 交易所标识
        market_type: 市场类型
        timeframe: 时间帧
        start_time: 起始时间过滤（可选）
        end_time: 结束时间过滤（可选）
        limit: 返回最大条数

    Returns:
        FactorResult 对象列表
    """
    query = select(FactorResult).where(
        and_(
            FactorResult.exchange == exchange,
            FactorResult.symbol == symbol,
            FactorResult.market_type == market_type,
            FactorResult.factor_key == factor_key,
            FactorResult.timeframe == timeframe,
        )
    )

    if start_time:
        query = query.where(FactorResult.event_time >= start_time)
    if end_time:
        query = query.where(FactorResult.event_time <= end_time)

    query = query.order_by(desc(FactorResult.event_time)).limit(limit)

    result = await db.execute(query)
    results = list(result.scalars().all())

    logger.debug(
        f"因子结果查询: {factor_key} {symbol} {timeframe}，"
        f"返回 {len(results)} 条"
    )
    return results


async def _build_factor_context(
    db: AsyncSession,
    exchange: str,
    symbol: str,
    market_type: str,
    timeframe: str,
    input_types: List[str],
    kline_limit: int,
) -> Dict[str, Any]:
    """
    根据因子声明的输入依赖类型，构建计算所需的数据上下文。

    上下文是一个字典，键为数据类型标识，值为对应的数据（DataFrame 或字典）。
    例如：{"kline": <DataFrame>, "orderbook": <Dict>, "open_interest": <Dict>}

    Args:
        db: 异步数据库会话
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        timeframe: 时间帧
        input_types: 因子声明的数据源依赖列表
        kline_limit: K线数据条数

    Returns:
        数据上下文字典
    """
    context: Dict[str, Any] = {
        "exchange": exchange,
        "symbol": symbol,
        "market_type": market_type,
        "timeframe": timeframe,
    }

    # 按因子声明的依赖类型加载对应数据
    if "kline" in input_types:
        kline_query = (
            select(MarketKline)
            .where(
                and_(
                    MarketKline.exchange == exchange,
                    MarketKline.symbol == symbol,
                    MarketKline.market_type == market_type,
                    MarketKline.interval == timeframe,
                )
            )
            .order_by(MarketKline.open_time.asc())
            .limit(kline_limit)
        )
        kline_result = await db.execute(kline_query)
        klines = list(kline_result.scalars().all())

        # 转换为 DataFrame 便于因子计算
        context["kline"] = pd.DataFrame([
            {
                "open_time": k.open_time,
                "open": float(k.open),
                "high": float(k.high),
                "low": float(k.low),
                "close": float(k.close),
                "volume": float(k.volume),
                "quote_volume": float(k.quote_volume),
                "trade_count": k.trade_count or 0,
            }
            for k in klines
        ])

    if "orderbook" in input_types:
        ob_query = (
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
        ob_result = await db.execute(ob_query)
        ob = ob_result.scalar_one_or_none()
        context["orderbook"] = {
            "bids": ob.bids_json if ob else [],
            "asks": ob.asks_json if ob else [],
            "snapshot_time": str(ob.snapshot_time) if ob else None,
        }

    if "open_interest" in input_types:
        oi_query = (
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
        oi_result = await db.execute(oi_query)
        oi = oi_result.scalar_one_or_none()
        context["open_interest"] = {
            "open_interest": float(oi.open_interest) if oi else 0.0,
            "event_time": str(oi.event_time) if oi else None,
        }

    if "trades" in input_types:
        trades_query = (
            select(MarketTrade)
            .where(
                and_(
                    MarketTrade.exchange == exchange,
                    MarketTrade.symbol == symbol,
                    MarketTrade.market_type == market_type,
                )
            )
            .order_by(desc(MarketTrade.event_time))
            .limit(200)
        )
        trades_result = await db.execute(trades_query)
        trades = list(trades_result.scalars().all())
        context["trades"] = pd.DataFrame([
            {
                "trade_id": t.trade_id,
                "price": float(t.price),
                "quantity": float(t.quantity),
                "side": t.side,
                "event_time": t.event_time,
            }
            for t in trades
        ])

    return context
