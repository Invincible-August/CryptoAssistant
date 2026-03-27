"""
AI分析记录模型。
存储每次调用AI大模型进行市场分析时的请求与响应。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AIAnalysisRecord(Base):
    """
    AI分析记录表模型。

    完整记录每次AI大模型调用的输入输出，包括原始请求载荷、
    文本响应、结构化 JSON 响应、所用模型名称以及调用状态。
    便于调试、审计和模型效果回溯。
    """

    __tablename__ = "ai_analysis_records"

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

    # ---- 请求与响应 ----
    request_payload: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="发送给AI模型的请求载荷（JSON）"
    )
    response_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="AI模型返回的原始文本"
    )
    response_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="AI模型返回的结构化数据（JSON）"
    )

    # ---- 模型信息 ----
    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="使用的AI模型名称（如 gpt-4 / claude-3）"
    )

    # ---- 调用状态 ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="调用状态（success / failed / timeout）"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息（仅在失败时有值）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<AIAnalysisRecord(id={self.id}, {self.exchange}:{self.symbol} "
            f"model='{self.model_name}', status='{self.status}')>"
        )
