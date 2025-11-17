"""Ensure timestamp columns use timezone-aware types.

Revision ID: 20251028_timestamp_tz_alignment
Revises: 20251027_knowledge_entity_canonicalization
Create Date: 2025-10-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251028_timestamp_tz_alignment"
down_revision = "20251027_knowledge_entity_canonicalization"
branch_labels = None
depends_on = None


TIMESTAMPTZ_COLUMNS: dict[str, tuple[str, ...]] = {
    "tenants": ("created_at",),
    "projects": ("created_at",),
    "user_project_roles": ("created_at",),
    "document_summaries": ("created_at", "updated_at"),
    "project_summaries": ("refreshed_at", "created_at", "updated_at"),
    "knowledge_entities": ("created_at", "updated_at"),
    "knowledge_relationships": ("created_at", "updated_at"),
    "knowledge_relationship_metadata": ("created_at", "updated_at"),
    "knowledge_entity_aliases": ("created_at",),
    "context_entities": ("created_at", "updated_at"),
    "context_entity_documents": ("created_at",),
    "context_entity_threads": ("created_at",),
    "text_threads": ("thread_started_at", "thread_closed_at", "created_at", "updated_at"),
    "text_thread_messages": ("sent_at", "created_at", "updated_at"),
    "user_products": ("created_at", "updated_at"),
}


def upgrade() -> None:
    for table, columns in TIMESTAMPTZ_COLUMNS.items():
        for column in columns:
            _ensure_timestamptz(table, column)


def downgrade() -> None:
    for table, columns in TIMESTAMPTZ_COLUMNS.items():
        for column in columns:
            _ensure_timestamp_without_tz(table, column)


def _ensure_timestamptz(table: str, column: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{column}'
                      AND data_type = 'timestamp without time zone'
                ) THEN
                    EXECUTE 'ALTER TABLE {table}
                             ALTER COLUMN {column}
                             TYPE TIMESTAMP WITH TIME ZONE
                             USING {column} AT TIME ZONE ''UTC'' ';
                END IF;
            END
            $$;
            """
        )
    )


def _ensure_timestamp_without_tz(table: str, column: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{column}'
                      AND data_type = 'timestamp with time zone'
                ) THEN
                    EXECUTE 'ALTER TABLE {table}
                             ALTER COLUMN {column}
                             TYPE TIMESTAMP WITHOUT TIME ZONE
                             USING timezone(''UTC'', {column}) ';
                END IF;
            END
            $$;
            """
        )
    )
