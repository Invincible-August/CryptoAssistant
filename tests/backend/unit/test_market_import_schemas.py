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
            # 说明：timeframe 在 Task2 中改为可选；服务端会强制覆盖为 1m
            "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "import_types": ["kline", "funding_rate"],
        }

        req = MarketImportCreateRequest.model_validate(payload)
        assert req.exchange == "binance"
        assert req.timeframe is None
        assert req.import_types == ["kline", "funding_rate"]

    def test_create_request_excludes_server_controlled_fields(self) -> None:
        """created_by and status are server-controlled; create schema must not expose them."""
        field_names = set(MarketImportCreateRequest.model_fields.keys())
        assert "created_by" not in field_names
        assert "status" not in field_names

    def test_create_request_rejects_naive_datetimes(self) -> None:
        """Naive datetimes must be rejected to avoid timezone ambiguity."""
        payload = {
            "exchange": "binance",
            "market_type": "spot",
            "symbol": "BTCUSDT",
            "start_date": datetime(2024, 1, 1),  # naive
            "end_date": datetime(2024, 1, 2),  # naive
            "import_types": ["kline"],
        }

        with pytest.raises(ValidationError) as exc_info:
            MarketImportCreateRequest.model_validate(payload)

        # Explicit error message makes API misuse easier to debug.
        assert "timezone-aware" in str(exc_info.value)

    def test_create_request_rejects_unknown_import_types_with_allowlist(self) -> None:
        """
        import_types 必须在服务端 allowlist 内。

        说明：该校验应发生在后端（schema 或 API 均可）；这里在 schema 层验证，
        以确保 FastAPI 在请求进入 handler 前就能返回 422。
        """
        payload = {
            "exchange": "binance",
            "market_type": "spot",
            "symbol": "BTCUSDT",
            "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end_date": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "import_types": ["trades"],
        }

        with pytest.raises(ValidationError) as exc_info:
            MarketImportCreateRequest.model_validate(payload)

        # 错误信息必须包含 allowlist，便于客户端修复请求参数
        error_text = str(exc_info.value)
        assert "kline" in error_text
        assert "open_interest" in error_text
        assert "funding_rate" in error_text

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
