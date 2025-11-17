"""add knowledge events table

Revision ID: 20251120_add_events
Revises: 20251115_temporal_knowledge_tables
Create Date: 2025-11-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251120_add_events"
down_revision = "20251115_temporal_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety: drop if an earlier partial run created the table.
    op.execute("DROP TABLE IF EXISTS knowledge_events CASCADE")
    op.create_table(
        "knowledge_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=False, index=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_statements.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("triplets", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("statement_type", sa.String(length=32), nullable=False),
        sa.Column("temporal_type", sa.String(length=32), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_knowledge_events_tenant_project",
        "knowledge_events",
        ["tenant_id", "project_id"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_events")
