"""
因子计算结果模型。
存储各量化因子在不同时间点的计算输出。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class FactorResult(Base):
    """
    因子计算结果表模型。

    每行记录某个量化因子在特定交易对、特定时间帧下的一次计算输出，
    计算结果以 JSON 格式存储，结构由对应 FactorDefinition.output_schema 定义。
    """

    __tablename__ = "factor_results"

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

    # ---- 因子信息 ----
    factor_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="关联的因子唯一标识"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="因子来源（builtin / ai）"
    )
    timeframe: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="计算所用的时间帧（如 1m / 5m / 1h）"
    )

    # ---- 计算结果 ----
    event_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="因子计算对应的事件时间"
    )
    result_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="因子计算输出结果（JSON格式）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<FactorResult(id={self.id}, {self.exchange}:{self.symbol} "
            f"key='{self.factor_key}' @ {self.event_time})>"
        )
