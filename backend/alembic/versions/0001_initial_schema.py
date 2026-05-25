"""
Initial schema — creates all four core tables.

Revision ID: 0001
Revises: (none)
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # correlation_rules (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "correlation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(50), nullable=False, server_default="system"),
        sa.Column("condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("threshold", sa.Integer, nullable=False, server_default="1"),
        sa.Column("time_window", sa.Integer, nullable=False, server_default="300"),
        sa.Column("mitre_tactic", sa.String(100), nullable=True),
        sa.Column("mitre_technique", sa.String(100), nullable=True),
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
        sa.Column("last_triggered", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "alert_title_template",
            sa.String(500),
            nullable=False,
            server_default="{rule_name} triggered",
        ),
        sa.Column(
            "alert_description_template",
            sa.Text,
            nullable=False,
            server_default="Rule {rule_name} triggered {count} times in {window} seconds.",
        ),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ------------------------------------------------------------------
    # security_events
    # ------------------------------------------------------------------
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("destination_ip", sa.String(45), nullable=True),
        sa.Column("source_port", sa.Integer, nullable=True),
        sa.Column("destination_port", sa.Integer, nullable=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("log_source", sa.String(50), nullable=False, server_default="api"),
        sa.Column("log_type", sa.String(50), nullable=False, server_default="generic"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="low"),
        sa.Column("category", sa.String(50), nullable=False, server_default="system"),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("raw_log", sa.Text, nullable=True),
        sa.Column("parsed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("user", sa.String(255), nullable=True),
        sa.Column("process", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=True),
    )
    op.create_index("ix_security_events_timestamp", "security_events", ["timestamp"])
    op.create_index("ix_security_events_source_ip", "security_events", ["source_ip"])
    op.create_index("ix_security_events_hostname", "security_events", ["hostname"])
    op.create_index("ix_security_events_tags", "security_events", ["tags"], postgresql_using="gin")
    op.create_index("ix_security_events_user", "security_events", ["user"])
    op.create_index(
        "ix_security_events_timestamp_severity",
        "security_events",
        ["timestamp", "severity"],
    )
    op.create_index(
        "ix_security_events_log_type_category",
        "security_events",
        ["log_type", "category"],
    )
    op.create_index(
        "ix_security_events_source_ip_timestamp",
        "security_events",
        ["source_ip", "timestamp"],
    )

    # ------------------------------------------------------------------
    # alerts  (FK -> correlation_rules)
    # ------------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("correlation_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_ips", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_users", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mitre_tactic", sa.String(100), nullable=True),
        sa.Column("mitre_technique", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
    )
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"])

    # ------------------------------------------------------------------
    # threat_intel_cache
    # ------------------------------------------------------------------
    op.create_table(
        "threat_intel_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator", sa.String(500), nullable=False),
        sa.Column("indicator_type", sa.String(50), nullable=False),
        sa.Column("is_malicious", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence_score", sa.Integer, nullable=True),
        sa.Column("threat_types", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "queried_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("asn", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_threat_intel_cache_indicator",
        "threat_intel_cache",
        ["indicator"],
        unique=True,
    )
    op.create_index(
        "ix_threat_intel_cache_indicator_type",
        "threat_intel_cache",
        ["indicator_type"],
    )


def downgrade() -> None:
    op.drop_table("threat_intel_cache")
    op.drop_table("alerts")
    op.drop_table("security_events")
    op.drop_table("correlation_rules")
