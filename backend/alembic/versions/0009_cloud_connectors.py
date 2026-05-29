"""Cloud connectors table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create the `cloud_connectors` table used to store cloud connector configurations and status.
    
    The table schema includes:
    - `id` (String(36)): primary key identifier.
    - `name` (String(255)): human-readable connector name, not nullable.
    - `connector_type` (String(30)): connector type identifier, not nullable.
    - `config` (JSON): connector-specific configuration, nullable.
    - `enabled` (Boolean): whether the connector is active; defaults to `true`.
    - `last_polled_at` (DateTime with timezone): timestamp of the last poll, nullable.
    - `last_error` (Text): last error message, nullable.
    - `poll_interval_seconds` (Integer): polling interval in seconds; defaults to `300`.
    - `events_ingested_total` (Integer): cumulative ingested events counter; defaults to `0`.
    - `created_at` (DateTime with timezone): creation timestamp; defaults to current time.
    """
    op.create_table(
        'cloud_connectors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('connector_type', sa.String(30), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_polled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('poll_interval_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('events_ingested_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """
    Remove the 'cloud_connectors' table from the database.
    
    This operation drops the table and all data it contains, reversing the schema change introduced by the migration that created the table.
    """
    op.drop_table('cloud_connectors')
