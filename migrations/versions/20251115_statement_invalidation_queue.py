"""statement invalidation queue

Revision ID: 20251115_statement_invalidation_queue
Revises: 20251115_temporal_knowledge_tables
Create Date: 2025-11-15 16:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251115_statement_invalidation_queue"
down_revision = "20251115_temporal_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_statement_invalidations CASCADE")
    op.create_table(
        "knowledge_statement_invalidations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_statement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("suggested_invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["new_statement_id"],
            ["knowledge_statements.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["knowledge_statements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_statement_invalidation_status",
        "knowledge_statement_invalidations",
        ["tenant_id", "project_id", "status"],
    )
    op.create_index(
        "ix_statement_invalidation_statement",
        "knowledge_statement_invalidations",
        ["statement_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_statement_invalidation_statement",
        table_name="knowledge_statement_invalidations",
    )
    op.drop_index(
        "ix_statement_invalidation_status",
        table_name="knowledge_statement_invalidations",
    )
    op.drop_table("knowledge_statement_invalidations")
