"""Case management tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='open'),
        sa.Column('severity', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('assigned_to', sa.String(255), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False, server_default='admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
    )

    op.create_table(
        'case_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(36), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('added_by', sa.String(255), nullable=False, server_default='admin'),
    )
    op.create_index('ix_case_events_case_id', 'case_events', ['case_id'])

    op.create_table(
        'case_alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_id', sa.String(36), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_case_alerts_case_id', 'case_alerts', ['case_id'])

    op.create_table(
        'case_comments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_case_comments_case_id', 'case_comments', ['case_id'])

    op.create_table(
        'case_artifacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artifact_type', sa.String(30), nullable=False),
        sa.Column('value', sa.String(1000), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_case_artifacts_case_id', 'case_artifacts', ['case_id'])


def downgrade() -> None:
    op.drop_table('case_artifacts')
    op.drop_table('case_comments')
    op.drop_table('case_alerts')
    op.drop_table('case_events')
    op.drop_table('cases')
