"""
资金费率模型。
存储永续合约的资金费率历史数据。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketFunding(Base):
    """
    资金费率表模型。

    记录永续合约每个结算周期的资金费率，
    正值表示多头付费给空头，负值则反之。
    是判断市场多空情绪的重要辅助指标。
    """

    __tablename__ = "market_fundings"

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
