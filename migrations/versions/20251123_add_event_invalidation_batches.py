"""add event invalidation batches

Revision ID: 20251123_event_batches
Revises: 20251122_entity_event_resolved
Create Date: 2025-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251123_event_batches"
down_revision = "20251122_entity_event_resolved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_event_invalidation_batch_items CASCADE")
    op.execute("DROP TABLE IF EXISTS knowledge_event_invalidation_batches CASCADE")
    op.create_table(
        "knowledge_event_invalidation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "knowledge_event_invalidation_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=False, index=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_event_invalidation_batches.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_events.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("new_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_events.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("suggested_invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_event_invalidation_batch_status",
        "knowledge_event_invalidation_batches",
        ["tenant_id", "project_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_event_invalidation_batch_items")
    op.drop_table("knowledge_event_invalidation_batches")
