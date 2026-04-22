from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.repo_knowledge.mcp_tools_service import (
    RepoKnowledgeMcpService,
    RepoKnowledgeMcpServiceError,
    _insert_path,
    _new_dir_node,
    _render_tree,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_service() -> Any:
    return RepoKnowledgeMcpService(session=None, tenant_id="tenant-1", user_id="user-1")  # type: ignore[arg-type]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_run(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="run-1", status="completed", source_type="git",
        repo_address="https://github.com/org/repo", source_locator=None,
        files_seen=10, files_ingested=9, files_skipped=1, chunks_written=100,
        parse_success_count=9, parse_failed_count=0,
        edge_count_file=5, edge_count_symbol=3,
        error_message=None,
        queued_at=_now(), started_at=_now(), finished_at=_now(),
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def _make_file_summary_run(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="fsr-1", source_run_id="run-1", status="completed",
        prompt_version="v1", files_seen=9, files_summarized=9, files_failed=0,
        error_message=None, queued_at=_now(), started_at=_now(), finished_at=_now(),
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def _make_embedding_run(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="emb-1", source_run_id="run-1", source_file_summary_run_id="fsr-1",
        status="completed", subjects_seen=9, subjects_embedded=9, subjects_failed=0,
        error_message=None, queued_at=_now(), started_at=_now(), finished_at=_now(),
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def _make_repo_manager_run(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="rmr-1", source_run_id="run-1", source_file_summary_run_id="fsr-1",
        status="completed", prompt_version="v1",
        groups_seen=3, groups_summarized=3, groups_failed=0, members_seen=9,
        error_message=None,
        architecture_overview="An overview",
        merged_mermaid_diagram="graph TD\nA-->B",
        queued_at=_now(), started_at=_now(), finished_at=_now(),
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def _make_full_summary_run(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="fsr-full-1", source_run_id="run-1", status="completed",
        error_message=None, queued_at=_now(), started_at=_now(), finished_at=_now(),
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def _make_snapshot_row(subject_path: str = "src/main.py"):
    subject = SimpleNamespace(
        id="subj-1", subject_path=subject_path, subject_type="file", language="python",
    )
    snapshot = SimpleNamespace(
        run_id="run-1", size_bytes=1000, line_count=50,
        content_hash="abc123", ingest_status="ingested",
        parse_status="success", skip_reason=None, parse_error=None, chunk_count=5,
    )
    return snapshot, subject


def _make_edge_row():
    edge = SimpleNamespace(
        run_id="run-1", from_subject_id="subj-1", to_subject_id="subj-2",
        edge_type="imports", line=1, column=0, evidence=None, is_external_target=False,
    )
    from_subject = SimpleNamespace(subject_type="file", subject_path="src/a.py")
    to_subject = SimpleNamespace(subject_type="file", subject_path="src/b.py")
    return edge, from_subject, to_subject


def _make_summary_row(subject_path: str = "src/main.py"):
    summary = SimpleNamespace(
        overall_summary="does stuff", file_cluster=["cluster-a"],
        important_relationships=["imports b"], group_function="service",
        updated_at=_now(),
    )
    subject = SimpleNamespace(id="subj-1", subject_path=subject_path, language="python")
    snapshot = SimpleNamespace(parse_status="success")
    return summary, subject, snapshot


def _make_embedding_row(subject_path: str = "src/main.py"):
    embedding = SimpleNamespace(
        embedding_run_id="emb-1", source_run_id="run-1",
        source_file_summary_run_id="fsr-1", kind="file_summary",
        text_hash="abc", embedding_dims=1536, updated_at=_now(),
    )
    subject = SimpleNamespace(id="subj-1", subject_path=subject_path, language="python")
    snapshot = SimpleNamespace()
    return embedding, subject, snapshot


def _make_group_row():
    group = SimpleNamespace(
        group_id="grp-1", group_key="services/auth", group_label="Auth Service",
        layer_hint="service", member_count=3, dependency_neighbor_count=2,
        is_infrastructure_seed=False,
    )
    summary = SimpleNamespace(
        name="Auth Service", overall_summary="handles auth", business_purpose="auth",
        responsibilities=["login", "logout"], tags=["auth"],
        representative_subject_ids=["subj-1"],
        is_infrastructure=False, confidence=0.95, updated_at=_now(),
    )
    return group, summary


def _make_member_row():
    member = SimpleNamespace(rank=1, is_representative=True, membership_reason="key file")
    subject = SimpleNamespace(id="subj-1", subject_path="src/auth.py", language="python")
    return member, subject


# ---------------------------------------------------------------------------
# get_run_overview
# ---------------------------------------------------------------------------


def test_get_run_overview_returns_all_latest_sub_runs() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=_make_file_summary_run()))
    service.embedding_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=_make_embedding_run()))
    service.group_summary_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=_make_repo_manager_run()))

    result = asyncio.run(service.get_run_overview(run_id="run-1"))

    assert result["run"]["run_id"] == "run-1"
    assert result["latest_file_summary_run"]["file_summary_run_id"] == "fsr-1"
    assert result["latest_embedding_run"]["embedding_run_id"] == "emb-1"
    assert result["latest_repo_manager_run"]["repo_manager_run_id"] == "rmr-1"


