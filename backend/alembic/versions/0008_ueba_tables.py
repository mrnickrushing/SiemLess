"""UEBA tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create the database schema for user behavior analytics by adding the user_behavior_profiles and ueba_anomalies tables and their username indexes.
    
    Creates:
    - user_behavior_profiles: stores per-user baseline data and evaluation timestamps with columns:
      - id (primary key)
      - username (unique, not null)
      - baseline_login_hours (JSON, nullable)
      - baseline_source_ips (JSON, nullable)
      - baseline_event_rate_per_hour (float, not null, default 0)
      - baseline_computed_at (timezone-aware datetime, nullable)
      - last_evaluated_at (timezone-aware datetime, nullable)
    - ueba_anomalies: records detected anomalies with columns:
      - id (primary key)
      - username (not null)
      - event_id (nullable)
      - anomaly_type (not null)
      - score (not null)
      - details (JSON, nullable)
      - alert_id (nullable)
      - created_at (timezone-aware datetime, not null, default now())
    
    Also creates indexes on username for both tables.
    """
    op.create_table(
        'user_behavior_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(255), nullable=False, unique=True),
        sa.Column('baseline_login_hours', sa.JSON(), nullable=True),
        sa.Column('baseline_source_ips', sa.JSON(), nullable=True),
        sa.Column('baseline_event_rate_per_hour', sa.Float(), nullable=False, server_default='0'),
        sa.Column('baseline_computed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_user_behavior_profiles_username', 'user_behavior_profiles', ['username'])

    op.create_table(
        'ueba_anomalies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('event_id', sa.String(36), nullable=True),
        sa.Column('anomaly_type', sa.String(50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('alert_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ueba_anomalies_username', 'ueba_anomalies', ['username'])


def downgrade() -> None:
    """
    Remove the UEBA-related database objects introduced by this migration.
    
    Drops the `ueba_anomalies` and `user_behavior_profiles` tables created in the corresponding upgrade step.
    """
    op.drop_table('ueba_anomalies')
    op.drop_table('user_behavior_profiles')
