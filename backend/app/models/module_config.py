"""
模块配置模型。
定义系统各功能模块的开关与JSON配置。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ModuleConfig(Base):
    """
    模块配置表模型。

    每行代表系统中一个可配置模块（如数据采集、指标计算、AI 分析等），
    记录其启用状态与运行时参数。
    """

    __tablename__ = "module_configs"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 模块标识 ----
    module_name: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="模块名称，全局唯一"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="模块是否启用"
    )

    # ---- 配置内容 ----
    config_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="模块运行时配置（JSON格式）"
    )

    # ---- 时间戳 ----
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), server_default=func.now(), comment="最后更新时间"
    )

    def __repr__(self) -> str:
        return f"<ModuleConfig(id={self.id}, module='{self.module_name}', enabled={self.enabled})>"
