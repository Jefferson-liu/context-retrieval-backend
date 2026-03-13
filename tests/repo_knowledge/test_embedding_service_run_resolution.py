from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from schemas.repo_knowledge_embedding import RepoEmbeddingRunCreateRequest
from services.repo_knowledge.embedding_service import RepoEmbeddingError, RepoKnowledgeEmbeddingService


def _build_service() -> RepoKnowledgeEmbeddingService:
    service = RepoKnowledgeEmbeddingService(session=None, tenant_id="tenant-1", user_id="user-1")  # type: ignore[arg-type]
    return service


def test_create_embedding_run_resolves_latest_completed_file_summary_for_source_run() -> None:
    service = _build_service()
    source_run = SimpleNamespace(id="run-1", status="completed")
    file_summary_run = SimpleNamespace(id="extract-1", status="completed", source_run_id="run-1")
    created_run = SimpleNamespace(
        id="embed-1",
        status="queued",
        queued_at=datetime.now(timezone.utc),
        source_run_id="run-1",
        source_file_summary_run_id="extract-1",
    )

    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=source_run))
    service.file_summary_run_repo = SimpleNamespace(
        get_scoped=AsyncMock(return_value=None),
        latest_completed_for_source=AsyncMock(return_value=file_summary_run),
    )
    service.embedding_run_repo = SimpleNamespace(
        find_completed_by_fingerprint=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created_run),
    )
    service.embedding_repo = SimpleNamespace()

    payload = RepoEmbeddingRunCreateRequest(source_run_id="run-1")
    run = asyncio.run(service.create_embedding_run(payload))

    assert run.id == "embed-1"
    service.file_summary_run_repo.latest_completed_for_source.assert_awaited_once_with(
        source_run_id="run-1",
        tenant_id="tenant-1",
        user_id="user-1",
    )
    service.embedding_run_repo.create.assert_awaited_once()


def test_create_embedding_run_rejects_mismatched_source_and_file_summary_runs() -> None:
    service = _build_service()
    source_run = SimpleNamespace(id="run-1", status="completed")
    file_summary_run = SimpleNamespace(id="extract-9", status="completed", source_run_id="run-2")

    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=source_run))
    service.file_summary_run_repo = SimpleNamespace(
        get_scoped=AsyncMock(return_value=file_summary_run),
        latest_completed_for_source=AsyncMock(return_value=None),
    )
    service.embedding_run_repo = SimpleNamespace(
        find_completed_by_fingerprint=AsyncMock(return_value=None),
        create=AsyncMock(),
    )
    service.embedding_repo = SimpleNamespace()

    payload = RepoEmbeddingRunCreateRequest(
        source_file_summary_run_id="extract-9",
        source_run_id="run-1",
    )
    with pytest.raises(RepoEmbeddingError, match="does not belong"):
        asyncio.run(service.create_embedding_run(payload))
