from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from services.repo_knowledge.prompt_loader import load_prompt, render_prompt
from services.repo_knowledge.summarization.file_summarizer import (
    FileSummaryAgentTools,
    SummaryInput,
    _format_directory_result,
    _format_file_code_result,
    _format_reference_graph_result,
)
from services.repo_knowledge.summarization.react_agent_runtime import (
    invoke_react_agent,
    log_react_agent_dependency_versions,
)
from services.repo_knowledge.repo_full_summarization.types import (
    RepoFullSummaryInput,
    RepoFullSummaryOutput,
)

if TYPE_CHECKING:
    from infrastructure.repositories.repo_edge_repository import RepoEdgeRepository
    from infrastructure.repositories.repo_file_summary_repository import RepoFileSummaryRepository
    from infrastructure.repositories.repo_subject_repository import RepoSubjectRepository

REPO_FULL_SUMMARY_SYSTEM_PROMPT = load_prompt("repo_full_summary_system")
REPO_FULL_SUMMARY_MAX_TOOL_PREVIEW_CHARS = 1200
logger = logging.getLogger(__name__)


class ReturnDirectoryArgs(BaseModel):
    """Arguments for the return_directory tool."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str
    depth: int = Field(default=4, ge=0, le=12)
    cursor: int = Field(default=0, ge=0)
    page_size: int = Field(default=400, ge=1, le=2000)


class ReturnFileCodeArgs(BaseModel):
    """Arguments for the return_file_code tool."""

    model_config = ConfigDict(extra="forbid")

    use_path: str
    start_line: int = Field(default=1, ge=1)
    max_lines: int = Field(default=250, ge=1, le=1000)


class ReturnReferenceGraphArgs(BaseModel):
    """Arguments for the return_reference_graph tool."""

    model_config = ConfigDict(extra="forbid")

    type: str
    input_subject: str
    limit_each_direction: int = Field(default=25, ge=1, le=200)


class ReturnFileSummaryArgs(BaseModel):
    """Arguments for the return_file_summary tool."""

    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(..., min_length=1)


@dataclass(slots=True)
class RepoFullSummaryResult:
    """Structured repo full-summary output plus raw model response payload."""

    output: RepoFullSummaryOutput
    raw_output: dict
    input_hash: str


class RepoFullSummaryAgentTools:
    """LangChain tools exposed to the repo full-summary ReAct agent."""

    def __init__(
        self,
        *,
        payload: RepoFullSummaryInput,
        subject_repo: RepoSubjectRepository | None,
        edge_repo: RepoEdgeRepository | None,
        file_summary_repo: RepoFileSummaryRepository,
        trace_sink: list[dict],
    ) -> None:
        self.payload = payload
        self.file_summary_repo = file_summary_repo
        self.trace_sink = trace_sink
        self._shared_tools = FileSummaryAgentTools(
            payload=SummaryInput(
                source_run_id=payload.source_run_id,
                subject_id="repo_root",
                subject_path=".",
                language=payload.tech_stack,
                parse_status="success",
                repo_path=payload.repo_path,
                repo_address=payload.repo_address,
                tech_stack=payload.tech_stack,
            ),
            subject_repo=subject_repo,
            edge_repo=edge_repo,
            trace_sink=[],
        )
        self._summary_index: dict[str, dict[str, Any]] | None = None

    def as_langchain_tools(self) -> list[StructuredTool]:
        """Build LangChain tool objects with exact prompt-compatible names."""

        return [
            StructuredTool.from_function(
                coroutine=self._return_directory_tool,
                name="return_directory",
                description=(
                    "Retrieve the project directory structure for a given path with bounded depth and pagination."
                ),
                args_schema=ReturnDirectoryArgs,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                coroutine=self._return_file_code_tool,
                name="return_file_code",
                description=(
                    "Read the content of a code file. The use_path should be a relative path "
                    "with the correct file extension (e.g. .py for Python, .c/.h for C). "
                    "Supports line-based paging via start_line and max_lines."
                ),
                args_schema=ReturnFileCodeArgs,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                coroutine=self._return_reference_graph_tool,
                name="return_reference_graph",
                description=(
                    "Retrieve the reference and reverse-reference graph for a file, class, or function. "
                    "The type can be 'file', 'class', or 'func'."
                ),
                args_schema=ReturnReferenceGraphArgs,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                coroutine=self._return_file_summary_tool,
                name="return_file_summary",
                description=(
                    "Read the summary for a specific file by name. "
                    "Matches by exact path or suffix."
                ),
                args_schema=ReturnFileSummaryArgs,
                handle_tool_error=True,
            ),
        ]

    async def _return_directory_tool(
        self,
        repo_path: str,
        depth: int = 4,
        cursor: int = 0,
        page_size: int = 400,
    ) -> str:
        result = await self._shared_tools.return_directory(
            repo_path=repo_path,
            depth=depth,
            cursor=cursor,
            page_size=page_size,
        )
        _record_tool_trace(
            self.trace_sink,
            name="return_directory",
            arguments={
                "repo_path": repo_path,
                "depth": depth,
                "cursor": cursor,
                "page_size": page_size,
            },
            result=result,
        )
        return _format_directory_result(result)

    async def _return_file_code_tool(
        self,
        use_path: str,
        start_line: int = 1,
        max_lines: int = 250,
    ) -> str:
        result = await self._shared_tools.return_file_code(
            use_path=use_path,
            start_line=start_line,
            max_lines=max_lines,
        )
        _record_tool_trace(
            self.trace_sink,
            name="return_file_code",
            arguments={
                "use_path": use_path,
                "start_line": start_line,
                "max_lines": max_lines,
            },
            result=result,
        )
        return _format_file_code_result(result)

    async def _return_reference_graph_tool(
        self,
        type: str,
        input_subject: str,
        limit_each_direction: int = 25,
    ) -> str:
        result = await self._shared_tools.return_reference_graph(
            type=type,
            input_subject=input_subject,
            limit_each_direction=limit_each_direction,
        )
        _record_tool_trace(
            self.trace_sink,
            name="return_reference_graph",
            arguments={
                "type": type,
                "input_subject": input_subject,
                "limit_each_direction": limit_each_direction,
            },
            result=result,
        )
        return _format_reference_graph_result(result)

    async def _return_file_summary_tool(self, file_name: str) -> str:
        result = await self.return_file_summary(file_name=file_name)
        _record_tool_trace(
            self.trace_sink,
            name="return_file_summary",
            arguments={"file_name": file_name},
            result=result,
        )
        return _format_file_summary_result(result)

    async def return_file_summary(self, *, file_name: str) -> dict:
        """Return one file summary payload by exact path or deterministic suffix match."""

        requested = file_name.strip().replace("\\", "/").lstrip("./")
        if not requested:
            return {
                "requested_file_name": file_name,
                "resolved_subject_path": None,
                "error": "invalid_file_name",
            }

        index = await self._load_summary_index()
        if not index:
            return {
                "requested_file_name": file_name,
                "resolved_subject_path": None,
                "error": "no_file_summaries_available",
            }

        entry = index.get(requested)
        match_type = "exact"
        if entry is None:
            suffix_matches = [path for path in index if path.endswith(requested)]
            if not suffix_matches and "/" not in requested:
                suffix_matches = [path for path in index if path.split("/")[-1] == requested]
            if not suffix_matches:
                return {
                    "requested_file_name": file_name,
                    "resolved_subject_path": None,
                    "error": "not_found",
                }
            suffix_matches.sort(key=lambda item: (len(item), item))
            chosen = suffix_matches[0]
            entry = index[chosen]
            match_type = "suffix"

        return {
            "requested_file_name": file_name,
            "resolved_subject_path": entry["subject_path"],
            "match_type": match_type,
            "subject_id": entry["subject_id"],
            "language": entry["language"],
            "overall_summary": entry["overall_summary"],
            "file_cluster": entry["file_cluster"],
            "important_relationships": entry["important_relationships"],
            "group_function": entry["group_function"],
        }

    async def _load_summary_index(self) -> dict[str, dict[str, Any]]:
        if self._summary_index is not None:
            return self._summary_index

        rows = await self.file_summary_repo.list_for_file_summary_all(
            file_summary_run_id=self.payload.source_file_summary_run_id
        )
        index: dict[str, dict[str, Any]] = {}
        for summary, subject, _snapshot in rows:
            normalized_path = subject.subject_path.replace("\\", "/").lstrip("./")
            if normalized_path in index:
                continue
            index[normalized_path] = {
                "subject_id": subject.id,
                "subject_path": subject.subject_path,
                "language": subject.language,
                "overall_summary": summary.overall_summary,
                "file_cluster": list(summary.file_cluster or []),
                "important_relationships": list(summary.important_relationships or []),
                "group_function": summary.group_function,
            }
        self._summary_index = index
        return index


class RepoFullSummarizer:
    """LangGraph ReAct repo README summarizer with strict output normalization."""

    def __init__(
        self,
        *,
        chat_model: BaseChatModel,
        prompt_version: str,
        max_input_chars: int,
        retry_count: int,
        timeout_seconds: int,
        subject_repo: RepoSubjectRepository | None,
        edge_repo: RepoEdgeRepository | None,
        file_summary_repo: RepoFileSummaryRepository,
        max_iterations: int = 10,
    ) -> None:
        self.chat_model = chat_model
        self.prompt_version = prompt_version
        self.max_input_chars = max(4000, max_input_chars)
        self.retry_count = max(1, retry_count)
        self.timeout_seconds = max(5, timeout_seconds)
        self.max_iterations = max(1, max_iterations)
        self.subject_repo = subject_repo
        self.edge_repo = edge_repo
        self.file_summary_repo = file_summary_repo
        log_react_agent_dependency_versions(logger)

    async def summarize(self, *, payload: RepoFullSummaryInput) -> RepoFullSummaryResult:
        material = [
            payload.source_run_id,
            payload.source_file_summary_run_id,
            payload.repo_path,
            payload.repo_address,
            payload.tech_stack,
            self.prompt_version,
        ]
        input_hash = sha256("\n".join(material).encode("utf-8")).hexdigest()

        user_prompt = render_prompt(
            "repo_full_summary_user",
            prompt_version=self.prompt_version,
            tech=(payload.tech_stack or "unknown"),
            repo_path=payload.repo_path,
        )

        last_error: Exception | None = None
        for _ in range(self.retry_count):
            tool_trace: list[dict] = []
            try:
                output, raw_text, agent_meta = await self._invoke_agent(
                    payload=payload,
                    user_prompt=user_prompt,
                    tool_trace=tool_trace,
                )
                return RepoFullSummaryResult(
                    output=output,
                    raw_output={
                        "mode": "agent",
                        "raw_text": raw_text,
                        "tool_trace": tool_trace,
                        "agent": agent_meta,
                    },
                    input_hash=input_hash,
                )
            except Exception as exc:  # pragma: no cover - runtime model/tool errors
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _invoke_agent(
        self,
        *,
        payload: RepoFullSummaryInput,
        user_prompt: str,
        tool_trace: list[dict],
    ) -> tuple[RepoFullSummaryOutput, str, dict[str, int]]:
        tools = RepoFullSummaryAgentTools(
            payload=payload,
            subject_repo=self.subject_repo,
            edge_repo=self.edge_repo,
            file_summary_repo=self.file_summary_repo,
            trace_sink=tool_trace,
        ).as_langchain_tools()
        agent_result = await invoke_react_agent(
            chat_model=self.chat_model,
            tools=tools,
            system_prompt=REPO_FULL_SUMMARY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            timeout_seconds=self.timeout_seconds,
            max_iterations=self.max_iterations,
        )
        output = RepoFullSummaryOutput.model_validate(_extract_readme_payload(agent_result.raw_text))
        return output, agent_result.raw_text, {"message_count": _message_count(agent_result.state)}


def _format_file_summary_result(result: dict) -> str:
    """Format file summary as compact text for LLM consumption."""

    if "error" in result:
        return f"[file_summary: {result['requested_file_name']} | error: {result['error']}]"
    lines = [f"[file_summary: {result['resolved_subject_path']} | {result['match_type']} | {result.get('language', 'unknown')}]"]
    lines.append(result["overall_summary"])
    cluster = result.get("file_cluster", [])
    if cluster:
        lines.append("[cluster]")
        for item in cluster:
            lines.append(f"- {item}")
    relationships = result.get("important_relationships", [])
    if relationships:
        lines.append("[relationships]")
        for item in relationships:
            lines.append(f"- {item}")
    gf = result.get("group_function")
    if gf:
        lines.append(f"[group_function]\n{gf}")
    return "\n".join(lines)


def _record_tool_trace(
    trace_sink: list[dict],
    *,
    name: str,
    arguments: dict[str, Any],
    result: dict,
) -> None:
    preview = json.dumps(result, ensure_ascii=True)
    if len(preview) > REPO_FULL_SUMMARY_MAX_TOOL_PREVIEW_CHARS:
        preview = f"{preview[:REPO_FULL_SUMMARY_MAX_TOOL_PREVIEW_CHARS]}..."
    trace_item: dict[str, Any] = {
        "name": name,
        "arguments": arguments,
        "result_preview": preview,
    }
    resolved_subject_path = result.get("resolved_subject_path")
    if isinstance(resolved_subject_path, str):
        trace_item["resolved_subject_path"] = resolved_subject_path
    trace_sink.append(trace_item)


def _extract_readme_payload(raw: str) -> dict[str, str]:
    readme = _extract_between_markers(
        raw,
        start_marker="【markdown_start】",
        end_marker="【markdown_end】",
    )
    if readme is None:
        # Tolerate ASCII fallback markers for occasional model variance.
        readme = _extract_between_markers(
            raw,
            start_marker="[markdown_start]",
            end_marker="[markdown_end]",
        )
    if readme is None:
        raise ValueError("Model output missing markdown_start/markdown_end markers")
    markdown = readme.strip()
    if not markdown:
        raise ValueError("README markdown output is empty")
    return {"readme_markdown": markdown}


def _extract_between_markers(raw: str, *, start_marker: str, end_marker: str) -> str | None:
    start = raw.find(start_marker)
    if start < 0:
        return None
    content_start = start + len(start_marker)
    end = raw.find(end_marker, content_start)
    if end < 0 or end <= content_start:
        return None
    return raw[content_start:end]


def _truncate_text(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[:max_chars]


def _message_count(state: dict[str, Any]) -> int:
    messages = state.get("messages")
    if isinstance(messages, list):
        return len(messages)
    return 0
