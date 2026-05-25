"""
Add saved_searches, watchlist_entries, and SLA columns on alerts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # saved_searches
    # ------------------------------------------------------------------
    op.create_table(
        "saved_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # watchlist_entries
    # ------------------------------------------------------------------
    op.create_table(
        "watchlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_watchlist_entries_entry_type", "watchlist_entries", ["entry_type"])
    op.create_index(
        "ix_watchlist_type_value",
        "watchlist_entries",
        ["entry_type", "value"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # SLA columns on alerts
    # ------------------------------------------------------------------
    op.add_column(
        "alerts",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("sla_breach_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_sla_breach_at", "alerts", ["sla_breach_at"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_created_at", table_name="alerts")
    op.drop_index("ix_alerts_sla_breach_at", table_name="alerts")
    op.drop_column("alerts", "sla_breach_at")
    op.drop_column("alerts", "escalated_at")
    op.drop_index("ix_watchlist_type_value", table_name="watchlist_entries")
    op.drop_index("ix_watchlist_entries_entry_type", table_name="watchlist_entries")
    op.drop_table("watchlist_entries")
    op.drop_table("saved_searches")
