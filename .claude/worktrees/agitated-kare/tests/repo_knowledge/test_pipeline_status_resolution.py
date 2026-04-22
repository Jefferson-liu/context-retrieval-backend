from __future__ import annotations

from types import SimpleNamespace

from services.repo_knowledge.pipeline_service import _resolve_pipeline_status


def _source(status: str, error: str | None = None):
    return SimpleNamespace(status=status, error_message=error)


def _stage(status: str, error: str | None = None, groups_seen: int = 0):
    return SimpleNamespace(status=status, error_message=error, groups_seen=groups_seen)


def test_pipeline_status_during_ingestion() -> None:
    status, stage, error, stage_error = _resolve_pipeline_status(
        source_run=_source("queued"),
        file_summary_run=None,
        repo_full_summary_run=None,
        embedding_run=None,
        repo_manager_run=None,
    )
    assert status == "queued"
    assert stage == "ingestion"
    assert error is None
    assert stage_error is None


def test_pipeline_status_during_file_summary() -> None:
    status, stage, _, _ = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=None,
        repo_full_summary_run=None,
        embedding_run=None,
        repo_manager_run=None,
    )
    assert status == "in_progress"
    assert stage == "file_summary"


def test_pipeline_status_during_repo_full_summary() -> None:
    status, stage, _, _ = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=_stage("completed"),
        repo_full_summary_run=_stage("in_progress"),
        embedding_run=None,
        repo_manager_run=None,
    )
    assert status == "in_progress"
    assert stage == "repo_full_summary"


def test_pipeline_status_during_repo_manager() -> None:
    status, stage, _, _ = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=_stage("completed"),
        repo_full_summary_run=_stage("completed"),
        embedding_run=_stage("completed"),
        repo_manager_run=_stage("in_progress", groups_seen=0),
    )
    assert status == "in_progress"
    assert stage == "repo_manager"


def test_pipeline_status_during_architecture() -> None:
    status, stage, _, _ = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=_stage("completed"),
        repo_full_summary_run=_stage("completed"),
        embedding_run=_stage("completed"),
        repo_manager_run=_stage("in_progress", groups_seen=3),
    )
    assert status == "in_progress"
    assert stage == "architecture"


def test_pipeline_status_failed_stage_bubbles_error() -> None:
    status, stage, error, stage_error = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=_stage("failed", error="extract failed"),
        repo_full_summary_run=None,
        embedding_run=None,
        repo_manager_run=None,
    )
    assert status == "failed"
    assert stage == "failed"
    assert error == "extract failed"
    assert stage_error == "extract failed"


def test_pipeline_status_completed() -> None:
    status, stage, error, stage_error = _resolve_pipeline_status(
        source_run=_source("completed"),
        file_summary_run=_stage("completed"),
        repo_full_summary_run=_stage("completed"),
        embedding_run=_stage("completed"),
        repo_manager_run=_stage("completed", groups_seen=8),
    )
    assert status == "completed"
    assert stage == "completed"
    assert error is None
    assert stage_error is None
