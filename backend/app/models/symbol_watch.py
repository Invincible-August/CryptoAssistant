"""
交易对监控列表模型。
定义系统需要实时监控的交易对及其采集配置。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class SymbolWatch(Base):
    """
    交易对监控表模型。

    每行代表一个被系统关注的交易对，记录交易所、币对、
    市场类型（现货/合约）、事件类型（K线/成交/深度等）、
    监控状态以及采集参数。
    """

    __tablename__ = "symbol_watches"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 交易对标识 ----
    exchange: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易所标识（如 binance）"
    )
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对（如 ETHUSDT）"
    )
    market_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="市场类型（spot / futures）"
    )

    # ---- 采集事件配置 ----
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件类型（kline / trade / depth 等）"
    )
    watch_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="监控状态（active / paused / stopped）"
    )
    config_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="采集参数配置（如K线周期列表，JSON格式）"
    )

    # ---- 关联用户 ----
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True, comment="创建者用户ID"
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
            f"<SymbolWatch(id={self.id}, {self.exchange}:{self.symbol}, "
            f"type='{self.event_type}', status='{self.watch_status}')>"
        )
