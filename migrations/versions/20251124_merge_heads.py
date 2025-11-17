"""merge statement invalidation queue and event batches heads

Revision ID: 20251124_merge_heads
Revises: 20251115_statement_invalidation_queue, 20251123_event_batches
Create Date: 2025-11-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251124_merge_heads"
down_revision = ("20251115_statement_invalidation_queue", "20251123_event_batches")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge revision; no schema changes.
    pass


def downgrade() -> None:
    # Merge revision; nothing to undo.
    pass
