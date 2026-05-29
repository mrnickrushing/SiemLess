"""Compliance reports table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'compliance_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('framework', sa.String(30), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('generated_by', sa.String(255), nullable=False, server_default='admin'),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('output_format', sa.String(10), nullable=False, server_default='json'),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('compliance_reports')