def test_get_run_overview_returns_none_for_missing_sub_runs() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=None))
    service.embedding_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=None))
    service.group_summary_run_repo = SimpleNamespace(latest_completed_for_source=AsyncMock(return_value=None))

    result = asyncio.run(service.get_run_overview(run_id="run-1"))

    assert result["latest_file_summary_run"] is None
    assert result["latest_embedding_run"] is None
    assert result["latest_repo_manager_run"] is None


def test_get_run_overview_raises_when_run_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=None))

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Run not found"):
        asyncio.run(service.get_run_overview(run_id="missing"))


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


def test_list_runs_returns_scoped_runs() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(list_scoped=AsyncMock(return_value=[
        _make_run(id="run-2", repo_address="https://github.com/org/repo-two"),
        _make_run(id="run-1", repo_address="https://github.com/org/repo-one"),
    ]))

    result = asyncio.run(service.list_runs(limit=20, offset=0, status="completed"))

    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["status"] == "completed"
    assert [item["run_id"] for item in result["items"]] == ["run-2", "run-1"]
    assert result["items"][0]["repo_address"] == "https://github.com/org/repo-two"


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------


def test_list_files_returns_paginated_items() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.snapshot_repo = SimpleNamespace(list_for_run=AsyncMock(return_value=[_make_snapshot_row("src/main.py")]))

    result = asyncio.run(service.list_files(run_id="run-1", limit=10, offset=0, ingest_status=None))

    assert result["run_id"] == "run-1"
    assert len(result["items"]) == 1
    assert result["items"][0]["subject_path"] == "src/main.py"
    assert result["items"][0]["ingest_status"] == "ingested"


def test_list_files_raises_when_run_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=None))

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Run not found"):
        asyncio.run(service.list_files(run_id="missing", limit=10, offset=0, ingest_status=None))


# ---------------------------------------------------------------------------
# list_edges
# ---------------------------------------------------------------------------


def test_list_edges_returns_paginated_items() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.edge_repo = SimpleNamespace(list_for_run=AsyncMock(return_value=[_make_edge_row()]))

    result = asyncio.run(service.list_edges(
        run_id="run-1", limit=10, offset=0,
        edge_type=None, from_subject_type=None, to_subject_type=None, language=None,
    ))

    assert result["run_id"] == "run-1"
    assert len(result["items"]) == 1
    assert result["items"][0]["edge_type"] == "imports"
    assert result["items"][0]["from_subject_path"] == "src/a.py"
    assert result["items"][0]["to_subject_path"] == "src/b.py"


def test_list_edges_raises_when_run_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=None))

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Run not found"):
        asyncio.run(service.list_edges(
            run_id="missing", limit=10, offset=0,
            edge_type=None, from_subject_type=None, to_subject_type=None, language=None,
        ))


# ---------------------------------------------------------------------------
# list_summaries
# ---------------------------------------------------------------------------


