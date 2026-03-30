"""Add unique constraints for market import idempotency.

Revision ID: 7c1b2f3a4d11
Revises: 9f3c2a4b1d8e
Create Date: 2026-03-30

This migration enforces idempotent writes for market import flows by adding
database-level uniqueness constraints.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "7c1b2f3a4d11"
down_revision = "9f3c2a4b1d8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes."""
    op.create_unique_constraint(
        "uq_trade_identity",
        "market_trades",
        ["exchange", "symbol", "market_type", "trade_id"],
    )
    op.create_unique_constraint(
        "uq_funding_identity",
        "market_fundings",
        ["exchange", "symbol", "funding_time"],
    )
    op.create_unique_constraint(
        "uq_open_interest_identity",
        "market_open_interests",
        ["exchange", "symbol", "market_type", "event_time"],
    )


def downgrade() -> None:
    """Revert schema changes."""
    op.drop_constraint(
        "uq_open_interest_identity", "market_open_interests", type_="unique"
    )
    op.drop_constraint("uq_funding_identity", "market_fundings", type_="unique")
    op.drop_constraint("uq_trade_identity", "market_trades", type_="unique")

