"""ECS normalization column (already added in 0004, so this is a no-op placeholder)

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # normalized_fields was already added to security_events in migration 0004
    # This migration serves as a placeholder to keep the chain intact
    pass


def downgrade() -> None:
    pass