def test_list_summaries_uses_latest_file_summary_run_when_none_given() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_file_summary_run()),
    )
    service.summary_repo = SimpleNamespace(list_for_file_summary=AsyncMock(return_value=[_make_summary_row()]))

    result = asyncio.run(service.list_summaries(
        run_id="run-1", file_summary_run_id=None,
        limit=10, offset=0, language=None, parse_status=None, subject_path_prefix=None,
    ))

    service.file_summary_run_repo.latest_completed_for_source.assert_awaited_once()
    assert result["file_summary_run_id"] == "fsr-1"
    assert len(result["items"]) == 1


def test_list_summaries_returns_empty_when_no_completed_file_summary_run() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=None),
    )

    result = asyncio.run(service.list_summaries(
        run_id="run-1", file_summary_run_id=None,
        limit=10, offset=0, language=None, parse_status=None, subject_path_prefix=None,
    ))

    assert result["file_summary_run_id"] is None
    assert result["items"] == []


def test_list_summaries_raises_when_explicit_run_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=None))

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Extraction run not found"):
        asyncio.run(service.list_summaries(
            run_id="run-1", file_summary_run_id="fsr-missing",
            limit=10, offset=0, language=None, parse_status=None, subject_path_prefix=None,
        ))


def test_list_summaries_raises_when_explicit_run_belongs_to_different_source() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run(id="run-1")))
    service.file_summary_run_repo = SimpleNamespace(
        get_scoped=AsyncMock(return_value=_make_file_summary_run(source_run_id="run-2")),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="does not belong"):
        asyncio.run(service.list_summaries(
            run_id="run-1", file_summary_run_id="fsr-1",
            limit=10, offset=0, language=None, parse_status=None, subject_path_prefix=None,
        ))


# ---------------------------------------------------------------------------
# read_summary_file
# ---------------------------------------------------------------------------


def test_read_summary_file_returns_matching_item() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_file_summary_run()),
    )
    service.summary_repo = SimpleNamespace(
        list_for_file_summary=AsyncMock(return_value=[_make_summary_row("src/auth.py")]),
    )

    result = asyncio.run(service.read_summary_file(
        run_id="run-1", subject_path="src/auth.py", file_summary_run_id=None,
    ))

    assert result["item"]["subject_path"] == "src/auth.py"


def test_read_summary_file_raises_when_path_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.file_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_file_summary_run()),
    )
    service.summary_repo = SimpleNamespace(
        list_for_file_summary=AsyncMock(return_value=[_make_summary_row("src/other.py")]),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Summary not found"):
        asyncio.run(service.read_summary_file(
            run_id="run-1", subject_path="src/auth.py", file_summary_run_id=None,
        ))


# ---------------------------------------------------------------------------
# list_embedding_items
# ---------------------------------------------------------------------------


def test_list_embedding_items_uses_latest_embedding_run_when_none_given() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.embedding_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_embedding_run()),
    )
    service.embedding_repo = SimpleNamespace(
        list_for_embedding_run=AsyncMock(return_value=[_make_embedding_row()]),
    )

    result = asyncio.run(service.list_embedding_items(
        run_id="run-1", embedding_run_id=None,
        limit=10, offset=0, kind=None, language=None, subject_path_prefix=None,
    ))

    service.embedding_run_repo.latest_completed_for_source.assert_awaited_once()
    assert result["embedding_run_id"] == "emb-1"
    assert len(result["items"]) == 1


def test_list_embedding_items_returns_empty_when_no_completed_embedding_run() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.embedding_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=None),
    )

    result = asyncio.run(service.list_embedding_items(
        run_id="run-1", embedding_run_id=None,
        limit=10, offset=0, kind=None, language=None, subject_path_prefix=None,
    ))

    assert result["embedding_run_id"] is None
    assert result["items"] == []


def test_list_embedding_items_raises_when_explicit_run_belongs_to_different_source() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run(id="run-1")))
    service.embedding_run_repo = SimpleNamespace(
        get_scoped=AsyncMock(return_value=_make_embedding_run(source_run_id="run-2")),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="does not belong"):
        asyncio.run(service.list_embedding_items(
            run_id="run-1", embedding_run_id="emb-1",
            limit=10, offset=0, kind=None, language=None, subject_path_prefix=None,
        ))


