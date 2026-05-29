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
    """
    Create the 'compliance_reports' database table.
    
    Creates a table named 'compliance_reports' with the following columns:
    - id: primary key string(36)
    - framework: string(30), not null
    - title: string(500), not null
    - generated_at: timestamp with timezone, not null, server default now()
    - generated_by: string(255), not null, server default 'admin'
    - parameters: JSON, nullable
    - status: string(20), not null, server default 'pending'
    - output_format: string(10), not null, server default 'json'
    - result_data: JSON, nullable
    - error_message: text, nullable
    - created_at: timestamp with timezone, not null, server default now()
    """
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
    """
    Drop the 'compliance_reports' table and its contents from the database.
    
    This removes the table's schema and any stored rows created by the corresponding migration.
    """
    op.drop_table('compliance_reports')
