"""add market_import_tasks

Revision ID: 9f3c2a4b1d8e
Revises: 
Create Date: 2026-03-30 18:52:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9f3c2a4b1d8e"
# This repository had no prior Alembic revisions under `migrations/versions/`
# (first migration in the chain). Keep down_revision=None until an older base revision exists.
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create market import task table.

    We keep the schema flexible by storing `import_types` and `result_json`
    as JSON payloads. Progress is stored as a float in [0,1].
    """

    op.create_table(
        "market_import_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="Primary key ID"),
        sa.Column("name", sa.String(length=128), nullable=True, comment="Optional task name for display/search"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="Optional creator user ID"),
        sa.Column("exchange", sa.String(length=32), nullable=False, comment="Exchange identifier, e.g. binance"),
        sa.Column("market_type", sa.String(length=32), nullable=False, comment="Market type, e.g. spot / futures"),
        sa.Column("symbol", sa.String(length=64), nullable=False, comment="Trading symbol, e.g. BTCUSDT"),
        sa.Column("timeframe", sa.String(length=16), nullable=False, comment="Timeframe for kline import, e.g. 1m / 1h"),
        sa.Column("start_date", sa.DateTime(), nullable=False, comment="Import start timestamp (inclusive)"),
        sa.Column("end_date", sa.DateTime(), nullable=False, comment="Import end timestamp (inclusive)"),
        sa.Column(
            "import_types",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
            comment="Import types list (JSON)",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="Task status (pending / running / completed / failed)",
        ),
        sa.Column(
            "progress",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Progress in [0,1]",
        ),
        sa.Column("result_json", sa.JSON(), nullable=True, comment="Result payload (arbitrary JSON)"),
        sa.Column("last_error", sa.String(length=2048), nullable=True, comment="Last error message (if failed)"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Created at",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            comment="Updated at",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(),
            nullable=True,
            comment="Finished at (completed/failed)",
        ),
    )

    op.create_check_constraint(
        "ck_market_import_tasks_status",
        "market_import_tasks",
        "status in ('pending','running','completed','failed')",
    )
    op.create_check_constraint(
        "ck_market_import_tasks_progress",
        "market_import_tasks",
        "progress >= 0 and progress <= 1",
    )


def downgrade() -> None:
    """Drop market import task table."""
    op.drop_table("market_import_tasks")