# ---------------------------------------------------------------------------
# list_repo_manager_segments
# ---------------------------------------------------------------------------


def test_list_repo_manager_segments_returns_groups_without_members() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_repo_manager_run()),
    )
    service.summary_group_repo = SimpleNamespace(
        list_groups_for_run=AsyncMock(return_value=[_make_group_row()]),
    )

    result = asyncio.run(service.list_repo_manager_segments(
        run_id="run-1", repo_manager_run_id=None,
        limit=10, offset=0, layer_hint=None, is_infrastructure=None,
        group_key_prefix=None, include_members=False,
    ))

    assert result["repo_manager_run_id"] == "rmr-1"
    assert len(result["items"]) == 1
    assert result["items"][0]["group_key"] == "services/auth"
    assert result["items"][0]["members"] == []


def test_list_repo_manager_segments_fetches_members_when_requested() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_repo_manager_run()),
    )
    service.summary_group_repo = SimpleNamespace(
        list_groups_for_run=AsyncMock(return_value=[_make_group_row()]),
        list_members_for_groups=AsyncMock(return_value={"grp-1": [_make_member_row()]}),
    )

    result = asyncio.run(service.list_repo_manager_segments(
        run_id="run-1", repo_manager_run_id=None,
        limit=10, offset=0, layer_hint=None, is_infrastructure=None,
        group_key_prefix=None, include_members=True,
    ))

    service.summary_group_repo.list_members_for_groups.assert_awaited_once()
    assert len(result["items"][0]["members"]) == 1
    assert result["items"][0]["members"][0]["subject_path"] == "src/auth.py"


def test_list_repo_manager_segments_returns_empty_when_no_completed_run() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=None),
    )

    result = asyncio.run(service.list_repo_manager_segments(
        run_id="run-1", repo_manager_run_id=None,
        limit=10, offset=0, layer_hint=None, is_infrastructure=None,
        group_key_prefix=None, include_members=False,
    ))

    assert result["repo_manager_run_id"] is None
    assert result["items"] == []


# ---------------------------------------------------------------------------
# read_repo_manager_segment
# ---------------------------------------------------------------------------


def test_read_repo_manager_segment_raises_when_neither_id_nor_key_given() -> None:
    service = _build_service()
    # check fires before any DB call — no repos need to be mocked
    with pytest.raises(RepoKnowledgeMcpServiceError, match="Either group_id or group_key"):
        asyncio.run(service.read_repo_manager_segment(
            run_id="run-1", group_id=None, group_key=None, repo_manager_run_id=None,
        ))


def test_read_repo_manager_segment_raises_when_no_completed_run() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=None),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="No completed repo-manager run"):
        asyncio.run(service.read_repo_manager_segment(
            run_id="run-1", group_id="grp-1", group_key=None, repo_manager_run_id=None,
        ))


def test_read_repo_manager_segment_raises_when_group_not_found() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_repo_manager_run()),
    )
    service.summary_group_repo = SimpleNamespace(
        get_group_with_summary=AsyncMock(return_value=None),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="Group summary not found"):
        asyncio.run(service.read_repo_manager_segment(
            run_id="run-1", group_id="grp-missing", group_key=None, repo_manager_run_id=None,
        ))


# ---------------------------------------------------------------------------
# get_repo_architecture
# ---------------------------------------------------------------------------


def test_get_repo_architecture_returns_overview_and_diagram() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_repo_manager_run()),
    )

    result = asyncio.run(service.get_repo_architecture(run_id="run-1", repo_manager_run_id=None))

    assert result["architecture_overview"] == "An overview"
    assert result["merged_mermaid_diagram"] == "graph TD\nA-->B"
    assert result["repo_manager_run_id"] == "rmr-1"


def test_get_repo_architecture_raises_when_no_completed_run() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=None),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="No completed repo-manager run"):
        asyncio.run(service.get_repo_architecture(run_id="run-1", repo_manager_run_id=None))


