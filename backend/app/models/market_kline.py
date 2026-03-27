"""
K线（蜡烛图）数据模型。
存储各交易对不同周期的OHLCV数据，是技术分析的基础数据源。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, String, DateTime, Integer, Numeric,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketKline(Base):
    """
    K线数据表模型。

    存储每根K线的开盘价、最高价、最低价、收盘价、成交量等信息。
    通过 (exchange, symbol, market_type, interval, open_time) 五元组唯一确定一条记录。
    """

    __tablename__ = "market_klines"

    # ---- 表级约束 ----
    __table_args__ = (
        UniqueConstraint(
            "exchange", "symbol", "market_type", "interval", "open_time",
            name="uq_kline_identity",
        ),
        Index("ix_kline_symbol_interval_opentime", "symbol", "interval", "open_time"),
    )

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 交易对标识 ----
    exchange: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易所标识"
    )
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对"
    )
    market_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="市场类型（spot / futures）"
    )
    interval: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="K线周期（1m / 5m / 1h / 1d 等）"
    )

    # ---- 时间范围 ----
    open_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="开盘时间"
    )
    close_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="收盘时间"
    )

    # ---- OHLCV 数据（精度30位，小数点后10位，满足高精度需求） ----
    open: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="开盘价"
    )
    high: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="最高价"
    )
    low: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="最低价"
    )
    close: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="收盘价"
    )
    volume: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交量（基础货币）"
    )
    quote_volume: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交额（计价货币）"
    )

    # ---- 成交笔数 ----
    trade_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="该周期内成交笔数"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<MarketKline(id={self.id}, {self.exchange}:{self.symbol} "
            f"{self.interval} @ {self.open_time})>"
        )
