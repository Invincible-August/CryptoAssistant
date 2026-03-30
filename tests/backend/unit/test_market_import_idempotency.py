from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.models.market_funding import MarketFunding
from app.models.market_open_interest import MarketOpenInterest
from app.models.market_trade import MarketTrade
from app.services import market_service


def _find_unique_constraint(table, constraint_name: str) -> UniqueConstraint:
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and constraint.name == constraint_name:
            return constraint
    raise AssertionError(f"UniqueConstraint not found: {constraint_name}")


def _constraint_columns(constraint: UniqueConstraint) -> list[str]:
    # SQLAlchemy stores columns as Column objects; we only care about column names.
    return [col.name for col in constraint.columns]


def test_market_trade_has_unique_identity_constraint() -> None:
    constraint = _find_unique_constraint(MarketTrade.__table__, "uq_trade_identity")
    assert _constraint_columns(constraint) == ["exchange", "symbol", "market_type", "trade_id"]


def test_market_funding_has_unique_identity_constraint() -> None:
    constraint = _find_unique_constraint(MarketFunding.__table__, "uq_funding_identity")
    assert _constraint_columns(constraint) == ["exchange", "symbol", "funding_time"]


def test_market_open_interest_has_unique_identity_constraint() -> None:
    constraint = _find_unique_constraint(MarketOpenInterest.__table__, "uq_open_interest_identity")
    assert _constraint_columns(constraint) == ["exchange", "symbol", "market_type", "event_time"]


@dataclass(frozen=True)
class _FakeResult:
    """
    Minimal fake SQLAlchemy result.

    We only implement the scalar accessors that `market_service.save_*` uses.
    """

    scalar_one_or_none_value: Optional[int] = None
    scalar_one_value: Any = None

    def scalar_one_or_none(self) -> Optional[int]:
        return self.scalar_one_or_none_value

    def scalar_one(self) -> Any:
        return self.scalar_one_value


@pytest.mark.asyncio
async def test_market_service_trade_builds_postgres_on_conflict_do_nothing() -> None:
    """
    Ensure `save_trade()` builds a PostgreSQL `ON CONFLICT ... DO NOTHING` statement
    bound to the unique constraint `uq_trade_identity`.

    This is a non-DB test: we intercept the statement passed into `db.execute()`
    and validate its compiled SQL.
    """

    captured_insert: list[Any] = []

    class _FakeSession:
        async def execute(self, stmt: Any) -> _FakeResult:
            # Call order in `save_trade()`:
            # 1) execute(insert ... returning)
            # 2) execute(select(MarketTrade).where(MarketTrade.id == inserted_pk))
            if len(captured_insert) == 0:
                captured_insert.append(stmt)
                return _FakeResult(scalar_one_or_none_value=1, scalar_one_value=1)
            return _FakeResult(
                scalar_one_value=MarketTrade(
                    id=1,
                    exchange="binance",
                    symbol="BTCUSDT",
                    market_type="spot",
                    trade_id="123",
                    price=Decimal("1.23"),
                    quantity=Decimal("0.10"),
                    side="buy",
                    event_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
                )
            )

    session = _FakeSession()
    trade_data = {
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "market_type": "spot",
        "trade_id": "123",
        "price": 1.23,
        "quantity": 0.10,
        "side": "buy",
        "event_time": datetime(2026, 3, 1, tzinfo=timezone.utc),
    }

    _ = await market_service.save_trade(session, trade_data)
    assert captured_insert, "insert statement not captured"

    sql = str(captured_insert[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "ON CONSTRAINT uq_trade_identity" in sql
    assert "DO NOTHING" in sql


@pytest.mark.asyncio
async def test_market_service_funding_builds_postgres_on_conflict_do_update() -> None:
    """
    Ensure `save_funding()` builds `ON CONFLICT ... DO UPDATE` on `uq_funding_identity`.
    """

    captured_insert: list[Any] = []

    class _FakeSession:
        async def execute(self, stmt: Any) -> _FakeResult:
            # Call order in `save_funding()`:
            # 1) execute(insert ... returning)
            # 2) execute(select(MarketFunding).where(MarketFunding.id == funding_pk))
            if len(captured_insert) == 0:
                captured_insert.append(stmt)
                return _FakeResult(scalar_one_or_none_value=None, scalar_one_value=1)
            return _FakeResult(
                scalar_one_value=MarketFunding(
                    id=1,
                    exchange="binance",
                    symbol="BTCUSDT",
                    funding_rate=Decimal("0.01"),
                    funding_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
                )
            )

    session = _FakeSession()
    funding_data = {
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "funding_time": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "funding_rate": 0.01,
    }

    _ = await market_service.save_funding(session, funding_data)
    assert captured_insert, "insert statement not captured"

    sql = str(captured_insert[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "ON CONSTRAINT uq_funding_identity" in sql
    assert "DO UPDATE" in sql


@pytest.mark.asyncio
async def test_market_service_open_interest_builds_postgres_on_conflict_do_update() -> None:
    """
    Ensure `save_open_interest()` builds `ON CONFLICT ... DO UPDATE` on
    `uq_open_interest_identity`.
    """

    captured_insert: list[Any] = []

    class _FakeSession:
        async def execute(self, stmt: Any) -> _FakeResult:
            # Call order in `save_open_interest()`:
            # 1) execute(insert ... returning)
            # 2) execute(select(MarketOpenInterest).where(MarketOpenInterest.id == oi_pk))
            if len(captured_insert) == 0:
                captured_insert.append(stmt)
                return _FakeResult(scalar_one_or_none_value=None, scalar_one_value=1)
            return _FakeResult(
                scalar_one_value=MarketOpenInterest(
                    id=1,
                    exchange="binance",
                    symbol="BTCUSDT",
                    market_type="futures",
                    open_interest=Decimal("100.0"),
                    event_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
                )
            )

    session = _FakeSession()
    oi_data = {
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "market_type": "futures",
        "event_time": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "open_interest": 100.0,
    }

    _ = await market_service.save_open_interest(session, oi_data)
    assert captured_insert, "insert statement not captured"

    sql = str(captured_insert[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "ON CONSTRAINT uq_open_interest_identity" in sql
    assert "DO UPDATE" in sql


def test_market_service_contains_postgres_upsert_keywords() -> None:
    """
    Lightweight static check to detect accidental regressions where we might remove
    `pg_insert` / `on_conflict_do_*` without changing migrations.
    """

    save_trade_src = inspect.getsource(market_service.save_trade)
    save_funding_src = inspect.getsource(market_service.save_funding)
    save_oi_src = inspect.getsource(market_service.save_open_interest)

    assert "pg_insert" in save_trade_src
    assert "on_conflict_do_nothing" in save_trade_src
    assert "uq_trade_identity" in save_trade_src

    assert "pg_insert" in save_funding_src
    assert "on_conflict_do_update" in save_funding_src
    assert "uq_funding_identity" in save_funding_src

    assert "pg_insert" in save_oi_src
    assert "on_conflict_do_update" in save_oi_src
    assert "uq_open_interest_identity" in save_oi_src

