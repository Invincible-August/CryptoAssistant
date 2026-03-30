"""
Market import task model.

This table tracks long-running market data import jobs, including their
configuration (exchange/symbol/timeframe/date range), current status/progress,
and final result/error payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketImportTask(Base):
    """
    Market import task ORM model.

    Each row represents one import job that may run asynchronously (e.g. via
    background worker). We persist enough metadata for:
    - auditing (created_by, timestamps)
    - UI tracking (status/progress)
    - debugging (last_error)
    - post-run analytics (result_json)
    """

    __tablename__ = "market_import_tasks"

    # ---- Primary key ----
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Primary key ID",
    )

    # ---- Human-friendly description ----
    name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Optional task name for display/search",
    )

    # ---- Actor / audit ----
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Optional creator user ID",
    )

    # ---- Import configuration ----
    exchange: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Exchange identifier, e.g. binance",
    )
    market_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Market type, e.g. spot / futures",
    )
    symbol: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Trading symbol, e.g. BTCUSDT",
    )
    timeframe: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Timeframe for kline import, e.g. 1m / 1h",
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Import start timestamp (inclusive)",
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Import end timestamp (inclusive)",
    )

    # Stored as JSON to keep the import pipeline flexible:
    # e.g. ["kline","trade"] or ["kline","orderbook_snapshot"].
    import_types: Mapped[Any] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [],
        comment="Import types list (JSON)",
    )

    # ---- Runtime state ----
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="Task status (pending / running / completed / failed)",
    )
    progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Progress in [0,1]",
    )

    # ---- Output / error ----
    result_json: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Result payload (arbitrary JSON)",
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
        comment="Last error message (if failed)",
    )

    # ---- Timestamps ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Created at",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Updated at",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Finished at (completed/failed)",
    )

    def __repr__(self) -> str:
        return (
            f"<MarketImportTask(id={self.id}, exchange='{self.exchange}', "
            f"symbol='{self.symbol}', status='{self.status}')>"
        )
