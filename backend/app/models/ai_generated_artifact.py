"""
AI生成产物模型。
存储AI动态生成的指标或因子定义草案及其审核状态。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AIGeneratedArtifact(Base):
    """
    AI生成产物表模型。

    当AI分析后自动提议新的指标或因子时，先以"草案"形式存储于此表，
    经人工或自动审核通过后，再同步到对应的 indicator_definitions / factor_definitions 表。
    """

    __tablename__ = "ai_generated_artifacts"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 产物标识 ----
    artifact_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="产物类型（indicator / factor）"
    )
    artifact_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="产物唯一标识（如 ai_rsi_adaptive）"
    )
    source: Mapped[str] = mapped_column(
        String(16), default="ai", comment="来源（默认 ai）"
    )

    # ---- 提议内容 ----
    proposal_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="AI提议的完整定义内容（JSON）"
    )

    # ---- 审核状态 ----
    review_status: Mapped[str] = mapped_column(
        String(32), default="pending",
        comment="审核状态（pending / approved / rejected）"
    )
    linked_definition_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="审核通过后关联的指标/因子定义ID"
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
            f"<AIGeneratedArtifact(id={self.id}, type='{self.artifact_type}', "
            f"key='{self.artifact_key}', status='{self.review_status}')>"
        )
