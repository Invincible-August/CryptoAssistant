"""
回测成交记录模型。
存储回测过程中模拟产生的每一笔交易明细。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BacktestTrade(Base):
    """
    回测成交记录表模型。

    每行代表回测中模拟执行的一笔交易，记录入场/出场时间、
    价格、数量以及盈亏情况。关联到具体的 BacktestTask。
    """

    __tablename__ = "backtest_trades"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 关联回测任务 ----
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("backtest_tasks.id"), nullable=False,
        comment="关联的回测任务ID"
    )

    # ---- 交易对 ----
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对"
    )

    # ---- 交易方向 ----
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="方向（long / short）"
    )

    # ---- 入场信息 ----
    entry_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="入场时间"
    )
    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="入场价格"
    )

    # ---- 出场信息（持仓中时为空） ----
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="出场时间"
    )
    exit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=10), nullable=True, comment="出场价格"
    )

    # ---- 数量 ----
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="交易数量"
    )

    # ---- 盈亏统计 ----
    pnl: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=10), nullable=True, comment="绝对盈亏金额"
    )
    pnl_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=10), nullable=True, comment="盈亏比率"
    )

    # ---- 备注 ----
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="开仓/平仓原因说明"
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestTrade(id={self.id}, task={self.task_id}, "
            f"{self.direction} {self.symbol}, pnl={self.pnl})>"
        )
