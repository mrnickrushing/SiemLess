"""
Convert security_events.tags from VARCHAR ARRAY to JSONB.

JSON/JSONB is supported by both PostgreSQL and SQLite (via SQLAlchemy's
JSON type), whereas PostgreSQL's native ARRAY type is not portable.
This migration converts the existing array column so the SQLAlchemy model
can use the universal JSON type.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert VARCHAR[] → JSONB, preserving all existing array values.
    # to_jsonb() on a PostgreSQL array produces a JSON array, e.g. '["a","b"]'.
    op.execute("""
        ALTER TABLE security_events
        ALTER COLUMN tags TYPE JSONB
        USING to_jsonb(tags)
    """)

    # The old ARRAY index is no longer valid; drop and recreate as a GIN index
    # on the JSONB column for efficient containment queries.
    op.execute("DROP INDEX IF EXISTS ix_security_events_tags")
    op.execute("""
        CREATE INDEX ix_security_events_tags
        ON security_events USING gin(tags)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_security_events_tags")
    op.execute("""
        ALTER TABLE security_events
        ALTER COLUMN tags TYPE VARCHAR[]
        USING ARRAY(SELECT jsonb_array_elements_text(tags))
    """)
    op.execute("""
        CREATE INDEX ix_security_events_tags ON security_events (tags)
    """)
