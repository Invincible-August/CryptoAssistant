"""
信号推荐模型。
存储基于综合分析产生的交易信号与具体操作建议。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON, Text, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class SignalRecommendation(Base):
    """
    信号推荐表模型。

    每行代表一条可执行的交易信号建议，关联到对应的 AnalysisSnapshot，
    包含方向、置信度、胜率、入场区间、止损位、多级止盈以及风险说明。
    """

    __tablename__ = "signal_recommendations"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 关联分析快照 ----
    analysis_snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("analysis_snapshots.id"), nullable=False,
        comment="关联的分析快照ID"
    )

    # ---- 交易对标识 ----
    exchange: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易所标识"
    )
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对"
    )

    # ---- 信号核心参数 ----
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="方向（long / short / neutral）"
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="置信度（0~1）"
    )
    win_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=10), nullable=False, comment="预估胜率（0~1）"
    )

    # ---- 入场与出场 ----
    entry_zone: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="入场区间（如 {\"low\": 1800, \"high\": 1820}）"
    )
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=10), nullable=True, comment="止损价位"
    )
    take_profits: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="多级止盈列表（JSON数组）"
    )
    tp_strategy: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="止盈策略配置"
    )

    # ---- 风险与理由 ----
    risks_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="风险因素列表"
    )
    reasons_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="推荐理由列表"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="信号摘要说明"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<SignalRecommendation(id={self.id}, {self.exchange}:{self.symbol} "
            f"dir='{self.direction}', conf={self.confidence})>"
        )
