"""add event_id and resolved_id to knowledge_entities

Revision ID: 20251122_entity_event_resolved
Revises: 20251121_event_invalidations
Create Date: 2025-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251122_entity_event_resolved"
down_revision = "20251121_event_invalidations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_entities",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_events.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "knowledge_entities",
        sa.Column("resolved_id", sa.Integer(), sa.ForeignKey("knowledge_entities.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_knowledge_entities_event_id", "knowledge_entities", ["event_id"])
    op.create_index("ix_knowledge_entities_resolved_id", "knowledge_entities", ["resolved_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_entities_resolved_id", table_name="knowledge_entities")
    op.drop_index("ix_knowledge_entities_event_id", table_name="knowledge_entities")
    op.drop_column("knowledge_entities", "resolved_id")
    op.drop_column("knowledge_entities", "event_id")
