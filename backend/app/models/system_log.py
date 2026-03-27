"""
系统日志模型。
存储系统运行期间的结构化日志条目。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class SystemLog(Base):
    """
    系统日志表模型。

    记录系统各模块在运行过程中产生的重要事件日志，
    包括日志级别、来源模块、消息内容以及可选的详细数据。
    """

    __tablename__ = "system_logs"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 日志内容 ----
    level: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="日志级别（DEBUG / INFO / WARNING / ERROR / CRITICAL）"
    )
    module: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="产生日志的模块名称"
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False, comment="日志消息内容"
    )
    detail_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="补充详情（JSON格式，可选）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<SystemLog(id={self.id}, [{self.level}] {self.module}: "
            f"{self.message[:50]}...)>"
        )
