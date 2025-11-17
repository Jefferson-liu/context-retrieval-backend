"""Add invalidated_by to knowledge_events

Revision ID: 20251117_add_invalidated_by_to_events
Revises: 20251117_convert_event_embedding_to_vector
Create Date: 2025-11-17 04:55:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251117_add_invalidated_by_to_events"
down_revision = "20251117_convert_event_embedding_to_vector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_events",
        sa.Column(
            "invalidated_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_knowledge_events_invalidated_by",
        "knowledge_events",
        ["invalidated_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_events_invalidated_by", table_name="knowledge_events")
    op.drop_column("knowledge_events", "invalidated_by")
