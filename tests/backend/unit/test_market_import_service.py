"""
Unit tests for `MarketImportService` algorithms and import orchestration.

No live network or database: pure helpers, mocks for exchange provider and DB session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import market_import_service as mis


def test_iter_trade_time_chunks_one_hour_windows() -> None:
    """
    Futures aggTrades windows must not exceed 1h; 2h30m span yields 3 chunks.
    """
    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    chunks = mis.iter_trade_time_chunks_ms(
        start_ms=int(start.timestamp() * 1000),
        end_exclusive_ms=int(end.timestamp() * 1000) + 1,
        chunk_ms=mis.TRADE_CHUNK_MS_MS,
    )
    assert len(chunks) == 3
    assert chunks[0][0] == int(start.timestamp() * 1000)
    assert chunks[0][1] == int(start.timestamp() * 1000) + mis.TRADE_CHUNK_MS_MS
    assert chunks[1][1] == chunks[0][1] + mis.TRADE_CHUNK_MS_MS
    assert chunks[2][1] == int(end.timestamp() * 1000) + 1


def test_crop_open_interest_range_marks_partial_outside_30d() -> None:
    """
    Effective OI range must fall within [now-30d, now]; partial when user range is wider.
    """
    now = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)
    req_start = now - timedelta(days=60)
    req_end = now - timedelta(days=1)
    eff_start, eff_end, partial = mis.crop_open_interest_range(
        request_start=req_start,
        request_end=req_end,
        now=now,
    )
    assert partial is True
    assert eff_start == now - timedelta(days=30)
    assert eff_end == req_end


def test_crop_open_interest_range_not_partial_when_inside_window() -> None:
    """When fully inside the 30d window, partial is False."""
    now = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)
    req_start = now - timedelta(days=5)
    req_end = now - timedelta(days=1)
    eff_start, eff_end, partial = mis.crop_open_interest_range(
        request_start=req_start,
        request_end=req_end,
        now=now,
    )
    assert partial is False
    assert eff_start == req_start
    assert eff_end == req_end


def test_normalize_import_types_aliases() -> None:
    # Canonical MVP order: kline before trades (see ``_PROCESS_ORDER``).
    assert mis.normalize_import_types(["trade", "kline"]) == ["kline", "trades"]


def test_apply_progress_monotonic() -> None:
    """Progress must never decrease when applying updates."""
    task = MagicMock()
    task.progress = 0.4
    mis.apply_progress_monotonic(task, 0.2)
    assert task.progress == 0.4
    mis.apply_progress_monotonic(task, 0.9)
    assert task.progress == 0.9
    mis.apply_progress_monotonic(task, 0.85)
    assert task.progress == 0.9


def test_build_empty_result_json_has_required_keys() -> None:
    out = mis.build_result_json(
        summary={"import_types_requested": ["orderbook"], "rows_total": 0},
        type_results={"orderbook": {"status": "unsupported_historical"}},
        errors=[],
    )
    assert "summary" in out and "type_results" in out and "errors" in out
    assert out["type_results"]["orderbook"]["status"] == "unsupported_historical"


@pytest.mark.asyncio
async def test_run_import_orderbook_only_marks_unsupported_historical() -> None:
    """Orderbook must not trigger network or save_*; only unsupported_historical result."""
    task = _make_task(
        import_types=["orderbook"],
        market_type="futures",
    )
    session = _FakeSession(task)
    provider = AsyncMock()
    svc = mis.MarketImportService(exchange=provider)

    await svc.run_import_with_session(session, task.id)

    provider.fetch_klines_window.assert_not_called()
    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.result_json is not None
    assert (
        task.result_json["type_results"]["orderbook"]["status"]
        == "unsupported_historical"
    )


@pytest.mark.asyncio
async def test_run_import_trades_chunks_call_provider_per_window() -> None:
    """Trades import must call provider once per <=1h chunk."""
    # 2.5h span -> 3 windows (same geometry as test_iter_trade_time_chunks_one_hour_windows).
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 2, 30, 0, tzinfo=timezone.utc)
    task = _make_task(
        import_types=["trades"],
        market_type="futures",
        start_date=start,
        end_date=end,
    )
    session = _FakeSession(task)
    provider = AsyncMock()
    provider.fetch_agg_trades_window = AsyncMock(return_value=[])

    saves: List[str] = []

    async def fake_save_trade(db: Any, row: Dict[str, Any]) -> None:
        saves.append("trade")

    svc = mis.MarketImportService(exchange=provider, save_trade_fn=fake_save_trade)
    await svc.run_import_with_session(session, task.id)

    assert provider.fetch_agg_trades_window.await_count == 3
    assert task.status == "completed"
    assert task.progress == 1.0


def _make_task(
    *,
    import_types: List[str],
    market_type: str = "spot",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    from app.models.market_import_task import MarketImportTask

    start_date = start_date or datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = end_date or datetime(2026, 1, 2, tzinfo=timezone.utc)
    t = MarketImportTask(
        id=1,
        name="t",
        created_by=1,
        exchange="binance",
        market_type=market_type,
        symbol="BTCUSDT",
        timeframe="1h",
        start_date=start_date,
        end_date=end_date,
        import_types=import_types,
        status="running",
        progress=0.0,
    )
    return t


class _FakeSession:
    """Minimal async session stub: one MarketImportTask row, id=1."""

    def __init__(self, task: Any) -> None:
        self._task = task
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def execute(self, stmt: Any) -> Any:
        return _FakeResult(self._task)

    def add(self, obj: Any) -> None:
        pass


class _FakeResult:
    def __init__(self, task: Any) -> None:
        self._task = task

    def scalar_one_or_none(self) -> Any:
        return self._task

    def scalars(self) -> Any:
        return self

    def all(self) -> List[Any]:
        return [self._task]


@pytest.mark.asyncio
async def test_run_import_result_json_summary_and_errors_on_spot_funding() -> None:
    """Funding on spot should record an error entry and skip fetch."""
    task = _make_task(import_types=["funding_rate"], market_type="spot")
    session = _FakeSession(task)
    provider = AsyncMock()

    svc = mis.MarketImportService(exchange=provider)
    await svc.run_import_with_session(session, task.id)

    provider.fetch_funding_rate_history.assert_not_called()
    assert task.result_json is not None
    assert task.result_json["errors"]
    assert "funding_rate" in task.result_json["errors"][0].get("type", "")


@pytest.mark.asyncio
async def test_progress_sequence_non_decreasing() -> None:
    """During import, recorded progress values must be monotonic non-decreasing."""
    task = _make_task(
        import_types=["trades"],
        market_type="futures",
    )
    session = _FakeSession(task)
    progress_log: List[float] = []

    orig = mis.apply_progress_monotonic

    def wrap(t: Any, v: float) -> None:
        orig(t, v)
        progress_log.append(float(t.progress))

    provider = AsyncMock()
    provider.fetch_agg_trades_window = AsyncMock(return_value=[])

    monkey = pytest.MonkeyPatch()
    monkey.setattr(mis, "apply_progress_monotonic", wrap)
    try:
        svc = mis.MarketImportService(exchange=provider)
        await svc.run_import_with_session(session, task.id)
    finally:
        monkey.undo()

    for i in range(1, len(progress_log)):
        assert progress_log[i] >= progress_log[i - 1] - 1e-9