def test_get_repo_architecture_raises_when_artifact_fields_empty() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.group_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(
            return_value=_make_repo_manager_run(architecture_overview=None, merged_mermaid_diagram=None),
        ),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="no architecture artifact"):
        asyncio.run(service.get_repo_architecture(run_id="run-1", repo_manager_run_id=None))


# ---------------------------------------------------------------------------
# get_repo_full_summary
# ---------------------------------------------------------------------------


def test_get_repo_full_summary_returns_readme_markdown() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.full_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_full_summary_run()),
    )
    service.full_summary_repo = SimpleNamespace(
        get_for_run=AsyncMock(return_value=SimpleNamespace(readme_markdown="# My Repo\n\nHello world")),
    )

    result = asyncio.run(service.get_repo_full_summary(run_id="run-1", repo_full_summary_run_id=None))

    assert result["readme_markdown"] == "# My Repo\n\nHello world"
    assert result["repo_full_summary_run_id"] == "fsr-full-1"


def test_get_repo_full_summary_raises_when_explicit_run_belongs_to_different_source() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run(id="run-1")))
    service.full_summary_run_repo = SimpleNamespace(
        get_scoped=AsyncMock(return_value=_make_full_summary_run(source_run_id="run-2")),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="does not belong"):
        asyncio.run(service.get_repo_full_summary(
            run_id="run-1", repo_full_summary_run_id="fsr-full-1",
        ))


def test_get_repo_full_summary_raises_when_artifact_missing() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.full_summary_run_repo = SimpleNamespace(
        latest_completed_for_source=AsyncMock(return_value=_make_full_summary_run()),
    )
    service.full_summary_repo = SimpleNamespace(get_for_run=AsyncMock(return_value=None))

    with pytest.raises(RepoKnowledgeMcpServiceError, match="artifact not found"):
        asyncio.run(service.get_repo_full_summary(run_id="run-1", repo_full_summary_run_id=None))


# ---------------------------------------------------------------------------
# Code-reading tool helpers
# ---------------------------------------------------------------------------


def test_get_file_content_returns_bounded_window_with_pagination_metadata() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.subject_repo = SimpleNamespace(
        find_file_by_path=AsyncMock(return_value=SimpleNamespace(id="subj-1")),
    )
    service.chunk_repo = SimpleNamespace(
        list_for_subject=AsyncMock(return_value=[SimpleNamespace(content="line1\nline2\nline3\nline4\n")]),
    )

    result = asyncio.run(service.get_file_content(
        run_id="run-1",
        subject_path="src/main.py",
        start_line=1,
        end_line=None,
        max_lines=2,
    ))

    assert result["content"] == "line1\nline2"
    assert result["start_line"] == 1
    assert result["end_line"] == 2
    assert result["total_lines"] == 4
    assert result["truncated"] is True
    assert result["next_start_line"] == 3


def test_get_file_content_raises_when_start_line_is_out_of_range() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.subject_repo = SimpleNamespace(
        find_file_by_path=AsyncMock(return_value=SimpleNamespace(id="subj-1")),
    )
    service.chunk_repo = SimpleNamespace(
        list_for_subject=AsyncMock(return_value=[SimpleNamespace(content="line1\nline2\n")]),
    )

    with pytest.raises(RepoKnowledgeMcpServiceError, match="beyond end of file"):
        asyncio.run(service.get_file_content(
            run_id="run-1",
            subject_path="src/main.py",
            start_line=99,
            end_line=None,
            max_lines=50,
        ))


def test_grep_code_caps_files_and_truncates_long_lines() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    rows = [
        (
            SimpleNamespace(subject_path="src/a.py"),
            SimpleNamespace(chunk_index=0, content="alpha\nneedle-" + ("x" * 100) + "\nomega\n"),
        ),
        (
            SimpleNamespace(subject_path="src/b.py"),
            SimpleNamespace(chunk_index=0, content="needle-in-second-file\n"),
        ),
    ]
    service.session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
    )

    result = asyncio.run(service.grep_code(
        run_id="run-1",
        pattern="needle",
        path_prefix=None,
        ignore_case=True,
        context_lines=0,
        max_matches=10,
        max_files=1,
        max_line_length=20,
    ))

    assert result["truncated"] is True
    assert result["returned_file_count"] == 1
    assert result["matches"][0]["path"] == "src/a.py"
    match_line = result["matches"][0]["matches"][0]["context"][0]["text"]
    assert len(match_line) == 20
    assert match_line.endswith("...")


