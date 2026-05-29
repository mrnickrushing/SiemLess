"""Alert deduplication and risk scoring

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('security_events', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('security_events', sa.Column('normalized_fields', sa.JSON(), nullable=True))
    op.add_column('alerts', sa.Column('hit_count', sa.Integer(), server_default='1', nullable=False))
    op.add_column('alerts', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('alerts', sa.Column('dedup_key', sa.String(255), nullable=True))
    op.create_index('ix_alerts_dedup_key', 'alerts', ['dedup_key'])


def downgrade() -> None:
    op.drop_index('ix_alerts_dedup_key', table_name='alerts')
    op.drop_column('alerts', 'dedup_key')
    op.drop_column('alerts', 'risk_score')
    op.drop_column('alerts', 'hit_count')
    op.drop_column('security_events', 'normalized_fields')
    op.drop_column('security_events', 'risk_score')
