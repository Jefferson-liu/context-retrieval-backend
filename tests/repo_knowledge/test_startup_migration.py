from __future__ import annotations

import asyncio
from types import SimpleNamespace

import infrastructure.database as database


class _FakeConn:
    def __init__(self, dialect_name: str = "postgresql") -> None:
        self.dialect = SimpleNamespace(name=dialect_name)
        self.statements: list[str] = []

    async def execute(self, statement, params=None):  # noqa: ANN001
        self.statements.append(str(statement))
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
            first=lambda: None,
        )


def test_rename_table_if_needed_executes_when_old_exists_and_new_missing(monkeypatch) -> None:
    conn = _FakeConn()

    async def fake_table_exists(_conn, *, table_name: str):  # noqa: ANN001
        return table_name == "repo_extraction_runs"

    monkeypatch.setattr(database, "_table_exists", fake_table_exists)
    asyncio.run(
        database._rename_table_if_needed(
            conn,
            old_name="repo_extraction_runs",
            new_name="repo_file_summary_runs",
        )
    )
    joined = "\n".join(conn.statements)
    assert "ALTER TABLE" in joined
    assert "repo_extraction_runs" in joined
    assert "repo_file_summary_runs" in joined


def test_rename_column_if_needed_is_idempotent_when_new_exists(monkeypatch) -> None:
    conn = _FakeConn()

    async def fake_table_exists(_conn, *, table_name: str):  # noqa: ANN001
        return table_name == "repo_embeddings"

    async def fake_column_exists(_conn, *, table_name: str, column_name: str):  # noqa: ANN001
        if table_name != "repo_embeddings":
            return False
        return column_name in {"source_extraction_run_id", "source_file_summary_run_id"}

    monkeypatch.setattr(database, "_table_exists", fake_table_exists)
    monkeypatch.setattr(database, "_column_exists", fake_column_exists)
    asyncio.run(
        database._rename_column_if_needed(
            conn,
            table_name="repo_embeddings",
            old_name="source_extraction_run_id",
            new_name="source_file_summary_run_id",
        )
    )
    assert conn.statements == []


def test_startup_migration_skips_for_non_postgres() -> None:
    conn = _FakeConn(dialect_name="sqlite")
    asyncio.run(database._run_repo_knowledge_startup_migration(conn))
    assert conn.statements == []
