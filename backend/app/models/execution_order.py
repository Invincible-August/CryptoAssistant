"""
实盘/模拟订单模型。
存储系统发出的每一笔交易委托单及其状态。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ExecutionOrder(Base):
    """
    执行订单表模型。

    记录系统向交易所提交的每一笔委托单，包括方向、类型、
    价格、数量、当前状态以及交易所返回的订单ID。
    支持模拟订单（纸交易）与实盘订单两种模式。
    """

    __tablename__ = "execution_orders"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 交易对标识 ----
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对"
    )
    exchange: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易所标识"
    )
    market_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="市场类型（spot / futures）"
    )

    # ---- 订单参数 ----
    side: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="买卖方向（buy / sell）"
    )
    order_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="订单类型（limit / market / stop_market 等）"
    )
    price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=10), nullable=True, comment="委托价格（市价单为空）"
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="委托数量"
    )

    # ---- 订单状态 ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="订单状态（pending / submitted / filled / partially_filled / cancelled / failed）"
    )

    # ---- 订单ID ----
    client_order_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="客户端自定义订单ID"
    )
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="交易所返回的订单ID"
    )

    # ---- 模式标识 ----
    is_simulated: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否为模拟订单（True=纸交易）"
    )

    # ---- 策略配置 ----
    strategy_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="触发该订单的策略配置快照（JSON）"
    )

    # ---- 关联用户 ----
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="创建者用户ID"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True, comment="最后更新时间"
    )

    def __repr__(self) -> str:
        return (
            f"<ExecutionOrder(id={self.id}, {self.exchange}:{self.symbol} "
            f"{self.side} {self.order_type}, status='{self.status}', "
            f"simulated={self.is_simulated})>"
        )
