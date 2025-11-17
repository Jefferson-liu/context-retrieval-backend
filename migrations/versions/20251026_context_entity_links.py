"""Add context entities with document and thread associations

Revision ID: 20251026_context_entity_links
Revises: 20251025_text_threads
Create Date: 2025-10-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251026_context_entity_links"
down_revision = "20251025_text_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_identifier", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "entity_type",
            "entity_identifier",
            name="uq_context_entity_scope_identifier",
        ),
    )
    op.create_index("ix_context_entities_tenant_id", "context_entities", ["tenant_id"])
    op.create_index("ix_context_entities_project_id", "context_entities", ["project_id"])
    op.create_index("ix_context_entities_entity_type", "context_entities", ["entity_type"])
    op.create_index("ix_context_entities_entity_identifier", "context_entities", ["entity_identifier"])

    op.create_table(
        "context_entity_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("context_entity_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("association_type", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["context_entity_id"], ["context_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("context_entity_id", "document_id", name="uq_context_entity_document"),
    )
    op.create_index(
        "ix_context_entity_documents_entity",
        "context_entity_documents",
        ["context_entity_id"],
    )
    op.create_index(
        "ix_context_entity_documents_document",
        "context_entity_documents",
        ["document_id"],
    )

    op.create_table(
        "context_entity_threads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("context_entity_id", sa.Integer(), nullable=False),
        sa.Column("text_thread_id", sa.Integer(), nullable=False),
        sa.Column("association_type", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["context_entity_id"], ["context_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["text_thread_id"], ["text_threads.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("context_entity_id", "text_thread_id", name="uq_context_entity_thread"),
    )
    op.create_index(
        "ix_context_entity_threads_entity",
        "context_entity_threads",
        ["context_entity_id"],
    )
    op.create_index(
        "ix_context_entity_threads_thread",
        "context_entity_threads",
        ["text_thread_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_context_entity_threads_thread", table_name="context_entity_threads")
    op.drop_index("ix_context_entity_threads_entity", table_name="context_entity_threads")
    op.drop_table("context_entity_threads")

    op.drop_index("ix_context_entity_documents_document", table_name="context_entity_documents")
    op.drop_index("ix_context_entity_documents_entity", table_name="context_entity_documents")
    op.drop_table("context_entity_documents")

    op.drop_index("ix_context_entities_entity_identifier", table_name="context_entities")
    op.drop_index("ix_context_entities_entity_type", table_name="context_entities")
    op.drop_index("ix_context_entities_project_id", table_name="context_entities")
    op.drop_index("ix_context_entities_tenant_id", table_name="context_entities")
    op.drop_table("context_entities")
