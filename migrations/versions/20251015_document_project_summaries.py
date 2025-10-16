"""Add document and project summaries tables

Revision ID: 20251015_document_project_summaries
Revises: 20251014_knowledge_graph_schema
Create Date: 2025-10-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251015_document_project_summaries"
down_revision = "20251014_knowledge_graph_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("summary_tokens", sa.Integer(), nullable=True),
        sa.Column("summary_hash", sa.String(length=64), nullable=True),
        sa.Column("milvus_primary_key", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", name="uq_document_summary_document_id"),
    )
    op.create_index("ix_document_summaries_tenant_id", "document_summaries", ["tenant_id"])
    op.create_index("ix_document_summaries_project_id", "document_summaries", ["project_id"])
    op.create_index(
        "ix_document_summaries_tenant_project_document",
        "document_summaries",
        ["tenant_id", "project_id", "document_id"],
    )
    op.create_index("ix_document_summaries_milvus_pk", "document_summaries", ["milvus_primary_key"])

    op.create_table(
        "project_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("summary_tokens", sa.Integer(), nullable=True),
        sa.Column("source_document_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "project_id", name="uq_project_summary_tenant_project"),
    )
    op.create_index("ix_project_summaries_tenant_id", "project_summaries", ["tenant_id"])
    op.create_index("ix_project_summaries_project_id", "project_summaries", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_summaries_project_id", table_name="project_summaries")
    op.drop_index("ix_project_summaries_tenant_id", table_name="project_summaries")
    op.drop_table("project_summaries")

    op.drop_index("ix_document_summaries_milvus_pk", table_name="document_summaries")
    op.drop_index("ix_document_summaries_tenant_project_document", table_name="document_summaries")
    op.drop_index("ix_document_summaries_project_id", table_name="document_summaries")
    op.drop_index("ix_document_summaries_tenant_id", table_name="document_summaries")
    op.drop_table("document_summaries")
