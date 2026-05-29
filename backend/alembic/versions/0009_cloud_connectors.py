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
    op.drop_table('cloud_connectors')
