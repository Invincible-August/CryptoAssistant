"""
行情数据相关模型

定义 K 线、逐笔成交、订单簿、资金费率、持仓量、行情概览等结构，
用于实时行情推送和历史数据查询的序列化与校验。
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class KlineData(BaseModel):
    """
    K 线（蜡烛图）数据模型

    单根 K 线包含 OHLCV 及其交易统计信息。

    Attributes:
        exchange: 交易所名称（如 binance）
        symbol: 交易对（如 BTCUSDT）
        market_type: 市场类型（spot / futures）
        interval: K 线周期（如 1m, 5m, 1h, 1d）
        open_time: 开盘时间
        close_time: 收盘时间
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量（基础资产）
        quote_volume: 成交额（报价资产）
        trade_count: 成交笔数
    """

    model_config = ConfigDict(from_attributes=True)

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型：spot / futures")
    interval: str = Field(..., description="K线周期，如 1m, 5m, 1h, 1d")
    open_time: datetime = Field(..., description="开盘时间")
    close_time: datetime = Field(..., description="收盘时间")
    open: Decimal = Field(..., description="开盘价")
    high: Decimal = Field(..., description="最高价")
    low: Decimal = Field(..., description="最低价")
    close: Decimal = Field(..., description="收盘价")
    volume: Decimal = Field(..., description="成交量（基础资产）")
    quote_volume: Decimal = Field(..., description="成交额（报价资产）")
    trade_count: int = Field(default=0, description="成交笔数")


class TradeData(BaseModel):
    """
    逐笔成交数据模型

    单条成交记录，包含价格、数量和方向等信息。

    Attributes:
        exchange: 交易所名称
        symbol: 交易对
        market_type: 市场类型
        trade_id: 交易所分配的成交 ID
        price: 成交价格
        quantity: 成交数量
        side: 成交方向（buy / sell）
        event_time: 成交发生时间
    """

    model_config = ConfigDict(from_attributes=True)

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型")
    trade_id: str = Field(..., description="成交ID")
    price: Decimal = Field(..., description="成交价格")
    quantity: Decimal = Field(..., description="成交数量")
    side: str = Field(..., description="方向：buy / sell")
    event_time: datetime = Field(..., description="成交时间")


class OrderbookData(BaseModel):
    """
    订单簿快照数据模型

    某一时刻的买卖盘口深度数据。
    bids / asks 每一项为 [价格, 数量] 的二元组列表。

    Attributes:
        exchange: 交易所名称
        symbol: 交易对
        market_type: 市场类型
        snapshot_time: 快照时间
        bids: 买盘列表，按价格从高到低排列
        asks: 卖盘列表，按价格从低到高排列
    """

    model_config = ConfigDict(from_attributes=True)

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型")
    snapshot_time: datetime = Field(..., description="快照时间")
    # 每条记录为 [价格, 数量]
    bids: List[List[Decimal]] = Field(
        default_factory=list,
        description="买盘深度，[[price, qty], ...]",
    )
    asks: List[List[Decimal]] = Field(
        default_factory=list,
        description="卖盘深度，[[price, qty], ...]",
    )


class FundingData(BaseModel):
    """
    资金费率数据模型

    永续合约的资金费率快照，用于多空成本分析。

    Attributes:
        exchange: 交易所名称
        symbol: 交易对
        funding_rate: 当期资金费率
        funding_time: 资金费率结算时间
    """

    model_config = ConfigDict(from_attributes=True)

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    funding_rate: Decimal = Field(..., description="资金费率")
    funding_time: datetime = Field(..., description="结算时间")


class OpenInterestData(BaseModel):
    """
    持仓量数据模型

    合约市场未平仓合约总量，反映市场参与度。

    Attributes:
        exchange: 交易所名称
        symbol: 交易对
        market_type: 市场类型
        open_interest: 未平仓合约数量
        event_time: 数据时间
    """

    model_config = ConfigDict(from_attributes=True)

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型")
    open_interest: Decimal = Field(..., description="未平仓量")
    event_time: datetime = Field(..., description="数据时间")


class MarketOverview(BaseModel):
    """
    行情概览模型

    单个交易对的 24 小时行情摘要，用于首页/列表展示。

    Attributes:
        symbol: 交易对
        last_price: 最新成交价
        change_24h: 24 小时涨跌幅（百分比）
        volume_24h: 24 小时成交量
        high_24h: 24 小时最高价
        low_24h: 24 小时最低价
    """

    symbol: str = Field(..., description="交易对")
    last_price: Decimal = Field(..., description="最新价")
    change_24h: Decimal = Field(..., description="24h 涨跌幅（%）")
    volume_24h: Decimal = Field(..., description="24h 成交量")
    high_24h: Decimal = Field(..., description="24h 最高价")
    low_24h: Decimal = Field(..., description="24h 最低价")
