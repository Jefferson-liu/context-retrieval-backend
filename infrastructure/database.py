from __future__ import annotations

import logging
import re
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings


logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for ORM models."""


def _build_engine():
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False, future=True)


engine = _build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if they do not exist."""
    # Import models so they are registered on the Base metadata before create_all.
    import infrastructure.models  # noqa: F401
    async with engine.begin() as conn:
        await _run_repo_knowledge_startup_migration(conn)
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("Unable to ensure pgvector extension: %s", exc)
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency to provide an async DB session."""
    async with SessionLocal() as session:
        yield session


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _qi(identifier: str) -> str:
    """Return a safely-quoted SQL identifier for static migration statements."""

    if not _IDENT_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'


async def _run_repo_knowledge_startup_migration(conn) -> None:  # noqa: ANN001
    """Run idempotent startup migration for file-summary/repo-full-summary split."""

    if conn.dialect.name != "postgresql":
        logger.info("Skipping repo-knowledge startup migration for non-PostgreSQL dialect=%s", conn.dialect.name)
        return

    logger.info("Running repo-knowledge startup migration checks")

    await _rename_table_if_needed(conn, old_name="repo_extraction_runs", new_name="repo_file_summary_runs")
    await _rename_table_if_needed(conn, old_name="repo_summaries", new_name="repo_file_summaries")
    await _rename_table_if_needed(
        conn,
        old_name="repo_summary_diagnostics",
        new_name="repo_file_summary_diagnostics",
    )

    # File-summary table internal column rename.
    await _rename_column_if_needed(
        conn,
        table_name="repo_file_summaries",
        old_name="extraction_run_id",
        new_name="file_summary_run_id",
    )
    await _rename_column_if_needed(
        conn,
        table_name="repo_file_summary_diagnostics",
        old_name="extraction_run_id",
        new_name="file_summary_run_id",
    )

    # Downstream dependent run references (use both old and new table names for idempotency).
    for table_name in (
        "repo_embedding_runs",
        "repo_embeddings",
        "repo_group_summary_runs",
        "repo_summary_groups",
        "repo_group_summaries",
        "repo_manager_runs",
        "repo_manager_segments",
        "repo_manager_segment_summaries",
    ):
        await _rename_column_if_needed(
            conn,
            table_name=table_name,
            old_name="source_extraction_run_id",
            new_name="source_file_summary_run_id",
        )

    # Safety copy path when both legacy and new tables exist.
    await _copy_legacy_file_summary_rows_if_needed(conn)

    # Architecture columns on the old table names (for pre-rename DBs).
    await _add_column_if_needed(conn, table_name="repo_group_summary_runs", column_name="architecture_overview", column_sql="TEXT")
    await _add_column_if_needed(conn, table_name="repo_group_summary_runs", column_name="merged_mermaid_diagram", column_sql="TEXT")
    await _add_column_if_needed(conn, table_name="repo_group_summary_runs", column_name="merge_raw_output", column_sql="JSON")
    await _add_column_if_needed(conn, table_name="repo_group_summaries", column_name="mermaid_diagram", column_sql="TEXT")

    # Rename group_summary tables to repo_manager.
    await _rename_table_if_needed(conn, old_name="repo_group_summary_runs", new_name="repo_manager_runs")
    await _rename_table_if_needed(conn, old_name="repo_summary_groups", new_name="repo_manager_segments")
    await _rename_table_if_needed(conn, old_name="repo_summary_group_members", new_name="repo_manager_segment_members")
    await _rename_table_if_needed(conn, old_name="repo_group_summaries", new_name="repo_manager_segment_summaries")
    await _rename_table_if_needed(conn, old_name="repo_group_summary_diagnostics", new_name="repo_manager_diagnostics")

    # Rename group_summary_run_id columns to repo_manager_run_id on the new tables.
    for table_name in (
        "repo_manager_segments",
        "repo_manager_segment_members",
        "repo_manager_segment_summaries",
        "repo_manager_diagnostics",
    ):
        await _rename_column_if_needed(
            conn,
            table_name=table_name,
            old_name="group_summary_run_id",
            new_name="repo_manager_run_id",
        )

    # Architecture columns on the new table names (for fresh DBs that skipped old names).
    await _add_column_if_needed(conn, table_name="repo_manager_runs", column_name="architecture_overview", column_sql="TEXT")
    await _add_column_if_needed(conn, table_name="repo_manager_runs", column_name="merged_mermaid_diagram", column_sql="TEXT")
    await _add_column_if_needed(conn, table_name="repo_manager_runs", column_name="merge_raw_output", column_sql="JSON")
    await _add_column_if_needed(conn, table_name="repo_manager_segment_summaries", column_name="mermaid_diagram", column_sql="TEXT")

    # Drop overly-strict composite FK on diagnostics — diagnostics can be run-level
    # (e.g. architecture merge errors) and don't always reference a segment.
    for fk_name in (
        "fk_repo_manager_diagnostics_segment",
        "fk_repo_group_summary_diagnostics_group",
    ):
        await _drop_constraint_if_exists(conn, table_name="repo_manager_diagnostics", constraint_name=fk_name)


async def _table_exists(conn, *, table_name: str) -> bool:  # noqa: ANN001
    result = await conn.execute(
        text("SELECT to_regclass(:qualified_name)"),
        {"qualified_name": f"public.{table_name}"},
    )
    return result.scalar_one_or_none() is not None


async def _drop_constraint_if_exists(conn, *, table_name: str, constraint_name: str) -> None:  # noqa: ANN001
    if not await _table_exists(conn, table_name=table_name):
        return
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND constraint_name = :constraint_name
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    )
    if result.scalar_one_or_none() is None:
        return
    logger.info("Startup migration: dropping constraint %s on %s", constraint_name, table_name)
    await conn.execute(text(f"ALTER TABLE {_qi(table_name)} DROP CONSTRAINT {_qi(constraint_name)}"))


async def _column_exists(conn, *, table_name: str, column_name: str) -> bool:  # noqa: ANN001
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.first() is not None


async def _rename_table_if_needed(conn, *, old_name: str, new_name: str) -> None:  # noqa: ANN001
    has_old = await _table_exists(conn, table_name=old_name)
    has_new = await _table_exists(conn, table_name=new_name)
    if not has_old or has_new:
        return
    logger.info("Startup migration: renaming table %s -> %s", old_name, new_name)
    await conn.execute(text(f"ALTER TABLE {_qi(old_name)} RENAME TO {_qi(new_name)}"))


async def _rename_column_if_needed(conn, *, table_name: str, old_name: str, new_name: str) -> None:  # noqa: ANN001
    if not await _table_exists(conn, table_name=table_name):
        return
    has_old = await _column_exists(conn, table_name=table_name, column_name=old_name)
    has_new = await _column_exists(conn, table_name=table_name, column_name=new_name)
    if not has_old or has_new:
        return
    logger.info("Startup migration: renaming %s.%s -> %s", table_name, old_name, new_name)
    await conn.execute(text(f"ALTER TABLE {_qi(table_name)} RENAME COLUMN {_qi(old_name)} TO {_qi(new_name)}"))


async def _add_column_if_needed(conn, *, table_name: str, column_name: str, column_sql: str) -> None:  # noqa: ANN001
    if not await _table_exists(conn, table_name=table_name):
        return
    if await _column_exists(conn, table_name=table_name, column_name=column_name):
        return
    logger.info("Startup migration: adding %s.%s", table_name, column_name)
    await conn.execute(text(f"ALTER TABLE {_qi(table_name)} ADD COLUMN {_qi(column_name)} {column_sql}"))


async def _copy_legacy_file_summary_rows_if_needed(conn) -> None:  # noqa: ANN001
    legacy_runs = await _table_exists(conn, table_name="repo_extraction_runs")
    legacy_summaries = await _table_exists(conn, table_name="repo_summaries")
    legacy_diags = await _table_exists(conn, table_name="repo_summary_diagnostics")
    current_runs = await _table_exists(conn, table_name="repo_file_summary_runs")
    current_summaries = await _table_exists(conn, table_name="repo_file_summaries")
    current_diags = await _table_exists(conn, table_name="repo_file_summary_diagnostics")

    if legacy_runs and current_runs:
        logger.warning("Both legacy and file-summary run tables exist; copying missing run rows")
        await conn.execute(
            text(
                """
                INSERT INTO repo_file_summary_runs (
                    id, source_run_id, tenant_id, user_id, status, error_message,
                    model_provider, model_name, prompt_version, run_fingerprint,
                    files_seen, files_summarized, files_failed,
                    queued_at, started_at, finished_at
                )
                SELECT
                    l.id, l.source_run_id, l.tenant_id, l.user_id, l.status, l.error_message,
                    l.model_provider, l.model_name, l.prompt_version, l.run_fingerprint,
                    l.files_seen, l.files_summarized, l.files_failed,
                    l.queued_at, l.started_at, l.finished_at
                FROM repo_extraction_runs l
                WHERE NOT EXISTS (
                    SELECT 1 FROM repo_file_summary_runs n WHERE n.id = l.id
                )
                """
            )
        )

    if legacy_summaries and current_summaries:
        logger.warning("Both legacy and file-summary artifact tables exist; copying missing summary rows")
        await conn.execute(
            text(
                """
                INSERT INTO repo_file_summaries (
                    file_summary_run_id, subject_id, source_run_id, overall_summary,
                    file_cluster, important_relationships, group_function,
                    raw_output, input_hash, updated_at
                )
                SELECT
                    l.extraction_run_id, l.subject_id, l.source_run_id, l.overall_summary,
                    l.file_cluster, l.important_relationships, l.group_function,
                    l.raw_output, l.input_hash, l.updated_at
                FROM repo_summaries l
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM repo_file_summaries n
                    WHERE n.file_summary_run_id = l.extraction_run_id
                      AND n.subject_id = l.subject_id
                )
                """
            )
        )

    if legacy_diags and current_diags:
        logger.warning("Both legacy and file-summary diagnostic tables exist; copying missing diagnostic rows")
        await conn.execute(
            text(
                """
                INSERT INTO repo_file_summary_diagnostics (
                    id, file_summary_run_id, subject_id, severity, message, details, created_at
                )
                SELECT
                    l.id, l.extraction_run_id, l.subject_id, l.severity, l.message, l.details, l.created_at
                FROM repo_summary_diagnostics l
                WHERE NOT EXISTS (
                    SELECT 1 FROM repo_file_summary_diagnostics n WHERE n.id = l.id
                )
                """
            )
        )
