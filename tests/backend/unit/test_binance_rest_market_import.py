"""
Unit tests for Binance REST historical endpoints used by market import.

All tests monkeypatch ``BinanceRestClient._request`` — no real network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.datafeeds.exchanges.binance.rest_client import (
    BinanceRestClient,
    _FUTURES_BASE_URL,
    _SPOT_BASE_URL,
)


@pytest.fixture
def rest_client() -> BinanceRestClient:
    """REST client forced to mainnet base URLs for stable assertions."""
    client = BinanceRestClient(use_testnet=False)
    return client


@pytest.mark.asyncio
async def test_get_spot_agg_trades_forwards_request_params(
    monkeypatch: pytest.MonkeyPatch, rest_client: BinanceRestClient
) -> None:
    """Spot aggTrades uses GET /api/v3/aggTrades with startTime/endTime/limit."""

    captured: dict = {}

    async def fake_request(self, method, base_url, path, params=None, use_proxy=False):
        captured["method"] = method
        captured["base_url"] = base_url
        captured["path"] = path
        captured["params"] = dict(params) if params else {}
        captured["use_proxy"] = use_proxy
        return []

    monkeypatch.setattr(BinanceRestClient, "_request", fake_request)

    await rest_client.get_spot_agg_trades(
        "BTCUSDT",
        start_time=1_000,
        end_time=2_000,
        limit=100,
        use_proxy=True,
    )

    assert captured["method"] == "GET"
    assert captured["base_url"] == _SPOT_BASE_URL
    assert captured["path"] == "/api/v3/aggTrades"
    assert captured["params"] == {
        "symbol": "BTCUSDT",
        "startTime": 1_000,
        "endTime": 2_000,
        "limit": 100,
    }
    assert captured["use_proxy"] is True


@pytest.mark.asyncio
async def test_get_futures_agg_trades_forwards_request_params(
    monkeypatch: pytest.MonkeyPatch, rest_client: BinanceRestClient
) -> None:
    """Futures aggTrades uses GET /fapi/v1/aggTrades."""

    captured: dict = {}

    async def fake_request(self, method, base_url, path, params=None, use_proxy=False):
        captured["method"] = method
        captured["base_url"] = base_url
        captured["path"] = path
        captured["params"] = dict(params) if params else {}
        captured["use_proxy"] = use_proxy
        return []

    monkeypatch.setattr(BinanceRestClient, "_request", fake_request)

    await rest_client.get_futures_agg_trades(
        "ETHUSDT",
        start_time=3,
        end_time=4,
        limit=999,
        use_proxy=False,
    )

    assert captured["base_url"] == _FUTURES_BASE_URL
    assert captured["path"] == "/fapi/v1/aggTrades"
    assert captured["params"] == {
        "symbol": "ETHUSDT",
        "startTime": 3,
        "endTime": 4,
        "limit": 999,
    }
    assert captured["use_proxy"] is False


@pytest.mark.asyncio
async def test_get_funding_rate_history_forwards_request_params(
    monkeypatch: pytest.MonkeyPatch, rest_client: BinanceRestClient
) -> None:
    """Funding rate history uses GET /fapi/v1/fundingRate."""

    captured: dict = {}

    async def fake_request(self, method, base_url, path, params=None, use_proxy=False):
        captured["method"] = method
        captured["base_url"] = base_url
        captured["path"] = path
        captured["params"] = dict(params) if params else {}
        captured["use_proxy"] = use_proxy
        return []

    monkeypatch.setattr(BinanceRestClient, "_request", fake_request)

    await rest_client.get_funding_rate_history(
        "BTCUSDT",
        start_time=10,
        end_time=20,
        limit=200,
        use_proxy=True,
    )

    assert captured["path"] == "/fapi/v1/fundingRate"
    assert captured["params"] == {
        "symbol": "BTCUSDT",
        "startTime": 10,
        "endTime": 20,
        "limit": 200,
    }
    assert captured["use_proxy"] is True


@pytest.mark.asyncio
async def test_get_open_interest_history_forwards_request_params(
    monkeypatch: pytest.MonkeyPatch, rest_client: BinanceRestClient
) -> None:
    """Open interest history uses GET /futures/data/openInterestHist on futures host."""

    captured: dict = {}

    async def fake_request(self, method, base_url, path, params=None, use_proxy=False):
        captured["method"] = method
        captured["base_url"] = base_url
        captured["path"] = path
        captured["params"] = dict(params) if params else {}
        captured["use_proxy"] = use_proxy
        return []

    monkeypatch.setattr(BinanceRestClient, "_request", fake_request)

    await rest_client.get_open_interest_history(
        "BTCUSDT",
        period="1h",
        start_time=100,
        end_time=200,
        limit=50,
        use_proxy=False,
    )

    assert captured["base_url"] == _FUTURES_BASE_URL
    assert captured["path"] == "/futures/data/openInterestHist"
    assert captured["params"] == {
        "symbol": "BTCUSDT",
        "period": "1h",
        "startTime": 100,
        "endTime": 200,
        "limit": 50,
    }
    assert captured["use_proxy"] is False


@pytest.mark.asyncio
async def test_request_passes_proxy_when_use_proxy_and_env_set(
    monkeypatch: pytest.MonkeyPatch, rest_client: BinanceRestClient
) -> None:
    """When use_proxy is True and HTTPS_PROXY is set, httpx receives proxy."""

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"ok": True}

    mock_request = AsyncMock(return_value=FakeResponse())

    await rest_client.init()
    assert rest_client._client is not None
    monkeypatch.setattr(rest_client._client, "request", mock_request)

    await rest_client._request(
        "GET",
        _SPOT_BASE_URL,
        "/api/v3/ping",
        params=None,
        use_proxy=True,
    )

    mock_request.assert_awaited_once()
    _args, kwargs = mock_request.call_args
    assert kwargs.get("proxy") == "http://127.0.0.1:8888"
