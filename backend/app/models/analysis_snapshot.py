"""
综合分析快照模型。
存储某一时刻对特定交易对的多维度分析结果汇总。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AnalysisSnapshot(Base):
    """
    综合分析快照表模型。

    记录系统在某个时间点对特定交易对进行的完整分析快照，
    包括分析阶段、预估成本区间、多维评分、市场假设、
    论据证据、风险提示及文字摘要。
    """

    __tablename__ = "analysis_snapshots"

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

    # ---- 快照时间与阶段 ----
    event_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="分析对应的市场时间"
    )
    stage: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="分析阶段标识（如 preliminary / final）"
    )

    # ---- 分析内容（JSON格式） ----
    estimated_cost_zone: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="预估成本区间"
    )
    scores_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="多维度评分（趋势/动量/波动率等）"
    )
    hypotheses_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="市场假设列表"
    )
    evidence_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="支撑论据与证据"
    )
    risks_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="风险因素"
    )

    # ---- 文字摘要 ----
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="分析结论文字摘要"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisSnapshot(id={self.id}, {self.exchange}:{self.symbol} "
            f"stage='{self.stage}' @ {self.event_time})>"
        )
