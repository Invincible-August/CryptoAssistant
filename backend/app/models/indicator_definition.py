"""
技术指标定义模型。
存储系统中所有可用技术指标的元数据与配置模板。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class IndicatorDefinition(Base):
    """
    技术指标定义表模型。

    每行描述一个技术指标（如 RSI、MACD、布林带等）的元信息，
    包括参数模板、输出结构、前端展示配置以及代码路径。
    支持内置指标与 AI 动态生成的指标两种来源。
    """

    __tablename__ = "indicator_definitions"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 指标标识 ----
    indicator_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="指标唯一标识（如 rsi_14）"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="指标显示名称"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="来源（builtin / ai）"
    )
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="指标版本号"
    )
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="指标类别（trend / momentum / volatility 等）"
    )

    # ---- Schema 定义 ----
    params_schema: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="参数 JSON Schema（定义指标的输入参数）"
    )
    output_schema: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="输出 JSON Schema（定义计算结果的结构）"
    )
    display_config: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="前端图表展示配置（颜色、叠加方式等）"
    )

    # ---- 代码路径 ----
    code_path: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="指标计算代码文件路径"
    )

    # ---- 状态与描述 ----
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="指标是否启用"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="指标详细说明"
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
            f"<IndicatorDefinition(id={self.id}, key='{self.indicator_key}', "
            f"source='{self.source}', enabled={self.enabled})>"
        )
