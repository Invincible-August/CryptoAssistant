"""
错误日志模型。
存储系统运行期间捕获的异常与错误详情。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ErrorLog(Base):
    """
    错误日志表模型。

    专门记录系统异常与错误信息，包括错误类型、异常消息、
    完整堆栈回溯以及触发错误时的上下文数据。
    与 SystemLog 互补，便于快速定位和排查问题。
    """

    __tablename__ = "error_logs"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 错误来源 ----
    module: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="产生错误的模块名称"
    )
    error_type: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="错误类型（如 ConnectionError / ValueError）"
    )

    # ---- 错误详情 ----
    message: Mapped[str] = mapped_column(
        Text, nullable=False, comment="错误消息内容"
    )
    traceback: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="完整堆栈回溯信息"
    )
    context_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="触发错误时的上下文数据（JSON格式）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="记录入库时间"
    )

    def __repr__(self) -> str:
        return (
            f"<ErrorLog(id={self.id}, module='{self.module}', "
            f"type='{self.error_type}': {self.message[:50]}...)>"
        )
