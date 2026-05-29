"""RBAC tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create RBAC-related database tables and indexes.
    
    Creates three tables and associated indexes/constraints:
    - organizations: columns `id`, `name` (unique), `slug` (unique), `created_at` (timezone-aware, defaults to now).
    - org_users: columns `id`, `org_id`, `username`, `email` (nullable), `role` (defaults to 'analyst'), `created_at` (timezone-aware, defaults to now); unique constraint on (`org_id`, `username`); index on `org_id`.
    - api_tokens: columns `id`, `username`, `token_hash` (unique), `description` (nullable), `expires_at` (nullable), `created_at` (timezone-aware, defaults to now); index on `username`.
    """
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'org_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(500), nullable=True),
        sa.Column('role', sa.String(30), nullable=False, server_default='analyst'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('org_id', 'username', name='uq_org_users_org_username'),
    )
    op.create_index('ix_org_users_org_id', 'org_users', ['org_id'])

    op.create_table(
        'api_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('token_hash', sa.String(128), nullable=False, unique=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_tokens_username', 'api_tokens', ['username'])


def downgrade() -> None:
    """
    Revert the migration by dropping the RBAC-related tables.
    
    Drops the tables in the following order to safely remove dependencies: `api_tokens`, `org_users`, then `organizations`.
    """
    op.drop_table('api_tokens')
    op.drop_table('org_users')
    op.drop_table('organizations')
