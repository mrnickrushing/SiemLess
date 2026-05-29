"""Threat feed connectors table

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'threat_feed_connectors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('feed_type', sa.String(30), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=True),
        sa.Column('last_pulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pull_interval_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('indicator_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('threat_feed_connectors')
