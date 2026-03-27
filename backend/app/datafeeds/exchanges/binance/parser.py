"""
Binance 原始数据解析器模块。
负责将 Binance REST/WebSocket 返回的原始 JSON 数据
转换为系统统一的数据结构（UnifiedKline / UnifiedTrade 等）。

所有转换逻辑集中在此模块，便于维护和测试。
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple

from loguru import logger

from app.datafeeds.schemas import (
    UnifiedFunding,
    UnifiedKline,
    UnifiedOI,
    UnifiedOrderbook,
    UnifiedTrade,
)


def _to_decimal(value: Any) -> Decimal:
    """
    安全地将任意值转换为 Decimal。
    对于无法转换的值返回 Decimal("0")，并记录警告日志。

    Args:
        value: 待转换的原始值（通常为字符串或数字）

    Returns:
        转换后的 Decimal 值
    """
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"Decimal 转换失败，原始值: {value}，使用默认值 0")
        return Decimal("0")


def _ms_to_datetime(timestamp_ms: int) -> datetime:
    """
    将毫秒级 Unix 时间戳转换为 UTC datetime 对象。

    Args:
        timestamp_ms: 毫秒级时间戳（如 Binance 返回的 1680000000000）

    Returns:
        UTC 时区的 datetime 对象
    """
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)


# ==============================================================================
# REST 数据解析
# ==============================================================================

def parse_rest_kline(
    raw: List, exchange: str, symbol: str, market_type: str, interval: str
) -> UnifiedKline:
    """
    解析 Binance REST API 返回的单根 K 线原始数组。

    Binance REST K线返回格式为数组：
    [开盘时间, 开盘价, 最高价, 最低价, 收盘价, 成交量, 收盘时间,
     成交额, 成交笔数, 主动买入量, 主动买入额, 忽略]

    Args:
        raw: 单根K线的原始数组（12个元素）
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        interval: K线周期

    Returns:
        UnifiedKline 统一K线数据对象
    """
    return UnifiedKline(
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        open_time=_ms_to_datetime(raw[0]),
        close_time=_ms_to_datetime(raw[6]),
        open=_to_decimal(raw[1]),
        high=_to_decimal(raw[2]),
        low=_to_decimal(raw[3]),
        close=_to_decimal(raw[4]),
        volume=_to_decimal(raw[5]),
        quote_volume=_to_decimal(raw[7]),
        trade_count=int(raw[8]) if raw[8] is not None else 0,
        # REST 返回的K线都是已收盘的历史数据
        is_closed=True,
    )


def parse_rest_klines(
    raw_list: List[List],
    exchange: str,
    symbol: str,
    market_type: str,
    interval: str,
) -> List[UnifiedKline]:
    """
    批量解析 REST 返回的K线数组列表。

    Args:
        raw_list: K线原始数组的列表
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        interval: K线周期

    Returns:
        UnifiedKline 对象列表
    """
    return [
        parse_rest_kline(raw, exchange, symbol, market_type, interval)
        for raw in raw_list
    ]


def parse_rest_ticker(raw: Dict) -> Dict[str, Any]:
    """
    解析 Binance 24小时行情统计接口的原始返回。

    Args:
        raw: 24hr ticker 原始字典

    Returns:
        标准化后的行情字典
    """
    return {
        "symbol": raw.get("symbol", ""),
        "last_price": _to_decimal(raw.get("lastPrice", "0")),
        "price_change": _to_decimal(raw.get("priceChange", "0")),
        "price_change_percent": _to_decimal(raw.get("priceChangePercent", "0")),
        "high_price": _to_decimal(raw.get("highPrice", "0")),
        "low_price": _to_decimal(raw.get("lowPrice", "0")),
        "volume": _to_decimal(raw.get("volume", "0")),
        "quote_volume": _to_decimal(raw.get("quoteVolume", "0")),
        "open_time": _ms_to_datetime(raw.get("openTime", 0)),
        "close_time": _ms_to_datetime(raw.get("closeTime", 0)),
        "trade_count": int(raw.get("count", 0)),
    }


def parse_rest_orderbook(
    raw: Dict, exchange: str, symbol: str, market_type: str
) -> UnifiedOrderbook:
    """
    解析 Binance 订单簿深度接口的原始返回。

    Args:
        raw: 订单簿原始字典，包含 bids 和 asks 数组
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型

    Returns:
        UnifiedOrderbook 统一订单簿对象
    """
    bids: List[Tuple[Decimal, Decimal]] = [
        (_to_decimal(bid[0]), _to_decimal(bid[1]))
        for bid in raw.get("bids", [])
    ]
    asks: List[Tuple[Decimal, Decimal]] = [
        (_to_decimal(ask[0]), _to_decimal(ask[1]))
        for ask in raw.get("asks", [])
    ]

    return UnifiedOrderbook(
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        snapshot_time=datetime.now(timezone.utc),
        bids=bids,
        asks=asks,
    )


def parse_rest_funding(raw: Dict, exchange: str) -> UnifiedFunding:
    """
    解析 Binance 资金费率接口的原始返回。

    Args:
        raw: 资金费率原始字典
        exchange: 交易所标识

    Returns:
        UnifiedFunding 统一资金费率对象
    """
    return UnifiedFunding(
        exchange=exchange,
        symbol=raw.get("symbol", ""),
        funding_rate=_to_decimal(raw.get("lastFundingRate", "0")),
        funding_time=_ms_to_datetime(raw.get("fundingTime", 0)),
        next_funding_time=_ms_to_datetime(raw.get("nextFundingTime", 0))
        if raw.get("nextFundingTime")
        else None,
    )


def parse_rest_open_interest(
    raw: Dict, exchange: str, symbol: str
) -> UnifiedOI:
    """
    解析 Binance 持仓量接口的原始返回。

    Args:
        raw: 持仓量原始字典
        exchange: 交易所标识
        symbol: 交易对

    Returns:
        UnifiedOI 统一持仓量对象
    """
    return UnifiedOI(
        exchange=exchange,
        symbol=raw.get("symbol", symbol),
        market_type="perp",
        open_interest=_to_decimal(raw.get("openInterest", "0")),
        event_time=_ms_to_datetime(raw.get("time", 0))
        if raw.get("time")
        else datetime.now(timezone.utc),
    )


# ==============================================================================
# WebSocket 数据解析
# ==============================================================================

def parse_ws_kline(raw: Dict, exchange: str, market_type: str) -> UnifiedKline:
    """
    解析 Binance WebSocket K线推送消息。

    WebSocket K线消息结构：
    {"e": "kline", "s": "BTCUSDT", "k": {
        "t": 开盘时间ms, "T": 收盘时间ms,
        "o": 开盘价, "h": 最高, "l": 最低, "c": 收盘,
        "v": 成交量, "q": 成交额, "n": 成交笔数,
        "i": 周期, "x": 是否收盘
    }}

    Args:
        raw: WebSocket 推送的完整消息字典
        exchange: 交易所标识
        market_type: 市场类型

    Returns:
        UnifiedKline 统一K线对象
    """
    kline_data = raw.get("k", {})

    return UnifiedKline(
        exchange=exchange,
        symbol=raw.get("s", ""),
        market_type=market_type,
        interval=kline_data.get("i", ""),
        open_time=_ms_to_datetime(kline_data.get("t", 0)),
        close_time=_ms_to_datetime(kline_data.get("T", 0)),
        open=_to_decimal(kline_data.get("o", "0")),
        high=_to_decimal(kline_data.get("h", "0")),
        low=_to_decimal(kline_data.get("l", "0")),
        close=_to_decimal(kline_data.get("c", "0")),
        volume=_to_decimal(kline_data.get("v", "0")),
        quote_volume=_to_decimal(kline_data.get("q", "0")),
        trade_count=int(kline_data.get("n", 0)),
        # "x" 字段表示该K线是否已收盘
        is_closed=kline_data.get("x", False),
    )


def parse_ws_trade(raw: Dict, exchange: str, market_type: str) -> UnifiedTrade:
    """
    解析 Binance WebSocket 逐笔成交推送消息。

    Binance 现货使用 "trade" 事件，合约使用 "aggTrade" 事件，
    此函数兼容两种格式。

    Args:
        raw: WebSocket 推送的完整消息字典
        exchange: 交易所标识
        market_type: 市场类型

    Returns:
        UnifiedTrade 统一成交对象
    """
    # 现货 trade 的 ID 字段是 "t"，聚合成交是 "a"
    trade_id = str(raw.get("t", raw.get("a", "")))

    # 判断主动成交方向：
    # 现货 "m"=True 表示 maker 是买方 → 该笔成交的 taker 是卖方
    # 合约 "m"=True 含义相同
    is_buyer_maker = raw.get("m", False)
    side = "sell" if is_buyer_maker else "buy"

    return UnifiedTrade(
        exchange=exchange,
        symbol=raw.get("s", ""),
        market_type=market_type,
        trade_id=trade_id,
        price=_to_decimal(raw.get("p", "0")),
        quantity=_to_decimal(raw.get("q", "0")),
        side=side,
        event_time=_ms_to_datetime(raw.get("E", raw.get("T", 0))),
    )


def parse_ws_depth(
    raw: Dict, exchange: str, market_type: str
) -> UnifiedOrderbook:
    """
    解析 Binance WebSocket 深度推送消息。

    支持 depthUpdate（增量）和 depth@level（快照）两种格式。

    Args:
        raw: WebSocket 推送的完整消息字典
        exchange: 交易所标识
        market_type: 市场类型

    Returns:
        UnifiedOrderbook 统一订单簿对象
    """
    # depthUpdate 事件用 "b"/"a"，快照用 "bids"/"asks"
    raw_bids = raw.get("b", raw.get("bids", []))
    raw_asks = raw.get("a", raw.get("asks", []))

    bids: List[Tuple[Decimal, Decimal]] = [
        (_to_decimal(b[0]), _to_decimal(b[1])) for b in raw_bids
    ]
    asks: List[Tuple[Decimal, Decimal]] = [
        (_to_decimal(a[0]), _to_decimal(a[1])) for a in raw_asks
    ]

    event_time_ms = raw.get("E", 0)
    snapshot_time = (
        _ms_to_datetime(event_time_ms)
        if event_time_ms
        else datetime.now(timezone.utc)
    )

    return UnifiedOrderbook(
        exchange=exchange,
        symbol=raw.get("s", ""),
        market_type=market_type,
        snapshot_time=snapshot_time,
        bids=bids,
        asks=asks,
    )


def parse_ws_mark_price(raw: Dict, exchange: str) -> UnifiedFunding:
    """
    解析 Binance 合约 WebSocket markPrice 推送消息。

    markPrice 推送中包含实时资金费率信息，适合追踪资金费率变化。

    Args:
        raw: WebSocket markPrice 推送消息
        exchange: 交易所标识

    Returns:
        UnifiedFunding 统一资金费率对象
    """
    return UnifiedFunding(
        exchange=exchange,
        symbol=raw.get("s", ""),
        funding_rate=_to_decimal(raw.get("r", "0")),
        funding_time=_ms_to_datetime(raw.get("T", 0))
        if raw.get("T")
        else datetime.now(timezone.utc),
        next_funding_time=_ms_to_datetime(raw.get("T", 0))
        if raw.get("T")
        else None,
    )
