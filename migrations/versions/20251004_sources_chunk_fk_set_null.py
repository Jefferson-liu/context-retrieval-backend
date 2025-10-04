"""Allow sources.chunk_id to set null on chunk deletion

Revision ID: 20251004_sources_chunk_fk_set_null
Revises: 20251003_multi_tenant_core
Create Date: 2025-10-04
"""

from __future__ import annotations

from alembic import op  # type: ignore
import sqlalchemy as sa


revision = "20251004_sources_chunk_fk_set_null"
down_revision = "20251003_multi_tenant_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sources", "chunk_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("sources_chunk_id_fkey", "sources", type_="foreignkey")
    op.create_foreign_key(
        "sources_chunk_id_fkey",
        "sources",
        "chunks",
        ["chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("sources_chunk_id_fkey", "sources", type_="foreignkey")
    op.create_foreign_key(
        "sources_chunk_id_fkey",
        "sources",
        "chunks",
        ["chunk_id"],
        ["id"],
    )
    op.alter_column("sources", "chunk_id", existing_type=sa.Integer(), nullable=True)
