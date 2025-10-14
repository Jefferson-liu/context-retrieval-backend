"""Create knowledge graph tables

Revision ID: 20251014_knowledge_graph_schema
Revises: 20251004_sources_chunk_fk_set_null
Create Date: 2025-10-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251014_knowledge_graph_schema"
down_revision = "20251004_sources_chunk_fk_set_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
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
            "name",
            "entity_type",
            name="uq_knowledge_entity_name_type",
        ),
    )
    op.create_index("ix_knowledge_entities_tenant_id", "knowledge_entities", ["tenant_id"])
    op.create_index("ix_knowledge_entities_project_id", "knowledge_entities", ["project_id"])

    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_entity_id", sa.Integer(), nullable=False),
        sa.Column("target_entity_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
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
        sa.ForeignKeyConstraint(["source_entity_id"], ["knowledge_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_entity_id"], ["knowledge_entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_knowledge_relationship_unique",
        ),
    )
    op.create_index("ix_knowledge_relationships_tenant_id", "knowledge_relationships", ["tenant_id"])
    op.create_index("ix_knowledge_relationships_project_id", "knowledge_relationships", ["project_id"])
    op.create_index("ix_knowledge_relationships_source_entity_id", "knowledge_relationships", ["source_entity_id"])
    op.create_index("ix_knowledge_relationships_target_entity_id", "knowledge_relationships", ["target_entity_id"])

    op.create_table(
        "knowledge_relationship_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("relationship_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["relationship_id"], ["knowledge_relationships.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("relationship_id", "key", name="uq_relationship_metadata_key"),
    )
    op.create_index("ix_knowledge_relationship_metadata_tenant_id", "knowledge_relationship_metadata", ["tenant_id"])
    op.create_index("ix_knowledge_relationship_metadata_project_id", "knowledge_relationship_metadata", ["project_id"])
    op.create_index(
        "ix_knowledge_relationship_metadata_relationship_id",
        "knowledge_relationship_metadata",
        ["relationship_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_relationship_metadata_relationship_id", table_name="knowledge_relationship_metadata")
    op.drop_index("ix_knowledge_relationship_metadata_project_id", table_name="knowledge_relationship_metadata")
    op.drop_index("ix_knowledge_relationship_metadata_tenant_id", table_name="knowledge_relationship_metadata")
    op.drop_table("knowledge_relationship_metadata")

    op.drop_index("ix_knowledge_relationships_target_entity_id", table_name="knowledge_relationships")
    op.drop_index("ix_knowledge_relationships_source_entity_id", table_name="knowledge_relationships")
    op.drop_index("ix_knowledge_relationships_project_id", table_name="knowledge_relationships")
    op.drop_index("ix_knowledge_relationships_tenant_id", table_name="knowledge_relationships")
    op.drop_table("knowledge_relationships")

    op.drop_index("ix_knowledge_entities_project_id", table_name="knowledge_entities")
    op.drop_index("ix_knowledge_entities_tenant_id", table_name="knowledge_entities")
    op.drop_table("knowledge_entities")
