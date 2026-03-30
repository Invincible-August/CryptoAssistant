"""
Funding rate ORM model.

Stores perpetual futures funding rate history.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketFunding(Base):
    """
    Funding rate table.

    Each row represents a funding settlement for a symbol at a given funding time.
    """

    __tablename__ = "market_fundings"

    # ---- 表级约束 ----
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "funding_time",
            name="uq_funding_identity",
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

    # ---- 资金费率数据 ----
    funding_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="资金费率"
    )
    funding_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="资金费率结算时间"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<MarketFunding(id={self.id}, {self.exchange}:{self.symbol} "
            f"rate={self.funding_rate} @ {self.funding_time})>"
        )
