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
    """
    Placeholder migration preserving the Alembic revision chain for the ECS normalization column.
    
    Performs no schema changes because the `normalized_fields` column was already added to `security_events` in migration 0004; this revision exists solely to advance the migration sequence.
    """
    pass


def downgrade() -> None:
    """
    No-op downgrade for revision 0014 that preserves the Alembic migration chain.
    
    This downgrade performs no schema changes or rollback actions. The ECS normalization column `normalized_fields` was already added in migration `0004`, so no changes are required here.
    """
    pass
