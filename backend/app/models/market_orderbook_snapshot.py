"""
订单簿快照模型。
定期存储盘口买卖挂单的深度快照数据。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketOrderbookSnapshot(Base):
    """
    订单簿快照表模型。

    按照固定时间间隔保存某个交易对的买盘（bids）和卖盘（asks）深度数据，
    以 JSON 格式存储价格档位列表，用于流动性分析和微观结构研究。
    """

    __tablename__ = "market_orderbook_snapshots"

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

    # ---- 快照时间 ----
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="快照采集时间"
    )

    # ---- 盘口数据（JSON 格式：[[price, qty], ...] ）----
    bids_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="买盘挂单列表（JSON）"
    )
    asks_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="卖盘挂单列表（JSON）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<MarketOrderbookSnapshot(id={self.id}, {self.exchange}:{self.symbol} "
            f"@ {self.snapshot_time})>"
        )
