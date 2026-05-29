"""Integration configs table

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integration_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('integration_type', sa.String(30), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('integration_configs')
