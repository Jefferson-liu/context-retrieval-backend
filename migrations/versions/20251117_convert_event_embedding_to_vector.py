"""Convert knowledge_events.embedding to pgvector

Revision ID: 20251117_convert_event_embedding_to_vector
Revises: 20251124_merge_heads
Create Date: 2025-11-17 03:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import settings

# revision identifiers, used by Alembic.
revision = "20251117_convert_event_embedding_to_vector"
down_revision = "20251124_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dim = settings.EMBEDDING_VECTOR_DIM
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # If existing data cannot be cast from JSON to vector, recreate the column.
    op.execute("ALTER TABLE knowledge_events DROP COLUMN IF EXISTS embedding;")
    op.execute(
        sa.text(
            f"ALTER TABLE knowledge_events "
            f"ADD COLUMN embedding vector({dim})"
        )
    )


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_events DROP COLUMN IF EXISTS embedding;")
    op.execute(
        sa.text(
            "ALTER TABLE knowledge_events ADD COLUMN embedding json"
        )
    )
