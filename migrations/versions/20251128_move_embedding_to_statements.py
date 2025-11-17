"""Move embeddings from knowledge_events to knowledge_statements

Revision ID: 20251128_move_embedding_to_statements
Revises: 20251127_remove_statement_text_from_events
Create Date: 2025-11-17 17:20:00.000000
"""

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "20251128_move_embedding_to_statements"
down_revision = "20251127_remove_statement_text_from_events"
branch_labels = None
depends_on = None


def _embed_dim() -> int:
    """Fixed embedding dimension for statements."""
    return 768


def upgrade() -> None:
    op.add_column(
        "knowledge_statements",
        sa.Column("embedding", Vector(dim=_embed_dim()), nullable=True),
    )

    # Copy embeddings from events to statements where present
    op.execute(
        """
        UPDATE knowledge_statements ks
        SET embedding = ke.embedding
        FROM knowledge_events ke
        WHERE ks.id = ke.statement_id
          AND ke.embedding IS NOT NULL
        """
    )

    op.drop_column("knowledge_events", "embedding")


def downgrade() -> None:
    op.add_column(
        "knowledge_events",
        sa.Column("embedding", Vector(dim=_embed_dim()), nullable=True),
    )

    # Copy embeddings back to events (prefer first match)
    op.execute(
        """
        UPDATE knowledge_events ke
        SET embedding = ks.embedding
        FROM knowledge_statements ks
        WHERE ke.statement_id = ks.id
          AND ks.embedding IS NOT NULL
        """
    )

    op.drop_column("knowledge_statements", "embedding")