def test_grep_code_merges_nearby_matches_into_one_window() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    rows = [
        (
            SimpleNamespace(subject_path="src/a.py"),
            SimpleNamespace(
                chunk_index=0,
                content="zero\nneedle-one\nbridge\nneedle-two\nlast\n",
            ),
        ),
    ]
    service.session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
    )

    result = asyncio.run(service.grep_code(
        run_id="run-1",
        pattern="needle",
        path_prefix=None,
        ignore_case=True,
        context_lines=1,
        max_matches=10,
        max_files=5,
        max_line_length=80,
    ))

    assert result["returned_match_count"] == 2
    assert result["returned_file_count"] == 1
    assert result["matches"][0]["match_count"] == 2
    assert result["matches"][0]["snippet_count"] == 1
    assert result["matches"][0]["matches"][0]["start_line"] == 1
    assert result["matches"][0]["matches"][0]["end_line"] == 5
    assert result["matches"][0]["matches"][0]["match_lines"] == [2, 4]


def test_glob_files_returns_paginated_matches() -> None:
    service = _build_service()
    service.run_repo = SimpleNamespace(get_scoped=AsyncMock(return_value=_make_run()))
    service.snapshot_repo = SimpleNamespace(
        list_for_run_all=AsyncMock(return_value=[
            (SimpleNamespace(), SimpleNamespace(subject_path="src/a.py", subject_type="file")),
            (SimpleNamespace(), SimpleNamespace(subject_path="src/b.py", subject_type="file")),
            (SimpleNamespace(), SimpleNamespace(subject_path="src/c.py", subject_type="file")),
            (SimpleNamespace(), SimpleNamespace(subject_path="src/not_a_file", subject_type="directory")),
        ]),
    )

    result = asyncio.run(service.glob_files(
        run_id="run-1",
        pattern="src/*.py",
        limit=1,
        offset=1,
    ))

    assert result["total"] == 3
    assert result["files"] == ["src/b.py"]
    assert result["truncated"] is True


# ---------------------------------------------------------------------------
# Pure tree helpers
# ---------------------------------------------------------------------------


def test_insert_path_builds_nested_structure() -> None:
    root = _new_dir_node(name="/", path="")
    _insert_path(root=root, path="src/services/auth.py")
    _insert_path(root=root, path="src/main.py")

    assert "src" in root["children"]
    src = root["children"]["src"]
    assert src["type"] == "dir"
    assert "services" in src["children"]
    assert src["children"]["services"]["children"]["auth.py"]["type"] == "file"
    assert src["children"]["main.py"]["type"] == "file"


def test_render_tree_truncates_at_max_depth() -> None:
    root = _new_dir_node(name="/", path="")
    _insert_path(root=root, path="a/b/c/deep.py")

    tree = _render_tree(node=root, depth=0, max_depth=2, include_file_counts=False)

    # root(0) -> a(1) -> b(2, truncated) — "c" should never appear
    a_node = tree["children"][0]
    assert a_node["name"] == "a"
    b_node = a_node["children"][0]
    assert b_node["name"] == "b"
    assert b_node.get("truncated") is True
    assert "children" not in b_node


def test_render_tree_sorts_dirs_before_files_alphabetically() -> None:
    root = _new_dir_node(name="/", path="")
    _insert_path(root=root, path="zebra.py")
    _insert_path(root=root, path="alpha.py")
    _insert_path(root=root, path="zoo/keeper.py")
    _insert_path(root=root, path="abc/worker.py")

    tree = _render_tree(node=root, depth=0, max_depth=5, include_file_counts=False)

    children = tree["children"]
    assert children[0]["type"] == "dir"
    assert children[1]["type"] == "dir"
    assert children[0]["name"] == "abc"
    assert children[1]["name"] == "zoo"
    assert children[2]["name"] == "alpha.py"
    assert children[3]["name"] == "zebra.py"
