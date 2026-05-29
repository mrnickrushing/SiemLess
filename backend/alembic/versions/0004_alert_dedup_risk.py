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
    """
    Apply schema changes to support alert deduplication and risk scoring.
    
    Adds nullable `risk_score` (Float) and `normalized_fields` (JSON) to `security_events`; adds `hit_count` (Integer, default 1, non-nullable), `risk_score` (Float), and `dedup_key` (String(255)) to `alerts`; and creates the index `ix_alerts_dedup_key` on `alerts.dedup_key`.
    """
    op.add_column('security_events', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('security_events', sa.Column('normalized_fields', sa.JSON(), nullable=True))
    op.add_column('alerts', sa.Column('hit_count', sa.Integer(), server_default='1', nullable=False))
    op.add_column('alerts', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('alerts', sa.Column('dedup_key', sa.String(255), nullable=True))
    op.create_index('ix_alerts_dedup_key', 'alerts', ['dedup_key'])


def downgrade() -> None:
    """
    Reverts the migration by removing the deduplication/risk-scoring index and columns.
    
    Drops the index `ix_alerts_dedup_key` on `alerts`, removes `dedup_key`, `risk_score`, and `hit_count` from the `alerts` table, and removes `normalized_fields` and `risk_score` from the `security_events` table.
    """
    op.drop_index('ix_alerts_dedup_key', table_name='alerts')
    op.drop_column('alerts', 'dedup_key')
    op.drop_column('alerts', 'risk_score')
    op.drop_column('alerts', 'hit_count')
    op.drop_column('security_events', 'normalized_fields')
    op.drop_column('security_events', 'risk_score')
