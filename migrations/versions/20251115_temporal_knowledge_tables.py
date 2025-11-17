"""add temporal knowledge tables

Revision ID: 20251115_temporal_knowledge_tables
Revises: 20251028_timestamp_tz_alignment
Create Date: 2025-11-15 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251115_temporal_knowledge_tables"
down_revision = "20251028_timestamp_tz_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("statement_type", sa.String(length=32), nullable=False),
        sa.Column("temporal_type", sa.String(length=32), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_statements_tenant_id", "knowledge_statements", ["tenant_id"])
    op.create_index("ix_knowledge_statements_project_id", "knowledge_statements", ["project_id"])
    op.create_index("ix_knowledge_statements_document_id", "knowledge_statements", ["document_id"])
    op.create_index("ix_knowledge_statements_chunk_id", "knowledge_statements", ["chunk_id"])
    op.create_index("ix_knowledge_statements_valid_at", "knowledge_statements", ["valid_at"])

    op.create_table(
        "knowledge_statement_triplets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entity_id", sa.Integer(), nullable=False),
        sa.Column("object_entity_id", sa.Integer(), nullable=False),
        sa.Column("predicate", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_entity_id"],
            ["knowledge_entities.id"],
            ondelete="CASCADE",
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
            ["subject_entity_id"],
            ["knowledge_entities.id"],
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
        "ix_knowledge_statement_triplets_tenant_id",
        "knowledge_statement_triplets",
        ["tenant_id"],
    )
    op.create_index(
        "ix_knowledge_statement_triplets_project_id",
        "knowledge_statement_triplets",
        ["project_id"],
    )
    op.create_index(
        "ix_knowledge_statement_triplets_statement_id",
        "knowledge_statement_triplets",
        ["statement_id"],
    )
    op.create_index(
        "ix_knowledge_statement_triplets_subject_entity_id",
        "knowledge_statement_triplets",
        ["subject_entity_id"],
    )
    op.create_index(
        "ix_knowledge_statement_triplets_object_entity_id",
        "knowledge_statement_triplets",
        ["object_entity_id"],
    )
    op.create_index(
        "ix_knowledge_statement_triplets_subject_object",
        "knowledge_statement_triplets",
        ["subject_entity_id", "object_entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_statement_triplets_subject_object", table_name="knowledge_statement_triplets")
    op.drop_index("ix_knowledge_statement_triplets_object_entity_id", table_name="knowledge_statement_triplets")
    op.drop_index("ix_knowledge_statement_triplets_subject_entity_id", table_name="knowledge_statement_triplets")
    op.drop_index("ix_knowledge_statement_triplets_statement_id", table_name="knowledge_statement_triplets")
    op.drop_index("ix_knowledge_statement_triplets_project_id", table_name="knowledge_statement_triplets")
    op.drop_index("ix_knowledge_statement_triplets_tenant_id", table_name="knowledge_statement_triplets")
    op.drop_table("knowledge_statement_triplets")

    op.drop_index("ix_knowledge_statements_valid_at", table_name="knowledge_statements")
    op.drop_index("ix_knowledge_statements_chunk_id", table_name="knowledge_statements")
    op.drop_index("ix_knowledge_statements_document_id", table_name="knowledge_statements")
    op.drop_index("ix_knowledge_statements_project_id", table_name="knowledge_statements")
    op.drop_index("ix_knowledge_statements_tenant_id", table_name="knowledge_statements")
    op.drop_table("knowledge_statements")
