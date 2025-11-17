"""Remove statement_type/temporal_type from knowledge_events

Revision ID: 20251129_remove_statement_and_temporal_type_from_events
Revises: 20251128_move_embedding_to_statements
Create Date: 2025-11-17 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251129_remove_statement_and_temporal_type_from_events"
down_revision = "20251128_move_embedding_to_statements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("knowledge_events", "statement_type")
    op.drop_column("knowledge_events", "temporal_type")


def downgrade() -> None:
    op.add_column(
        "knowledge_events",
        sa.Column("temporal_type", sa.String(length=32), nullable=False, server_default="ATEMPORAL"),
    )
    op.add_column(
        "knowledge_events",
        sa.Column("statement_type", sa.String(length=32), nullable=False, server_default="FACT"),
    )
    # remove defaults after backfill
    op.alter_column("knowledge_events", "temporal_type", server_default=None)
    op.alter_column("knowledge_events", "statement_type", server_default=None)
