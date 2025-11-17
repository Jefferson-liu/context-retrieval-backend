"""Resize knowledge_statements.embedding to 768 dims

Revision ID: 20251130_resize_statement_embeddings_to_768
Revises: 20251129_remove_statement_and_temporal_type_from_events
Create Date: 2025-11-17 17:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "20251130_resize_statement_embeddings_to_768"
down_revision = "20251129_remove_statement_and_temporal_type_from_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dropping and recreating the column resets embeddings; re-embed as needed.
    op.drop_column("knowledge_statements", "embedding")
    op.add_column(
        "knowledge_statements",
        sa.Column("embedding", Vector(dim=768), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_statements", "embedding")
    op.add_column(
        "knowledge_statements",
        sa.Column("embedding", Vector(dim=768), nullable=True),
    )
