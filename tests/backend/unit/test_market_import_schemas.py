"""
Market import schema unit tests.

These tests focus on Pydantic validation rules only (no database / service layer).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.market_import import (
    MarketImportCreateRequest,
    MarketImportTaskResponse,
)


class TestMarketImportSchemas:
    """Unit tests for market import Pydantic schemas."""

    def test_create_request_accepts_valid_payload(self) -> None:
        """A minimal valid create payload should pass validation."""
        payload = {
            "exchange": "binance",
            "market_type": "spot",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "import_types": ["kline", "trade"],
        }

        req = MarketImportCreateRequest.model_validate(payload)
        assert req.exchange == "binance"
        assert req.import_types == ["kline", "trade"]

    def test_create_request_rejects_invalid_status_value(self) -> None:
        """Status should be constrained to pending/running/completed/failed."""
        payload = {
            "exchange": "binance",
            "market_type": "spot",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "import_types": ["kline"],
            "status": "unknown_status",
        }

        with pytest.raises(ValidationError):
            MarketImportCreateRequest.model_validate(payload)

    def test_task_response_accepts_arbitrary_result_json_shape(self) -> None:
        """result_json should accept nested JSON-like objects without strict schema."""
        payload = {
            "id": 123,
            "name": "Import BTCUSDT spot 1h",
            "created_by": 1,
            "exchange": "binance",
            "market_type": "spot",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "import_types": ["kline"],
            "status": "completed",
            "progress": 1.0,
            "result_json": {
                "summary": {"rows": 12345, "duration_ms": 4567},
                "per_type": {"kline": {"inserted": 12000, "skipped": 345}},
                "warnings": ["some non-fatal warning"],
            },
            "last_error": None,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "finished_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }

        resp = MarketImportTaskResponse.model_validate(payload)
        assert resp.id == 123
        assert resp.result_json is not None
        assert resp.result_json["summary"]["rows"] == 12345
