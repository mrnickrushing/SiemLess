"""Asset inventory tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create schema for asset management: three tables (assets, asset_software, asset_vulnerabilities) and their indexes.
    
    Creates:
    - assets: primary id, unique hostname, ip_addresses (JSON), os_type, os_version, asset_type (default 'unknown'), first_seen/last_seen timestamps (default now), tags (JSON), criticality (default 'medium'), and cve_count (default 0); index on hostname.
    - asset_software: primary id, asset_id FK -> assets.id (ON DELETE CASCADE), name, version, cpe, last_scanned (default now); index on asset_id.
    - asset_vulnerabilities: primary id, asset_id FK -> assets.id (ON DELETE CASCADE), cve_id, cvss_score, description, severity (default 'medium'), published_at, fetched_at (default now); index on asset_id.
    """
    op.create_table(
        'assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('hostname', sa.String(255), nullable=False, unique=True),
        sa.Column('ip_addresses', sa.JSON(), nullable=True),
        sa.Column('os_type', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(100), nullable=True),
        sa.Column('asset_type', sa.String(50), nullable=False, server_default='unknown'),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('criticality', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('cve_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_assets_hostname', 'assets', ['hostname'])

    op.create_table(
        'asset_software',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('asset_id', sa.String(36), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('version', sa.String(100), nullable=True),
        sa.Column('cpe', sa.String(500), nullable=True),
        sa.Column('last_scanned', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_asset_software_asset_id', 'asset_software', ['asset_id'])

    op.create_table(
        'asset_vulnerabilities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('asset_id', sa.String(36), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cve_id', sa.String(50), nullable=False),
        sa.Column('cvss_score', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_asset_vulnerabilities_asset_id', 'asset_vulnerabilities', ['asset_id'])


def downgrade() -> None:
    """
    Remove the asset-related database tables created by the corresponding upgrade migration.
    
    Drops the `asset_vulnerabilities`, `asset_software`, and `assets` tables in that order to respect their foreign-key dependencies.
    """
    op.drop_table('asset_vulnerabilities')
    op.drop_table('asset_software')
    op.drop_table('assets')
