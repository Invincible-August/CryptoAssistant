"""
统一行情数据结构模块。
定义所有交易所适配器输出的标准化数据格式。
不同交易所的原始数据经过 parser 转换后统一为这些结构，
保证上层业务逻辑与交易所细节解耦。
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple


@dataclass
class UnifiedKline:
    """
    统一K线（蜡烛图）数据结构。

    所有交易所的K线数据最终都转换为此格式，
    供指标计算、因子分析、数据库存储等模块消费。

    Attributes:
        exchange: 交易所标识（如 "binance"）
        symbol: 交易对（如 "BTCUSDT"）
        market_type: 市场类型（"spot" 或 "perp"）
        interval: K线周期（如 "1m", "5m", "1h"）
        open_time: 该根K线的开盘时间
        close_time: 该根K线的收盘时间
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量（以基础货币计）
        quote_volume: 成交额（以计价货币计）
        trade_count: 该周期内成交笔数
        is_closed: 该根K线是否已经收盘（WebSocket推送时有未收盘K线）
    """

    exchange: str
    symbol: str
    market_type: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int = 0
    is_closed: bool = False


@dataclass
class UnifiedTrade:
    """
    统一逐笔成交数据结构。

    记录单笔实际撮合成交的详细信息。

    Attributes:
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        trade_id: 交易所分配的成交唯一ID
        price: 成交价格
        quantity: 成交数量
        side: 主动成交方向（"buy" 表示主动买入即吃卖单，"sell" 反之）
        event_time: 成交发生的时间戳
    """

    exchange: str
    symbol: str
    market_type: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    side: str
    event_time: datetime


@dataclass
class UnifiedOrderbook:
    """
    统一订单簿快照数据结构。

    Attributes:
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        snapshot_time: 快照采集时间
        bids: 买盘深度列表，每项为 (价格, 数量) 元组，按价格从高到低排列
        asks: 卖盘深度列表，每项为 (价格, 数量) 元组，按价格从低到高排列
    """

    exchange: str
    symbol: str
    market_type: str
    snapshot_time: datetime
    bids: List[Tuple[Decimal, Decimal]] = field(default_factory=list)
    asks: List[Tuple[Decimal, Decimal]] = field(default_factory=list)


@dataclass
class UnifiedFunding:
    """
    统一资金费率数据结构。

    永续合约特有的资金费率信息。

    Attributes:
        exchange: 交易所标识
        symbol: 交易对
        funding_rate: 本期资金费率（正值 = 多头付给空头）
        funding_time: 资金费率结算时间
        next_funding_time: 下一次结算时间（如果可用）
    """

    exchange: str
    symbol: str
    funding_rate: Decimal
    funding_time: datetime
    next_funding_time: datetime | None = None


@dataclass
class UnifiedOI:
    """
    统一持仓量（Open Interest）数据结构。

    反映合约市场的全网未平仓合约总量。

    Attributes:
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        open_interest: 全网未平仓合约总量
        event_time: 数据采集时间
    """

    exchange: str
    symbol: str
    market_type: str
    open_interest: Decimal
    event_time: datetime
