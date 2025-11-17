"""Normalize knowledge entities and add alias mapping

Revision ID: 20251027_knowledge_entity_canonicalization
Revises: 20251026_context_entity_links
Create Date: 2025-10-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from services.knowledge.entity_normalizer import normalize_entity_name


revision = "20251027_knowledge_entity_canonicalization"
down_revision = "20251026_context_entity_links"
branch_labels = None
depends_on = None


knowledge_entities = sa.table(
    "knowledge_entities",
    sa.column("id", sa.Integer),
    sa.column("tenant_id", sa.Integer),
    sa.column("project_id", sa.Integer),
    sa.column("entity_type", sa.String),
    sa.column("name", sa.String),
    sa.column("canonical_name", sa.String),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    op.add_column(
        "knowledge_entities",
        sa.Column("canonical_name", sa.String(length=255), nullable=True),
    )

    bind = op.get_bind()
    result = bind.execute(sa.select(knowledge_entities.c.id, knowledge_entities.c.name))
    rows = result.fetchall()
    for entity_id, entity_name in rows:
        normalized = normalize_entity_name(entity_name or "")
        bind.execute(
            knowledge_entities.update()
            .where(knowledge_entities.c.id == entity_id)
            .values(canonical_name=normalized.canonical_name)
        )

    _deduplicate_entities(bind)

    op.alter_column(
        "knowledge_entities",
        "canonical_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_index(
        "ix_knowledge_entities_canonical",
        "knowledge_entities",
        ["tenant_id", "project_id", "entity_type", "canonical_name"],
        unique=True,
    )

    op.create_table(
        "knowledge_entity_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column("alias_canonical_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entity_id"], ["knowledge_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "entity_type",
            "alias_canonical_name",
            name="uq_entity_alias_canonical",
        ),
    )
    op.create_index("ix_knowledge_entity_alias_tenant", "knowledge_entity_aliases", ["tenant_id"])
    op.create_index("ix_knowledge_entity_alias_project", "knowledge_entity_aliases", ["project_id"])
    op.create_index(
        "ix_knowledge_entity_alias_canonical",
        "knowledge_entity_aliases",
        ["alias_canonical_name"],
    )

    op.execute(
        """
        INSERT INTO knowledge_entity_aliases (
            tenant_id,
            project_id,
            entity_id,
            entity_type,
            alias_name,
            alias_canonical_name,
            created_at
        )
        SELECT
            tenant_id,
            project_id,
            id,
            entity_type,
            name,
            canonical_name,
            NOW()
        FROM knowledge_entities
        """
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_entity_alias_canonical", table_name="knowledge_entity_aliases")
    op.drop_index("ix_knowledge_entity_alias_project", table_name="knowledge_entity_aliases")
    op.drop_index("ix_knowledge_entity_alias_tenant", table_name="knowledge_entity_aliases")
    op.drop_table("knowledge_entity_aliases")

    op.drop_index("ix_knowledge_entities_canonical", table_name="knowledge_entities")
    op.drop_column("knowledge_entities", "canonical_name")


def _deduplicate_entities(bind) -> None:
    bind.execute(
        text(
        """
        WITH ranked AS (
            SELECT
                id,
                tenant_id,
                project_id,
                entity_type,
                canonical_name,
                MIN(id) OVER (
                    PARTITION BY tenant_id, project_id, entity_type, canonical_name
                ) AS keep_id
            FROM knowledge_entities
        )
        UPDATE knowledge_relationships kr
        SET source_entity_id = ranked.keep_id
        FROM ranked
        WHERE kr.source_entity_id = ranked.id
          AND ranked.keep_id <> ranked.id;
        """
    ))
    bind.execute(
        text(
        """
        WITH ranked AS (
            SELECT
                id,
                tenant_id,
                project_id,
                entity_type,
                canonical_name,
                MIN(id) OVER (
                    PARTITION BY tenant_id, project_id, entity_type, canonical_name
                ) AS keep_id
            FROM knowledge_entities
        )
        UPDATE knowledge_relationships kr
        SET target_entity_id = ranked.keep_id
        FROM ranked
        WHERE kr.target_entity_id = ranked.id
          AND ranked.keep_id <> ranked.id;
        """
    ))
    bind.execute(
        text(
        """
        DELETE FROM knowledge_entities ke
        USING (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, project_id, entity_type, canonical_name
                        ORDER BY id
                    ) AS rn
                FROM knowledge_entities
            ) sub
            WHERE sub.rn > 1
        ) dup
        WHERE ke.id = dup.id;
        """
    ))
