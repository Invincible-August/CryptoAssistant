"""
订单成交明细模型。
存储每笔委托单的逐笔成交记录。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ExecutionFill(Base):
    """
    订单成交明细表模型。

    一笔委托单可能被分多次撮合成交（部分成交），
    每次成交产生一条 Fill 记录，包含成交价格、数量和手续费。
    """

    __tablename__ = "execution_fills"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 关联委托单 ----
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("execution_orders.id"), nullable=False,
        comment="关联的委托单ID"
    )

    # ---- 成交明细 ----
    fill_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交价格"
    )
    fill_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="成交数量"
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="手续费"
    )

    # ---- 成交时间 ----
    fill_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="交易所成交时间"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<ExecutionFill(id={self.id}, order={self.order_id}, "
            f"{self.fill_quantity}@{self.fill_price}, fee={self.fee})>"
        )
