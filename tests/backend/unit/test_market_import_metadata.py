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

    def test_market_import_task_python_side_defaults(self) -> None:
        """
        ORM model should have Python-side defaults aligned with DB defaults.

        This ensures callers can instantiate the ORM object without explicitly
        setting status/progress/import_types when creating a new task.
        """
        table = MarketImportTask.__table__

        # Column defaults are applied at INSERT time; we can still assert they are configured.
        assert table.c.status.default is not None
        assert table.c.status.default.arg == "pending"

        assert table.c.progress.default is not None
        assert float(table.c.progress.default.arg) == 0.0

        assert table.c.import_types.default is not None
        assert callable(table.c.import_types.default.arg)
        # SQLAlchemy passes an execution context to callable defaults.
        assert table.c.import_types.default.arg(None) == []

    def test_market_import_task_datetime_columns_timezone_aware(self) -> None:
        """Datetime columns should be configured as timezone-aware at ORM level."""
        table = MarketImportTask.__table__
        assert getattr(table.c.start_date.type, "timezone", False) is True
        assert getattr(table.c.end_date.type, "timezone", False) is True
        assert getattr(table.c.created_at.type, "timezone", False) is True
        assert getattr(table.c.updated_at.type, "timezone", False) is True
        assert getattr(table.c.finished_at.type, "timezone", False) is True
