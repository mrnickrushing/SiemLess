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
    """
    Create the `integration_configs` table used to store integration metadata and settings.
    
    Creates a table with the following columns:
    - `id` (String(36)): primary key UUID.
    - `name` (String(255)): integration name, required.
    - `integration_type` (String(30)): type identifier for the integration, required.
    - `config` (JSON): integration configuration payload, required.
    - `enabled` (Boolean): whether the integration is active; defaults to `true` at the database level.
    - `created_at` (DateTime(timezone=True)): timestamp of record creation with a server-side default of `now()`.
    """
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
    """
    Drop the `integration_configs` table from the database.
    
    This operation removes the `integration_configs` table created by this migration.
    """
    op.drop_table('integration_configs')
