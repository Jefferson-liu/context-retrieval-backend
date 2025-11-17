"""Add document_id FK to text_threads

Revision ID: 20251126_add_text_thread_document_fk
Revises: 20251117_add_invalidated_by_to_events
Create Date: 2025-11-17 16:45:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251126_add_text_thread_document_fk"
down_revision = "20251117_add_invalidated_by_to_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "text_threads",
        sa.Column("document_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_text_threads_document_id"),
        "text_threads",
        ["document_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_text_threads_document_id_documents",
        "text_threads",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_text_threads_document_id_documents",
        "text_threads",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_text_threads_document_id"), table_name="text_threads")
    op.drop_column("text_threads", "document_id")
