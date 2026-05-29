"""Add SSO/OIDC configuration table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sso_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('provider_name', sa.String(100), nullable=False, unique=True),
        sa.Column('client_id', sa.String(500), nullable=False),
        sa.Column('client_secret', sa.String(500), nullable=False),
        sa.Column('authorization_endpoint', sa.Text(), nullable=False),
        sa.Column('token_endpoint', sa.Text(), nullable=False),
        sa.Column('userinfo_endpoint', sa.Text(), nullable=False),
        sa.Column('jwks_uri', sa.Text(), nullable=True),
        sa.Column('scopes', sa.String(500), nullable=False, server_default='openid email profile'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('sso_configs')
