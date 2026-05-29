"""Retention policy and cold events tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create database schema for retention policies and cold events and add an index on cold_events.original_id.
    
    Creates the `retention_policies` table with columns for policy metadata (id, name, log_type), retention durations (hot_retention_days, cold_retention_days) with defaults, S3 archival configuration (archive_to_s3, s3_bucket, s3_prefix), an enabled flag with default true, and a timezone-aware `created_at` timestamp defaulting to now. Creates the `cold_events` table with `id`, `original_id`, a timezone-aware `archived_at` timestamp defaulting to now, and required `event_data` JSON payload storage. Adds index `ix_cold_events_original_id` on `cold_events(original_id)`.
    """
    op.create_table(
        'retention_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('log_type', sa.String(50), nullable=True),
        sa.Column('hot_retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('cold_retention_days', sa.Integer(), nullable=False, server_default='365'),
        sa.Column('archive_to_s3', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('s3_bucket', sa.String(255), nullable=True),
        sa.Column('s3_prefix', sa.String(255), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'cold_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('original_id', sa.String(36), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('event_data', sa.JSON(), nullable=False),
    )
    op.create_index('ix_cold_events_original_id', 'cold_events', ['original_id'])


def downgrade() -> None:
    """
    Reverts the migration by removing the `cold_events` and `retention_policies` tables.
    
    Drops `cold_events` first, then `retention_policies`.
    """
    op.drop_table('cold_events')
    op.drop_table('retention_policies')
