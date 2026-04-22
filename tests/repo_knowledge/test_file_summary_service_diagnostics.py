from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.repo_knowledge.file_summary_service import RepoKnowledgeFileSummaryService


def _build_service() -> RepoKnowledgeFileSummaryService:
    return RepoKnowledgeFileSummaryService(session=None, tenant_id="tenant-1", user_id="user-1")  # type: ignore[arg-type]


def test_list_diagnostics_returns_none_for_unknown_run() -> None:
    service = _build_service()
    service.file_summary_run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=None))
    service.summary_diagnostic_repo = SimpleNamespace(list_for_file_summary=AsyncMock())

    run, rows = asyncio.run(
        service.list_diagnostics(
            file_summary_run_id="missing",
            limit=100,
            offset=0,
            severity=None,
            subject_path_prefix=None,
        )
    )

    assert run is None
    assert rows is None
    service.summary_diagnostic_repo.list_for_file_summary.assert_not_awaited()


def test_list_diagnostics_returns_rows_for_scoped_run() -> None:
    service = _build_service()
    run_record = SimpleNamespace(id="file-run-1", source_run_id="source-run-1")
    diagnostic_row = (
        SimpleNamespace(
            file_summary_run_id="file-run-1",
            subject_id="subj-1",
            severity="error",
            message="summary_file_summary_failed",
            details={"diagnostic_code": "summary_failed"},
            created_at=datetime.now(timezone.utc),
        ),
        SimpleNamespace(subject_path="services/example.py"),
    )

    service.file_summary_run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=run_record))
    service.summary_diagnostic_repo = SimpleNamespace(list_for_file_summary=AsyncMock(return_value=[diagnostic_row]))

    run, rows = asyncio.run(
        service.list_diagnostics(
            file_summary_run_id="file-run-1",
            limit=25,
            offset=5,
            severity="error",
            subject_path_prefix="services/",
        )
    )

    assert run is run_record
    assert rows == [diagnostic_row]
    service.summary_diagnostic_repo.list_for_file_summary.assert_awaited_once_with(
        file_summary_run_id="file-run-1",
        limit=25,
        offset=5,
        severity="error",
        subject_path_prefix="services/",
    )
