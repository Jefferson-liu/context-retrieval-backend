from __future__ import annotations

import logging
import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from services.repo_knowledge.path_input_normalization import coerce_local_source_path
from services.repo_knowledge.prompt_loader import load_prompt, render_prompt
from services.repo_knowledge.summarization.react_agent_runtime import (
    AgentProtocolError,
    extract_full_trace_from_state,
    invoke_react_agent,
    log_react_agent_dependency_versions,
    response_to_text,
)
from services.repo_knowledge.summarization.types import SummaryInput, SummaryOutput

if TYPE_CHECKING:
    from infrastructure.repositories.repo_edge_repository import RepoEdgeRepository
    from infrastructure.repositories.repo_subject_repository import RepoSubjectRepository

logger = logging.getLogger(__name__)

FILE_SUMMARY_SYSTEM_PROMPT = load_prompt("file_summary_system")
FILE_SUMMARY_MAX_SOURCE_SNIPPET_CHARS = 12000
FILE_SUMMARY_MAX_TOOL_PREVIEW_CHARS = 1200

_SYNTHESIS_FALLBACK_INSTRUCTION = (
    "You have run out of tool call budget. Produce your summary now using only "
    "the code provided above. Do not reference files you have not inspected — "
    "leave the Important_Relationships and Group_Function sections empty if you "
    "are uncertain. Focus on what you can directly observe from the provided code."
)


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


@dataclass(slots=True)
class SummaryResult:
    """Structured summary output plus raw model response payload."""

    output: SummaryOutput
    raw_output: dict
    input_hash: str
    usage_trace: dict | None = None


