"""
Non-DB tests for MarketImportTask ORM registration on SQLAlchemy metadata.

Mirrors `backend/migrations/env.py` wiring (`Base` + `import app.models`) so
Alembic autogenerate sees the same table set without opening a DB connection.
"""

from __future__ import annotations

from app.core.database import Base
import app.models  # noqa: F401  # side-effect: registers all ORM tables on Base.metadata
from app.models.market_import_task import MarketImportTask


class TestMarketImportMetadata:
    """Assertions against DeclarativeBase metadata (no engine / no session)."""

    def test_market_import_tasks_registered_on_base_metadata(self) -> None:
        """Importing app.models must register the market import task table."""
        assert "market_import_tasks" in Base.metadata.tables

    def test_market_import_task_tablename(self) -> None:
        """ORM model must map to the expected physical table name."""
        assert MarketImportTask.__tablename__ == "market_import_tasks"
