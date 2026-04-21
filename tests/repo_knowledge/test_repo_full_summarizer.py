from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from services.repo_knowledge.repo_full_summarization.repo_full_summarizer import (
    RepoFullSummaryAgentTools,
    RepoFullSummarizer,
)
from services.repo_knowledge.repo_full_summarization.types import RepoFullSummaryInput
from services.repo_knowledge.summarization.react_agent_runtime import (
    AgentProtocolError,
    ReActAgentResult,
)


class _FakeFileSummaryRepo:
    def __init__(self) -> None:
        self._rows: dict[str, list[tuple[SimpleNamespace, SimpleNamespace, None]]] = {
            "file-run-a": [
                (
                    SimpleNamespace(
                        overall_summary="A",
                        file_cluster=["cluster-a"],
                        important_relationships=["dep-a"],
                        group_function=None,
                    ),
                    SimpleNamespace(id="s1", subject_path="src/a.py", language="python"),
                    None,
                ),
                (
                    SimpleNamespace(
                        overall_summary="Helpers",
                        file_cluster=["cluster-h"],
                        important_relationships=["dep-h"],
                        group_function="helpers",
                    ),
                    SimpleNamespace(id="s2", subject_path="src/utils/helpers.py", language="python"),
                    None,
                ),
            ],
            "file-run-b": [
                (
                    SimpleNamespace(
                        overall_summary="B",
                        file_cluster=["cluster-b"],
                        important_relationships=["dep-b"],
                        group_function=None,
                    ),
                    SimpleNamespace(id="s3", subject_path="other/b.py", language="python"),
                    None,
                ),
            ],
        }

    async def list_for_file_summary_all(self, *, file_summary_run_id: str):  # noqa: ANN001
        return self._rows.get(file_summary_run_id, [])


def _payload(file_summary_run_id: str) -> RepoFullSummaryInput:
    return RepoFullSummaryInput(
        source_run_id="run-1",
        source_file_summary_run_id=file_summary_run_id,
        repo_path="/tmp/repo",
        repo_address="repo-address",
        tech_stack="python",
    )


def test_return_file_summary_exact_match() -> None:
    tools = RepoFullSummaryAgentTools(
        payload=_payload("file-run-a"),
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        trace_sink=[],
    )
    result = asyncio.run(tools.return_file_summary(file_name="src/a.py"))
    assert result["resolved_subject_path"] == "src/a.py"
    assert result["overall_summary"] == "A"
    assert result["match_type"] == "exact"


def test_return_file_summary_suffix_match() -> None:
    tools = RepoFullSummaryAgentTools(
        payload=_payload("file-run-a"),
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        trace_sink=[],
    )
    result = asyncio.run(tools.return_file_summary(file_name="helpers.py"))
    assert result["resolved_subject_path"] == "src/utils/helpers.py"
    assert result["match_type"] == "suffix"


def test_return_file_summary_not_found() -> None:
    tools = RepoFullSummaryAgentTools(
        payload=_payload("file-run-a"),
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        trace_sink=[],
    )
    result = asyncio.run(tools.return_file_summary(file_name="missing.py"))
    assert result["resolved_subject_path"] is None
    assert result["error"] == "not_found"


def test_return_file_summary_is_scoped_to_file_summary_run() -> None:
    tools = RepoFullSummaryAgentTools(
        payload=_payload("file-run-b"),
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        trace_sink=[],
    )
    result = asyncio.run(tools.return_file_summary(file_name="b.py"))
    assert result["resolved_subject_path"] == "other/b.py"
    assert result["overall_summary"] == "B"


def test_repo_full_summarizer_stores_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        return ReActAgentResult(
            raw_text="# Repo\nBody",
            state={"messages": [1, 2]},
        )

    monkeypatch.setattr(
        "services.repo_knowledge.repo_full_summarization.repo_full_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFullSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=6000,
        retry_count=1,
        timeout_seconds=20,
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        max_iterations=4,
    )
    result = asyncio.run(
        summarizer.summarize(
            payload=RepoFullSummaryInput(
                source_run_id="run-1",
                source_file_summary_run_id="file-run-a",
                repo_path="/tmp/repo",
                repo_address="repo-address",
                tech_stack="python",
            )
        )
    )
    assert result.output.readme_markdown.startswith("# Repo")
    assert result.raw_output["agent"]["message_count"] == 2


def test_repo_full_summarizer_react_executes_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**kwargs):  # noqa: ANN003
        tools = kwargs["tools"]
        tool_map = {tool.name: tool for tool in tools}
        await tool_map["return_file_summary"].ainvoke({"file_name": "src/a.py"})
        return ReActAgentResult(
            raw_text="# Repo\nBody",
            state={"messages": [1]},
        )

    monkeypatch.setattr(
        "services.repo_knowledge.repo_full_summarization.repo_full_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFullSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=6000,
        retry_count=1,
        timeout_seconds=20,
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        max_iterations=4,
    )
    result = asyncio.run(
        summarizer.summarize(
            payload=RepoFullSummaryInput(
                source_run_id="run-1",
                source_file_summary_run_id="file-run-a",
                repo_path="/tmp/repo",
                repo_address="repo-address",
                tech_stack="python",
            )
        )
    )
    assert result.output.readme_markdown.startswith("# Repo")
    assert len(result.raw_output["tool_trace"]) == 1
    assert result.raw_output["tool_trace"][0]["name"] == "return_file_summary"


def test_repo_full_summarizer_protocol_error_bubbles(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        raise AgentProtocolError(code="thought_signature_missing", message="missing thought signature")

    monkeypatch.setattr(
        "services.repo_knowledge.repo_full_summarization.repo_full_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFullSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=6000,
        retry_count=1,
        timeout_seconds=20,
        subject_repo=None,
        edge_repo=None,
        file_summary_repo=_FakeFileSummaryRepo(),  # type: ignore[arg-type]
        max_iterations=4,
    )
    with pytest.raises(AgentProtocolError):
        asyncio.run(
            summarizer.summarize(
                payload=RepoFullSummaryInput(
                    source_run_id="run-1",
                    source_file_summary_run_id="file-run-a",
                    repo_path="/tmp/repo",
                    repo_address="repo-address",
                    tech_stack="python",
                )
            )
        )
