"""
用户模型模块。
定义系统用户表，存储用户认证信息与角色权限。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """
    用户表模型。

    存储系统中所有注册用户的基本信息，包括账号、密码哈希、
    邮箱、角色以及账户激活状态。
    """

    __tablename__ = "users"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 认证字段 ----
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="用户名，全局唯一"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="用户邮箱地址"
    )

    # ---- 权限与状态 ----
    role: Mapped[str] = mapped_column(
        String(32), default="user", comment="用户角色（user / admin）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="账户是否激活"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True, comment="最后更新时间"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
