import inspect

from sqlalchemy import UniqueConstraint

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


def test_market_service_uses_postgres_on_conflict_for_idempotent_writes() -> None:
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

