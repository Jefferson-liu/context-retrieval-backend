from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.repo_knowledge_embedding import RepoEmbeddingRunCreateRequest
from schemas.repo_knowledge_file_summary import RepoFileSummaryRunCreateRequest
from schemas.repo_knowledge_repo_full_summary import RepoFullSummaryRunCreateRequest


def test_file_summary_request_accepts_source_run_id() -> None:
    payload = RepoFileSummaryRunCreateRequest(source_run_id="run-1")
    assert payload.source_run_id == "run-1"


def test_file_summary_request_accepts_repo_run_id_alias() -> None:
    payload = RepoFileSummaryRunCreateRequest(repo_run_id="run-2")
    assert payload.source_run_id == "run-2"
    assert payload.repo_run_id == "run-2"


def test_file_summary_request_rejects_missing_run_selector() -> None:
    with pytest.raises(ValidationError):
        RepoFileSummaryRunCreateRequest()


def test_file_summary_request_rejects_conflicting_run_selectors() -> None:
    with pytest.raises(ValidationError):
        RepoFileSummaryRunCreateRequest(source_run_id="run-1", repo_run_id="run-2")


def test_embedding_request_accepts_source_file_summary_run_id() -> None:
    payload = RepoEmbeddingRunCreateRequest(source_file_summary_run_id="extract-1")
    assert payload.source_file_summary_run_id == "extract-1"


def test_embedding_request_accepts_source_run_id() -> None:
    payload = RepoEmbeddingRunCreateRequest(source_run_id="run-1")
    assert payload.source_run_id == "run-1"


def test_embedding_request_accepts_repo_run_id_alias() -> None:
    payload = RepoEmbeddingRunCreateRequest(repo_run_id="run-2")
    assert payload.source_run_id == "run-2"
    assert payload.repo_run_id == "run-2"


def test_embedding_request_rejects_missing_selectors() -> None:
    with pytest.raises(ValidationError):
        RepoEmbeddingRunCreateRequest()


def test_embedding_request_rejects_conflicting_source_and_repo_run_ids() -> None:
    with pytest.raises(ValidationError):
        RepoEmbeddingRunCreateRequest(source_run_id="run-1", repo_run_id="run-2")


def test_repo_full_summary_request_requires_file_summary_run_id() -> None:
    with pytest.raises(ValidationError):
        RepoFullSummaryRunCreateRequest()


def test_repo_full_summary_request_accepts_force_flag() -> None:
    payload = RepoFullSummaryRunCreateRequest(
        source_file_summary_run_id="file-run-1",
        force_rerepo_summary=True,
    )
    assert payload.source_file_summary_run_id == "file-run-1"
    assert payload.force_rerepo_summary is True
