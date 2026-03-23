from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from services.repo_knowledge.summarization.file_summarizer import (
    RepoFileSummarizer,
    _extract_json,
    _extract_summary_payload,
)
from services.repo_knowledge.summarization.react_agent_runtime import (
    AgentProtocolError,
    ReActAgentResult,
)
from services.repo_knowledge.summarization.types import SummaryInput


def _payload(*, repo_path: str = "/tmp/repo", subject_path: str = "x.py") -> SummaryInput:
    return SummaryInput(
        source_run_id="run-1",
        subject_id="subject-1",
        subject_path=subject_path,
        language="python",
        parse_status="success",
        repo_path=repo_path,
        repo_address="repo-address",
        tech_stack="python",
        chunk_texts=["print('hello')"],
    )


def test_repo_file_summarizer_empty_payload_is_deterministic() -> None:
    summarizer = RepoFileSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=200,
        map_chunk_chars=100,
        retry_count=1,
        timeout_seconds=10,
    )
    result = asyncio.run(
        summarizer.summarize(
            payload=SummaryInput(
                source_run_id="run-1",
                subject_id="subject-1",
                subject_path="empty.py",
                language="python",
                parse_status="success",
                repo_path="/tmp/repo",
                repo_address="repo-address",
                tech_stack="python",
                chunk_texts=[],
                    )
        )
    )
    assert result.output.overall_summary == "Empty file with no content to summarize."
    assert result.raw_output["mode"] == "deterministic_empty"


def test_repo_file_summarizer_direct_path_non_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        return ReActAgentResult(
            raw_text='{"file_cluster":["a.py"],"overall_summary":"sum","important_relationships":["b.py"],"group_function":null}',
            state={"messages": [1, 2, 3]},
        )

    monkeypatch.setattr(
        "services.repo_knowledge.summarization.file_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFileSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=40,
        map_chunk_chars=20,
        retry_count=1,
        timeout_seconds=10,
    )
    result = asyncio.run(summarizer.summarize(payload=_payload()))
    assert result.output.overall_summary == "sum"
    assert result.raw_output["mode"] == "agent"
    assert result.raw_output["agent"]["message_count"] == 3


def test_extract_json_handles_markdown_fence() -> None:
    payload = _extract_json(
        "```json\n"
        '{"file_cluster":[],"overall_summary":"ok","important_relationships":[],"group_function":null}'
        "\n```"
    )
    assert payload["overall_summary"] == "ok"


def test_extract_summary_payload_accepts_tagged_output() -> None:
    payload = _extract_summary_payload(
        "[File_cluster_begin]\n- service/a.py\n[File_cluster_end]\n"
        "[Overall_Summary_start]\nCore summary\n[Overall_Summary_end]\n"
        "[Important_Relationships_start]\n- service/b.py\n[Important_Relationships_end]\n"
        "[Group_Function_start]\nImplements a flow.\n[Group_Function_end]"
    )
    assert payload["overall_summary"] == "Core summary"
    assert payload["file_cluster"] == ["service/a.py"]
    assert payload["important_relationships"] == ["service/b.py"]
    assert payload["group_function"] == "Implements a flow."


def test_repo_file_summarizer_malformed_output_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        return ReActAgentResult(raw_text="not-json-output", state={"messages": []})

    monkeypatch.setattr(
        "services.repo_knowledge.summarization.file_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFileSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=200,
        map_chunk_chars=100,
        retry_count=1,
        timeout_seconds=10,
    )
    with pytest.raises(Exception):
        asyncio.run(summarizer.summarize(payload=_payload()))


def test_repo_file_summarizer_react_executes_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "a.py").write_text("print('hello')\n", encoding="utf-8")

    async def _fake_invoke(**kwargs):  # noqa: ANN003
        tools = kwargs["tools"]
        tool_map = {tool.name: tool for tool in tools}
        await tool_map["return_file_code"].ainvoke({"use_path": "a.py", "start_line": 1, "max_lines": 20})
        return ReActAgentResult(
            raw_text='{"file_cluster":["a.py"],"overall_summary":"sum","important_relationships":[],"group_function":null}',
            state={"messages": [1]},
        )

    monkeypatch.setattr(
        "services.repo_knowledge.summarization.file_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFileSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=200,
        map_chunk_chars=100,
        retry_count=1,
        timeout_seconds=10,
        max_iterations=4,
    )

    result = asyncio.run(summarizer.summarize(payload=_payload(repo_path=str(repo_root), subject_path="a.py")))
    assert result.output.overall_summary == "sum"
    assert len(result.raw_output["tool_trace"]) == 1
    assert result.raw_output["tool_trace"][0]["name"] == "return_file_code"


def test_repo_file_summarizer_recursion_limit_falls_back_to_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the agent hits the recursion limit, a direct synthesis call is made."""

    class _GraphRecursionError(Exception):
        pass

    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        raise _GraphRecursionError(
            "Recursion limit of 10 reached without hitting a stop condition."
        )

    class _FakeChatModel:
        async def ainvoke(self, messages):  # noqa: ANN001
            from types import SimpleNamespace

            return SimpleNamespace(
                content=(
                    "[File_cluster_begin]\n[File_cluster_end]\n"
                    "[Overall_Summary_start]\nSynthesis fallback summary\n[Overall_Summary_end]\n"
                    "[Important_Relationships_start]\n[Important_Relationships_end]\n"
                    "[Group_Function_start]\n[Group_Function_end]"
                ),
                type="ai",
                usage_metadata={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            )

    monkeypatch.setattr(
        "services.repo_knowledge.summarization.file_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFileSummarizer(
        chat_model=_FakeChatModel(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=200,
        map_chunk_chars=100,
        retry_count=1,
        timeout_seconds=10,
        max_iterations=4,
    )
    result = asyncio.run(summarizer.summarize(payload=_payload()))
    assert result.output.overall_summary == "Synthesis fallback summary"
    assert result.raw_output["agent"].get("synthesis_fallback") is True


def test_repo_file_summarizer_protocol_error_bubbles(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_invoke(**_kwargs):  # noqa: ANN003
        raise AgentProtocolError(code="thought_signature_missing", message="missing thought signature")

    monkeypatch.setattr(
        "services.repo_knowledge.summarization.file_summarizer.invoke_react_agent",
        _fake_invoke,
    )
    summarizer = RepoFileSummarizer(
        chat_model=object(),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=200,
        map_chunk_chars=100,
        retry_count=1,
        timeout_seconds=10,
        max_iterations=4,
    )
    with pytest.raises(AgentProtocolError):
        asyncio.run(summarizer.summarize(payload=_payload()))
