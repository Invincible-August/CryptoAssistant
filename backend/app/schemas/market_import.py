"""
Market import schemas.

This module defines request/response payloads for initiating and tracking
market data import tasks (e.g., importing klines/trades/orderbook snapshots).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# NOTE:
# - We keep status values aligned with the ORM model and API expectations.
# - Using Literal makes client-side validation and OpenAPI docs clearer.
MarketImportStatus = Literal["pending", "running", "completed", "failed"]

_ALLOWED_IMPORT_TYPES: set[str] = {"kline", "open_interest", "funding_rate"}

def _require_tz_aware(value: datetime, *, field_name: str) -> datetime:
    """
    Require timezone-aware datetimes.

    We intentionally reject naive datetimes to avoid ambiguous interpretations
    (local time vs UTC). API clients should always send ISO8601 with offset,
    e.g. `2024-01-01T00:00:00Z` or `2024-01-01T08:00:00+08:00`.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware (include offset or Z)")
    return value


class MarketImportCreateRequest(BaseModel):
    """
    Market import task creation request.

    Server-controlled fields (e.g. ``created_by`` from auth, initial ``status``
    defaulting to ``pending``) are not part of this schema; the API layer sets
    them when persisting the task.

    Attributes:
        name: Optional human-friendly task name for display/search.
        exchange: Exchange identifier, e.g. "binance".
        market_type: Market type, e.g. "spot" or "futures".
        symbol: Trading symbol, e.g. "BTCUSDT".
        timeframe: Kline timeframe when importing klines, e.g. "1m", "1h".
        start_date: Import start timestamp (inclusive).
        end_date: Import end timestamp (inclusive).
        import_types: Which datasets to import (stored as JSON in DB).
    """

    name: Optional[str] = Field(default=None, max_length=128, description="任务名称（可选）")

    exchange: str = Field(..., max_length=32, description="交易所标识，例如 binance")
    market_type: str = Field(..., max_length=32, description="市场类型，例如 spot / futures")
    symbol: str = Field(..., max_length=64, description="交易对，例如 BTCUSDT")
    # 说明（重要）：
    # - timeframe 由服务端控制：即使客户端传入，也会在 API 层强制覆盖为 1m
    # - 这里将其改为可选，避免客户端误以为可以通过传参改变实际导入粒度
    timeframe: Optional[str] = Field(
        default=None,
        max_length=16,
        description="时间周期（可选；服务端将强制覆盖为 1m）",
    )

    start_date: datetime = Field(..., description="导入开始时间（包含）")
    end_date: datetime = Field(..., description="导入结束时间（包含）")

    import_types: List[str] = Field(
        default_factory=list,
        description="导入类型列表，例如 ['kline','trade']（JSON存储）",
    )

    @field_validator("import_types")
    @classmethod
    def validate_import_types_allowlist(cls, value: List[str]) -> List[str]:
        """
        Validate import_types against a strict allowlist.

        Notes:
            - We enforce this at the schema layer so FastAPI can return 422 before
              reaching the handler.
            - The allowlist is part of the public API contract; error message must
              include all allowed values for client-side fixes.
        """
        # 说明：入参可能为空列表；空表示“由服务端默认策略决定”，这里不强制要求至少一个
        unknown_types = sorted({t for t in (value or []) if t not in _ALLOWED_IMPORT_TYPES})
        if unknown_types:
            allowed = sorted(_ALLOWED_IMPORT_TYPES)
            raise ValueError(
                f"import_types contains unsupported values: {unknown_types}. "
                f"Allowed values: {allowed}"
            )
        return value

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_datetime_tz_aware(cls, value: datetime, info):  # type: ignore[override]
        """Reject naive datetimes explicitly to preserve correct timezone semantics."""
        return _require_tz_aware(value, field_name=info.field_name)


class MarketImportCreateResponse(BaseModel):
    """
    Market import task creation response.

    Attributes:
        task_id: The created task id.
    """

    task_id: int = Field(..., description="任务ID")


class MarketImportTaskResponse(BaseModel):
    """
    Market import task response model (for GET/list endpoints).

    This schema is intentionally tolerant for `result_json`, because different
    import types may emit different result payloads.

    Attributes:
        id: Task id.
        status: Task status.
        progress: Task progress in [0.0, 1.0].
        result_json: Task result payload (arbitrary JSON-like object).
        last_error: Last error message if failed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="任务ID")
    name: Optional[str] = Field(default=None, description="任务名称（可选）")
    created_by: Optional[int] = Field(default=None, description="创建者用户ID（可选）")

    exchange: str = Field(..., description="交易所标识")
    market_type: str = Field(..., description="市场类型")
    symbol: str = Field(..., description="交易对")
    timeframe: str = Field(..., description="时间周期")

    start_date: datetime = Field(..., description="导入开始时间")
    end_date: datetime = Field(..., description="导入结束时间")

    import_types: List[str] = Field(default_factory=list, description="导入类型列表")

    status: MarketImportStatus = Field(..., description="任务状态")
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="任务进度（0~1）",
    )

    result_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="任务结果（JSON，可变结构）",
    )
    last_error: Optional[str] = Field(default=None, description="最后错误信息（失败时）")

    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    finished_at: Optional[datetime] = Field(default=None, description="完成时间（成功/失败时）")

    @field_validator("start_date", "end_date", "created_at", "updated_at", "finished_at")
    @classmethod
    def validate_response_datetimes_tz_aware(cls, value: Optional[datetime], info):  # type: ignore[override]
        """
        Ensure all datetime fields are timezone-aware.

        Even though DB columns are timezone-aware, this extra check prevents
        accidentally serializing naive timestamps if upstream code constructs
        response payloads manually.
        """
        if value is None:
            return value
        return _require_tz_aware(value, field_name=info.field_name)
