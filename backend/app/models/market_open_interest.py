"""
Open interest ORM model.

Stores open interest snapshots for futures markets.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketOpenInterest(Base):
    """
    Open interest table.

    Each row represents an open interest measurement at a specific event time.
    """

    __tablename__ = "market_open_interests"

    # ---- 表级约束 ----
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "market_type",
            "event_time",
            name="uq_open_interest_identity",
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
        String(32), nullable=False, comment="市场类型（futures）"
    )

    # ---- 持仓量数据 ----
    open_interest: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="全网持仓量"
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="数据采集时间"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<MarketOpenInterest(id={self.id}, {self.exchange}:{self.symbol} "
            f"OI={self.open_interest} @ {self.event_time})>"
        )
