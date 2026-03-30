"""
Market trade (tick-by-tick) ORM model.

Stores executed trades streamed from exchanges for microstructure analysis.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketTrade(Base):
    """
    Executed trades table.

    Each row represents a single matched trade with price, quantity, and aggressor side.
    """

    __tablename__ = "market_trades"

    # ---- 表级约束 ----
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "market_type",
            "trade_id",
            name="uq_trade_identity",
        ),
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

    # ---- 成交明细 ----
    trade_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易所返回的成交ID"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交价格"
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交数量"
    )
    side: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="成交方向（buy / sell）"
    )

    # ---- 事件时间 ----
    event_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="交易所事件时间"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<MarketTrade(id={self.id}, {self.exchange}:{self.symbol} "
            f"{self.side} {self.quantity}@{self.price})>"
        )