class FileSummaryAgentTools:
    """LangChain tools exposed to the file-summary ReAct agent."""

    def __init__(
        self,
        *,
        payload: SummaryInput,
        subject_repo: RepoSubjectRepository | None,
        edge_repo: RepoEdgeRepository | None,
        trace_sink: list[dict],
    ) -> None:
        self.payload = payload
        self.subject_repo = subject_repo
        self.edge_repo = edge_repo
        self.trace_sink = trace_sink
        self.repo_root = _normalize_repo_root(payload.repo_path)
        self.repo_address = (payload.repo_address or "").strip()
        self._file_index: list[str] | None = None

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
        ]

    async def _return_directory_tool(
        self,
        repo_path: str,
        depth: int = 4,
        cursor: int = 0,
        page_size: int = 400,
    ) -> str:
        result = await self.return_directory(
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
        result = await self.return_file_code(
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
        result = await self.return_reference_graph(
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

    async def return_directory(
        self,
        *,
        repo_path: str,
        depth: int = 4,
        cursor: int = 0,
        page_size: int = 400,
    ) -> dict:
        """Return paginated directory entries within the scoped repository root."""

        try:
            root = self._resolve_repo_directory(repo_path)
        except (ValueError, OSError) as exc:
            return {
                "repo_path": repo_path,
                "error": str(exc),
                "total_entries": 0,
                "entries": [],
                "has_more": False,
                "next_cursor": None,
            }
        base_depth = len(root.relative_to(self.repo_root).parts)
        entries: list[dict[str, str]] = []

        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            rel_dir = current.relative_to(self.repo_root)
            current_depth = len(rel_dir.parts) - base_depth
            if current_depth >= depth:
                dirnames[:] = []

            for dirname in sorted(dirnames):
                entry_path = (rel_dir / dirname).as_posix()
                entries.append({"path": entry_path, "type": "dir"})
            for filename in sorted(filenames):
                entry_path = (rel_dir / filename).as_posix()
                entries.append({"path": entry_path, "type": "file"})

        entries.sort(key=lambda item: (item["path"], item["type"]))
        page = entries[cursor : cursor + page_size]
        next_cursor = cursor + len(page)
        has_more = next_cursor < len(entries)

        return {
            "repo_path": root.relative_to(self.repo_root).as_posix() or ".",
            "depth": depth,
            "cursor": cursor,
            "page_size": page_size,
            "total_entries": len(entries),
            "entries": page,
            "has_more": has_more,
            "next_cursor": next_cursor if has_more else None,
        }

    async def return_file_code(
        self,
        *,
        use_path: str,
        start_line: int = 1,
        max_lines: int = 250,
    ) -> dict:
        """Return paginated code lines for one repository file."""

        try:
            target = self._resolve_repo_file(use_path)
        except (ValueError, OSError) as exc:
            return {
                "use_path": use_path,
                "resolved_path": None,
                "error": str(exc),
                "start_line": start_line,
                "end_line": start_line - 1,
                "total_lines": 0,
                "has_more": False,
                "next_start_line": None,
                "content": "",
            }
        text = _read_text_safely(target)
        lines = text.splitlines()
        total_lines = len(lines)

        first_line = max(1, start_line)
        if total_lines == 0 or first_line > total_lines:
            return {
                "use_path": target.relative_to(self.repo_root).as_posix(),
                "resolved_path": target.relative_to(self.repo_root).as_posix(),
                "start_line": first_line,
                "end_line": first_line - 1,
                "total_lines": total_lines,
                "has_more": False,
                "next_start_line": None,
                "content": "",
            }

        last_line = min(total_lines, first_line + max(1, max_lines) - 1)
        content = "\n".join(lines[first_line - 1 : last_line])
        has_more = last_line < total_lines
        return {
            "use_path": use_path,
            "resolved_path": target.relative_to(self.repo_root).as_posix(),
            "start_line": first_line,
            "end_line": last_line,
            "total_lines": total_lines,
            "has_more": has_more,
            "next_start_line": (last_line + 1) if has_more else None,
            "content": content,
        }

    async def return_reference_graph(
        self,
        *,
        type: str,
        input_subject: str,
        limit_each_direction: int = 25,
    ) -> dict:
        """Return incoming/outgoing references for one file/class/function subject."""

        requested_type = type.strip().lower()
        if requested_type not in {"file", "class", "func"}:
            return {
                "error": f"Unsupported type '{type}'. Expected one of: file, class, func",
                "type": requested_type,
                "input_subject": input_subject,
                "incoming": [],
                "outgoing": [],
            }

        if not self.repo_address:
            return {
                "error": "repo_address is unavailable for graph lookup",
                "type": requested_type,
                "input_subject": input_subject,
                "incoming": [],
                "outgoing": [],
            }
        if self.subject_repo is None or self.edge_repo is None:
            return {
                "error": "reference graph tool is unavailable in this execution context",
                "type": requested_type,
                "input_subject": input_subject,
                "incoming": [],
                "outgoing": [],
            }

        subject = await self._resolve_subject_record(
            requested_type=requested_type,
            input_subject=input_subject,
        )
        if subject is None:
            return {
                "type": requested_type,
                "input_subject": input_subject,
                "resolved_subject": None,
                "incoming": [],
                "outgoing": [],
            }

        rows = await self.edge_repo.list_neighbors_for_subject(
            run_id=self.payload.source_run_id,
            subject_id=subject.id,
            limit_each_direction=limit_each_direction,
        )
        incoming = [row for row in rows if row["direction"] == "incoming"]
        outgoing = [row for row in rows if row["direction"] == "outgoing"]
        return {
            "type": requested_type,
            "input_subject": input_subject,
            "resolved_subject": {
                "id": subject.id,
                "subject_path": subject.subject_path,
                "subject_type": subject.subject_type,
                "symbol_name": subject.symbol_name,
                "symbol_qualname": subject.symbol_qualname,
            },
            "incoming": incoming,
            "outgoing": outgoing,
        }

    async def _resolve_subject_record(
        self,
        *,
        requested_type: str,
        input_subject: str,
    ) -> Any | None:
        if self.subject_repo is None:
            return None

        if requested_type == "file":
            path_hint = input_subject.strip().replace("\\", "/")
            normalized_hint = path_hint.lstrip("./")
            subject = await self.subject_repo.find_file_by_path(
                repo_address=self.repo_address,
                subject_path=normalized_hint,
            )
            if subject is not None:
                return subject
            try:
                resolved = self._resolve_repo_file(path_hint)
            except Exception:
                return None
            return await self.subject_repo.find_file_by_path(
                repo_address=self.repo_address,
                subject_path=resolved.relative_to(self.repo_root).as_posix(),
            )

        expected_subject_type = "class" if requested_type == "class" else "func"
        subject = await self.subject_repo.find_symbol_by_qualname(
            repo_address=self.repo_address,
            symbol_qualname=input_subject.strip(),
        )
        if subject is not None and subject.subject_type == expected_subject_type:
            return subject

        symbol_name = input_subject.strip().split(".")[-1]
        by_name = await self.subject_repo.find_symbol_by_name(
            repo_address=self.repo_address,
            symbol_name=symbol_name,
        )
        if by_name is not None and by_name.subject_type == expected_subject_type:
            return by_name
        return None

    def _resolve_repo_directory(self, repo_path: str) -> Path:
        root = self.repo_root
        if not repo_path or repo_path.strip() in {"", "."}:
            return root

        raw = coerce_local_source_path(repo_path.strip())
        candidate = Path(raw)
        if candidate.is_absolute():
            resolved = candidate.expanduser().resolve()
        else:
            resolved = (root / candidate).expanduser().resolve()
        _assert_path_within_repo(resolved, root=root)
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError("repo_path must resolve to a directory inside the repository root")
        return resolved

    def _resolve_repo_file(self, use_path: str) -> Path:
        root = self.repo_root
        normalized = coerce_local_source_path(use_path.strip())
        candidate = Path(normalized)
        resolved: Path
        if candidate.is_absolute():
            resolved = candidate.expanduser().resolve()
            _assert_path_within_repo(resolved, root=root)
            if resolved.is_file():
                return resolved
        else:
            resolved = (root / candidate).expanduser().resolve()
            _assert_path_within_repo(resolved, root=root)
            if resolved.is_file():
                return resolved

        suffix = normalized.replace("\\", "/").lstrip("./")
        if not suffix:
            raise ValueError("use_path must not be empty")

        matches = [item for item in self._list_repo_files() if item.endswith(suffix)]
        if not matches:
            raise ValueError(f"use_path could not be resolved: {use_path}")
        matches.sort(key=lambda item: (len(item), item))
        best = matches[0]
        return (root / Path(best)).resolve()

    def _list_repo_files(self) -> list[str]:
        if self._file_index is not None:
            return self._file_index

        root = self.repo_root
        files: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            for filename in filenames:
                full = current / filename
                rel = full.relative_to(root).as_posix()
                files.append(rel)
        files.sort()
        self._file_index = files
        return files


class RepoFileSummarizer:
    """LangGraph ReAct file summarizer with strict output normalization."""

    def __init__(
        self,
        *,
        chat_model: BaseChatModel,
        prompt_version: str,
        max_input_chars: int,
        map_chunk_chars: int,
        retry_count: int,
        timeout_seconds: int,
        subject_repo: RepoSubjectRepository | None = None,
        edge_repo: RepoEdgeRepository | None = None,
        max_iterations: int = 3,
    ) -> None:
        self.chat_model = chat_model
        self.prompt_version = prompt_version
        self.max_input_chars = max(2000, max_input_chars)
        self.map_chunk_chars = max(1000, map_chunk_chars)
        self.retry_count = max(1, retry_count)
        self.timeout_seconds = max(5, timeout_seconds)
        self.max_iterations = max(1, max_iterations)
        self.subject_repo = subject_repo
        self.edge_repo = edge_repo
        log_react_agent_dependency_versions(logger)

    async def summarize(self, *, payload: SummaryInput) -> SummaryResult:
        material = [
            payload.subject_path,
            payload.language or "",
            payload.parse_status,
            payload.repo_path or "",
            payload.repo_address or "",
            payload.tech_stack or "",
            *payload.chunk_texts,
            self.prompt_version,
        ]
        input_hash = sha256("\n".join(material).encode("utf-8")).hexdigest()

        if not payload.chunk_texts:
            output = SummaryOutput(
                file_cluster=[],
                overall_summary="Empty file with no content to summarize.",
                important_relationships=[],
                group_function=None,
            )
            return SummaryResult(
                output=output,
                raw_output={
                    "mode": "deterministic_empty",
                    "prompt_version": self.prompt_version,
                },
                input_hash=input_hash,
                usage_trace=None,
            )

        user_prompt = render_prompt(
            "file_summary_user",
            prompt_version=self.prompt_version,
            subject_path=payload.subject_path,
            language=payload.language or "unknown",
            parse_status=payload.parse_status,
            tech=(payload.tech_stack or payload.language or "unknown"),
            repo_path=payload.repo_path or "",
            original_code_content=self._join_chunks(
                payload.chunk_texts,
                min(self.max_input_chars, FILE_SUMMARY_MAX_SOURCE_SNIPPET_CHARS),
            ),
        )

        last_error: Exception | None = None
        for _ in range(self.retry_count):
            tool_trace: list[dict] = []
            try:
                summary_output, raw_text, agent_meta, usage_trace = await self._invoke_agent(
                    payload=payload,
                    user_prompt=user_prompt,
                    tool_trace=tool_trace,
                )
                return SummaryResult(
                    output=summary_output,
                    raw_output={
                        "mode": "agent",
                        "raw_text": raw_text,
                        "tool_trace": tool_trace,
                        "agent": agent_meta,
                    },
                    input_hash=input_hash,
                    usage_trace=usage_trace,
                )
            except Exception as exc:  # pragma: no cover - runtime model/tool errors
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _invoke_agent(
        self,
        *,
        payload: SummaryInput,
        user_prompt: str,
        tool_trace: list[dict],
    ) -> tuple[SummaryOutput, str, dict[str, int], dict]:
        import time as _time

        tools = FileSummaryAgentTools(
            payload=payload,
            subject_repo=self.subject_repo,
            edge_repo=self.edge_repo,
            trace_sink=tool_trace,
        ).as_langchain_tools()
        t0 = _time.perf_counter()

        try:
            agent_result = await invoke_react_agent(
                chat_model=self.chat_model,
                tools=tools,
                system_prompt=FILE_SUMMARY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                timeout_seconds=self.timeout_seconds,
                max_iterations=self.max_iterations,
            )
            duration_ms = int((_time.perf_counter() - t0) * 1000)
            usage_trace = extract_full_trace_from_state(agent_result.state)
            usage_trace["duration_ms"] = duration_ms
            output = SummaryOutput.model_validate(_extract_summary_payload(agent_result.raw_text))
            return output, agent_result.raw_text, {"message_count": _message_count(agent_result.state)}, usage_trace
        except Exception as exc:
            if isinstance(exc, AgentProtocolError) and exc.code == "thought_signature_missing":
                logger.warning(
                    "Gemini thought_signature error for %s — falling back to direct synthesis",
                    payload.subject_path,
                )
            elif _is_recursion_limit_error(exc):
                logger.warning(
                    "Agent hit recursion limit for %s — falling back to direct synthesis",
                    payload.subject_path,
                )
            else:
                raise

        # Phase 2: forced synthesis without tools
        raw_text, usage_trace = await self._synthesize_without_tools(user_prompt)
        duration_ms = int((_time.perf_counter() - t0) * 1000)
        usage_trace["duration_ms"] = duration_ms
        output = SummaryOutput.model_validate(_extract_summary_payload(raw_text))
        return output, raw_text, {"message_count": 0, "synthesis_fallback": True}, usage_trace

    async def _synthesize_without_tools(self, user_prompt: str) -> tuple[str, dict]:
        """Single LLM call without tools to force summary output on budget exhaustion."""

        messages = [
            SystemMessage(content=FILE_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt + "\n\n" + _SYNTHESIS_FALLBACK_INSTRUCTION),
        ]
        response = await self.chat_model.ainvoke(messages)
        raw_text = response_to_text(response)
        if not raw_text.strip():
            raise ValueError("Synthesis fallback produced empty response")

        usage = getattr(response, "usage_metadata", None) or {}
        usage_trace = {
            "total_input_tokens": usage.get("input_tokens", 0) or 0,
            "total_output_tokens": usage.get("output_tokens", 0) or 0,
            "total_tokens": usage.get("total_tokens", 0) or 0,
            "cached_input_tokens": 0,
            "reasoning_tokens": 0,
            "llm_step_count": 1,
            "tool_call_count": 0,
            "steps": [],
            "synthesis_fallback": True,
        }
        return raw_text, usage_trace

    @staticmethod
    def _join_chunks(chunks: list[str], max_chars: int) -> str:
        buff: list[str] = []
        current = 0
        for chunk in chunks:
            if current >= max_chars:
                break
            remaining = max_chars - current
            piece = chunk[:remaining]
            buff.append(piece)
            current += len(piece)
        return "\n\n".join(buff)


def _record_tool_trace(
    trace_sink: list[dict],
    *,
    name: str,
    arguments: dict[str, Any],
    result: dict,
) -> None:
    """Append a compact tool-call trace entry for observability."""

    preview = json.dumps(result, ensure_ascii=True)
    if len(preview) > FILE_SUMMARY_MAX_TOOL_PREVIEW_CHARS:
        preview = f"{preview[:FILE_SUMMARY_MAX_TOOL_PREVIEW_CHARS]}..."
    trace_sink.append(
        {
            "name": name,
            "arguments": arguments,
            "result_preview": preview,
        }
    )


def _normalize_repo_root(repo_path: str | None) -> Path:
    """Return a resolved repository root path or current working directory fallback."""

    raw = coerce_local_source_path((repo_path or "").strip())
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def _assert_path_within_repo(path: Path, *, root: Path) -> None:
    """Raise when a path escapes the repository root."""

    if path == root:
        return
    if root not in path.parents:
        raise ValueError("Path is outside repository root")


def _read_text_safely(path: Path) -> str:
    """Read file text with utf-8 primary and latin-1 fallback."""

    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _is_recursion_limit_error(exc: Exception) -> bool:
    """Check whether the exception is a LangGraph recursion limit error."""

    raw = str(exc).lower()
    return "recursion limit" in raw or "graphrecursionerror" in raw


def _format_directory_result(result: dict) -> str:
    """Format directory listing as compact text for LLM consumption."""

    if "error" in result:
        return f"[directory: {result['repo_path']} | error: {result['error']}]"
    lines = [f"[directory: {result['repo_path']} | {result['total_entries']} entries]"]
    for entry in result["entries"]:
        prefix = "D" if entry["type"] == "dir" else "F"
        lines.append(f"{prefix} {entry['path']}")
    if result["has_more"]:
        lines.append(f"[next_cursor: {result['next_cursor']}]")
    return "\n".join(lines)


def _format_file_code_result(result: dict) -> str:
    """Format file code content as compact text for LLM consumption."""

    if "error" in result:
        return f"[file: {result['use_path']} | error: {result['error']}]"
    if not result.get("content"):
        return f"[file: {result['resolved_path']} | empty | {result['total_lines']} total lines]"
    header = (
        f"[file: {result['resolved_path']} | lines {result['start_line']}-{result['end_line']}"
        f" of {result['total_lines']}]"
    )
    parts = [header, result["content"]]
    if result["has_more"]:
        parts.append(f"[next_start_line: {result['next_start_line']}]")
    return "\n".join(parts)


def _format_reference_graph_result(result: dict) -> str:
    """Format reference graph as compact text for LLM consumption."""

    if "error" in result:
        return f"[ref_graph: error | {result['error']}]"

    resolved = result.get("resolved_subject")
    if resolved is None:
        return f"[ref_graph: {result['type']} | {result['input_subject']} | not found]"

    lines = [f"[ref_graph: {result['type']} | {result['input_subject']} -> {resolved['subject_path']}]"]
    for direction in ("outgoing", "incoming"):
        edges = result.get(direction, [])
        if not edges:
            continue
        lines.append(f"{direction}:")
        for edge in edges:
            parts = [f"  {edge['edge_type']} {edge['related_subject_path']} ({edge['related_subject_type']})"]
            if edge.get("line") is not None:
                loc = f"L{edge['line']}"
                if edge.get("column") is not None:
                    loc += f":{edge['column']}"
                parts.append(loc)
            sym = edge.get("related_symbol_qualname") or edge.get("related_symbol_name")
            if sym:
                parts.append(f"[{sym}]")
            lines.append(" ".join(parts))
    if not result.get("outgoing") and not result.get("incoming"):
        lines.append("(no references)")
    return "\n".join(lines)


def _extract_summary_payload(raw: str) -> dict:
    """Extract a summary payload from tagged sections or JSON fallback."""

    tagged_payload = _extract_tagged_payload(raw)
    if tagged_payload is not None:
        return tagged_payload
    return _extract_json(raw)


def _extract_tagged_payload(raw: str) -> dict | None:
    """Extract summary fields from ArchAgent-style tagged output."""

    file_cluster = _extract_tag_section(raw, "File_cluster_begin", "File_cluster_end")
    overall_summary = _extract_tag_section(raw, "Overall_Summary_start", "Overall_Summary_end")
    important = _extract_tag_section(raw, "Important_Relationships_start", "Important_Relationships_end")
    group_function = _extract_tag_section(raw, "Group_Function_start", "Group_Function_end")

    if overall_summary is None:
        return None

    summary_text = overall_summary.strip()
    if not summary_text:
        return None

    return {
        "file_cluster": _parse_tag_list(file_cluster),
        "overall_summary": summary_text,
        "important_relationships": _parse_tag_list(important),
        "group_function": (group_function.strip() if group_function and group_function.strip() else None),
    }


def _extract_tag_section(raw: str, start_tag: str, end_tag: str) -> str | None:
    pattern = re.compile(rf"\[{re.escape(start_tag)}\](.*?)\[{re.escape(end_tag)}\]", flags=re.DOTALL)
    match = pattern.search(raw)
    if not match:
        return None
    return match.group(1).strip()


def _parse_tag_list(value: str | None) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for line in value.splitlines():
        normalized = line.strip().strip(",")
        if not normalized:
            continue
        normalized = re.sub(r"^[-*]\s*", "", normalized)
        normalized = re.sub(r"^\d+\.\s*", "", normalized)
        if normalized:
            items.append(normalized)
    if items:
        return items

    # Fallback for comma-separated single-line outputs.
    split_items = [part.strip() for part in value.split(",") if part.strip()]
    return split_items


def _extract_json(raw: str) -> dict:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("Model output does not contain a JSON object")
    return json.loads(candidate[start : end + 1])


def _message_count(state: dict[str, Any]) -> int:
    messages = state.get("messages")
    if isinstance(messages, list):
        return len(messages)
    return 0
