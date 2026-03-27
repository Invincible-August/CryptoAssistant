"""
回测任务模型。
存储每次回测的配置参数、状态与最终结果。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class BacktestTask(Base):
    """
    回测任务表模型。

    每行代表一次回测运行，记录策略配置、回测时间范围、
    运行状态以及最终的绩效统计结果。
    """

    __tablename__ = "backtest_tasks"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 任务描述 ----
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="回测任务名称"
    )

    # ---- 交易对标识 ----
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易对"
    )
    exchange: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易所标识"
    )
    market_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="市场类型（spot / futures）"
    )
    timeframe: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="回测时间帧（如 1h / 4h / 1d）"
    )

    # ---- 策略与范围 ----
    strategy_config: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="策略参数配置（JSON格式）"
    )
    date_range: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="回测时间范围（如 {\"start\": ..., \"end\": ...}）"
    )

    # ---- 运行状态 ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="任务状态（pending / running / completed / failed）"
    )
    result_json: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True, comment="回测结果统计（收益率、最大回撤、夏普率等，JSON格式）"
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
            f"<BacktestTask(id={self.id}, name='{self.name}', "
            f"status='{self.status}')>"
        )
