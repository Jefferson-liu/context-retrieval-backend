from __future__ import annotations

from schemas.repo_knowledge import RepoRunCreateRequest
from schemas.repo_knowledge_pipeline import RepoPipelineRunCreateRequest
from services.repo_knowledge.ingestion_service import _should_mark_run_skipped_duplicate


def test_repo_run_request_accepts_force_reingest() -> None:
    payload = RepoRunCreateRequest(
        source_path="/tmp/repo",
        force_reingest=True,
    )
    assert payload.force_reingest is True


def test_pipeline_request_accepts_force_reingest() -> None:
    payload = RepoPipelineRunCreateRequest(
        source_path="/tmp/repo",
        force_reingest=True,
    )
    assert payload.force_reingest is True


def test_force_reingest_bypasses_duplicate_marking() -> None:
    assert _should_mark_run_skipped_duplicate(duplicate_found=True, force_reingest=True) is False


def test_duplicate_still_marks_skipped_when_not_forced() -> None:
    assert _should_mark_run_skipped_duplicate(duplicate_found=True, force_reingest=False) is True

