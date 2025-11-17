"""add knowledge event invalidations

Revision ID: 20251121_event_invalidations
Revises: 20251120_add_events
Create Date: 2025-11-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251121_event_invalidations"
down_revision = "20251120_add_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_event_invalidations CASCADE")
    op.create_table(
        "knowledge_event_invalidations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "new_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_events.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("suggested_invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_event_invalidation_status",
        "knowledge_event_invalidations",
        ["tenant_id", "project_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_event_invalidations")
