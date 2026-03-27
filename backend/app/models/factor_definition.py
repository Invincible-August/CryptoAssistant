"""
因子定义模型。
存储系统中所有可用量化因子的元数据与配置模板。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class FactorDefinition(Base):
    """
    因子定义表模型。

    每行描述一个量化因子（如动量因子、波动率因子、资金流因子等）的元信息，
    包括输入输出 Schema 和代码路径。因子用于综合多维度市场信号生成交易决策。
    """

    __tablename__ = "factor_definitions"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 因子标识 ----
    factor_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="因子唯一标识（如 momentum_5m）"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="因子显示名称"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="来源（builtin / ai）"
    )
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="因子版本号"
    )

    # ---- Schema 定义 ----
    input_schema: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="输入 JSON Schema（定义因子所需的数据源）"
    )
    output_schema: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="输出 JSON Schema（定义计算结果的结构）"
    )
    config_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="因子运行时配置（JSON格式）"
    )

    # ---- 代码路径 ----
    code_path: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="因子计算代码文件路径"
    )

    # ---- 状态与描述 ----
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="因子是否启用"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="因子详细说明"
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
            f"<FactorDefinition(id={self.id}, key='{self.factor_key}', "
            f"source='{self.source}', enabled={self.enabled})>"
        )
