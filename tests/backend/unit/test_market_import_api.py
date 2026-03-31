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

        async def commit(self) -> None:
            return None

    sess = _Sess()
    user = MagicMock()
    user.id = 7

    # 说明：timeframe 在 Task2 中变为可选；服务端应强制覆盖为 1m
    payload = MarketImportCreateRequest.model_validate(
        {
            "exchange": "binance",
            "market_type": "futures",
            "symbol": "BTCUSDT",
            "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "import_types": ["kline"],
        }
    )
    resp = await create_market_import(payload, sess, user)
    assert captured == [42]
    assert resp.data["task_id"] == 42

    # 断言写入 ORM 的 timeframe 被强制设为 1m（不受客户端是否传入影响）
    assert sess.added[0].timeframe == "1m"


@pytest.mark.asyncio
async def test_create_market_import_overrides_client_timeframe_to_1m(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When client provides non-1m timeframe, API must override it to 1m."""
    captured: list[int] = []
    logged: list[dict] = []

    def _fake_schedule(task_id: int) -> None:
        captured.append(task_id)

    monkeypatch.setattr(
        "app.api.v1.market.schedule_market_import",
        _fake_schedule,
    )

    # 说明：捕获 logger.info 的结构化日志参数，验证 client_timeframe_overridden 打点存在
    def _fake_logger_info(message: str, **kwargs):
        logged.append({"message": message, "kwargs": dict(kwargs)})

    monkeypatch.setattr("app.api.v1.market.logger.info", _fake_logger_info)

    class _Sess:
        def __init__(self) -> None:
            self.added: list = []

        def add(self, obj: object) -> None:
            self.added.append(obj)

        async def flush(self) -> None:
            if self.added:
                setattr(self.added[0], "id", 99)

        async def commit(self) -> None:
            return None

    sess = _Sess()
    user = MagicMock()
    user.id = 1

    payload = MarketImportCreateRequest(
        exchange="binance",
        market_type="spot",
        symbol="ETHUSDT",
        timeframe="1h",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        import_types=["kline"],
    )

    resp = await create_market_import(payload, sess, user)
    assert resp.data["task_id"] == 99
    assert sess.added[0].timeframe == "1m"
    assert any(
        x["message"] == "client_timeframe_overridden"
        and x["kwargs"].get("task_id") == 99
        and x["kwargs"].get("symbol") == "ETHUSDT"
        and x["kwargs"].get("client_timeframe") == "1h"
        and x["kwargs"].get("effective_timeframe") == "1m"
        for x in logged
    )
