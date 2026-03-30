"""
Minimal API-level checks for market import routes (no HTTP server, no real DB).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.v1.market import create_market_import
from app.schemas.market_import import MarketImportCreateRequest


@pytest.mark.asyncio
async def test_create_market_import_persists_task_and_schedules_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST handler must flush the task row and invoke ``schedule_market_import``."""
    captured: list[int] = []

    def _fake_schedule(task_id: int) -> None:
        captured.append(task_id)

    monkeypatch.setattr(
        "app.api.v1.market.schedule_market_import",
        _fake_schedule,
    )

    class _Sess:
        def __init__(self) -> None:
            self.added: list = []

        def add(self, obj: object) -> None:
            self.added.append(obj)

        async def flush(self) -> None:
            if self.added:
                setattr(self.added[0], "id", 42)

    sess = _Sess()
    user = MagicMock()
    user.id = 7

    payload = MarketImportCreateRequest(
        exchange="binance",
        market_type="futures",
        symbol="BTCUSDT",
        timeframe="1h",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
        import_types=["kline"],
    )
    resp = await create_market_import(payload, sess, user)
    assert captured == [42]
    assert resp.data["task_id"] == 42
