"""Remove duplicate statement text from knowledge_events

Revision ID: 20251127_remove_statement_text_from_events
Revises: 20251126_add_text_thread_document_fk
Create Date: 2025-11-17 17:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251127_remove_statement_text_from_events"
down_revision = "20251126_add_text_thread_document_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use IF EXISTS so the migration can run even if the column was already removed manually
    op.execute("ALTER TABLE knowledge_events DROP COLUMN IF EXISTS statement")
    op.alter_column(
        "knowledge_events",
        "statement_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_events",
        "statement_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "knowledge_events",
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column(
        "knowledge_events",
        "statement",
        server_default=None,
    )
