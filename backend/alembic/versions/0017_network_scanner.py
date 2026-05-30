"""Network scanner tables

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'network_scans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('target_cidr', sa.String(64), nullable=False),
        sa.Column('ports', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='queued'),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hosts_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hosts_scanned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hosts_up', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('open_ports', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
    )
    op.create_index('ix_network_scans_status', 'network_scans', ['status'])
    op.create_index('ix_network_scans_created_at', 'network_scans', ['created_at'])

    op.create_table(
        'network_scan_hosts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scan_id', sa.String(36), sa.ForeignKey('network_scans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='down'),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('open_ports', sa.JSON(), nullable=True),
        sa.Column('services', sa.JSON(), nullable=True),
        sa.Column('mac_address', sa.String(64), nullable=True),
        sa.Column('os_guess', sa.String(255), nullable=True),
        sa.Column('asset_id', sa.String(36), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('error', sa.Text(), nullable=True),
    )
    op.create_index('ix_network_scan_hosts_scan_id', 'network_scan_hosts', ['scan_id'])
    op.create_index('ix_network_scan_hosts_ip_address', 'network_scan_hosts', ['ip_address'])


def downgrade() -> None:
    op.drop_table('network_scan_hosts')
    op.drop_table('network_scans')
