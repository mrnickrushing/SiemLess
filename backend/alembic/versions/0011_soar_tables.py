"""SOAR playbook tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'playbooks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_config', sa.JSON(), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_table(
        'playbook_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('playbook_id', sa.String(36), nullable=False),
        sa.Column('alert_id', sa.String(36), nullable=True),
        sa.Column('triggered_by', sa.String(255), nullable=False, server_default='system'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='running'),
        sa.Column('step_results', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_index('ix_playbook_runs_playbook_id', 'playbook_runs', ['playbook_id'])


def downgrade() -> None:
    op.drop_table('playbook_runs')
    op.drop_table('playbooks')
