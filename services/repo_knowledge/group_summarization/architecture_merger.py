from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from hashlib import sha256

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from services.repo_knowledge.group_summarization.errors import TraceableLLMError
from services.repo_knowledge.prompt_loader import load_prompt, render_prompt

ARCHITECTURE_MERGE_SYSTEM_PROMPT = load_prompt("architecture_merge_system")


class ArchitectureMergeOutput(BaseModel):
    """Strict JSON schema for the merged repo architecture artifact."""

    model_config = ConfigDict(extra="forbid")

    overall_summary: str = Field(..., min_length=1)
    mermaid_diagram: str = Field(..., min_length=1)


@dataclass(slots=True)
class ArchitectureSegmentArtifact:
    """One segment-level architecture artifact used during merge."""

    group_id: str
    name: str
    overall_summary: str
    business_purpose: str
    mermaid_diagram: str


@dataclass(slots=True)
class ArchitectureMergeInput:
    """Prompt material for merging repo-manager segments into one architecture diagram."""

    source_run_id: str
    source_file_summary_run_id: str
    repo_readme_markdown: str
    segment_artifacts: list[ArchitectureSegmentArtifact]
    prompt_version: str


@dataclass(slots=True)
class ArchitectureMergeResult:
    """Structured merge output plus raw model response payload."""

    output: ArchitectureMergeOutput
    raw_output: dict
    input_hash: str


class RepoArchitectureMerger:
    """LLM merger that turns Repo Manager segment artifacts into one Mermaid architecture diagram."""

    def __init__(
        self,
        *,
        chat_model: BaseChatModel,
        max_input_chars: int,
        retry_count: int,
        timeout_seconds: int,
    ) -> None:
        self.chat_model = chat_model
        self.max_input_chars = max(4000, max_input_chars)
        self.retry_count = max(1, retry_count)
        self.timeout_seconds = max(5, timeout_seconds)

    async def summarize(self, *, payload: ArchitectureMergeInput) -> ArchitectureMergeResult:
        material = [
            payload.source_run_id,
            payload.source_file_summary_run_id,
            payload.repo_readme_markdown,
            payload.prompt_version,
            *[
                f"{segment.group_id}|{segment.name}|{segment.overall_summary}|{segment.business_purpose}|{segment.mermaid_diagram}"
                for segment in payload.segment_artifacts
            ],
        ]
        input_hash = sha256("\n".join(material).encode("utf-8")).hexdigest()

        user_prompt = render_prompt(
            "architecture_merge_user",
            prompt_version=payload.prompt_version,
            repo_readme_markdown=_truncate_text(payload.repo_readme_markdown, self.max_input_chars // 2),
            segment_artifacts=_truncate_text(self._render_segments(payload.segment_artifacts), self.max_input_chars // 2),
        )

        last_error: Exception | None = None
        last_raw_text: str | None = None
        for _ in range(self.retry_count):
            try:
                response = await self._invoke_messages(
                    messages=[
                        SystemMessage(content=ARCHITECTURE_MERGE_SYSTEM_PROMPT),
                        HumanMessage(content=user_prompt),
                    ]
                )
                raw_text = self._response_to_text(response)
                last_raw_text = raw_text
                output = ArchitectureMergeOutput.model_validate(_extract_architecture_merge_payload(raw_text))
                return ArchitectureMergeResult(
                    output=output,
                    raw_output={"mode": "single_pass", "raw_text": raw_text},
                    input_hash=input_hash,
                )
            except Exception as exc:  # pragma: no cover - runtime LLM failures
                last_error = exc
        assert last_error is not None
        raise TraceableLLMError(
            stage="repo_architecture_merge",
            diagnostic_code=_classify_llm_failure(last_error),
            message="repo_architecture_merge_llm_failed",
            raw_text=last_raw_text,
            details={
                "error": str(last_error),
                "error_type": type(last_error).__name__,
            },
        ) from last_error

    @staticmethod
    def _render_segments(segments: list[ArchitectureSegmentArtifact]) -> str:
        blocks: list[str] = []
        for segment in segments:
            blocks.append(
                json.dumps(
                    {
                        "group_id": segment.group_id,
                        "name": segment.name,
                        "overall_summary": segment.overall_summary,
                        "business_purpose": segment.business_purpose,
                        "mermaid_diagram": segment.mermaid_diagram,
                    },
                    ensure_ascii=True,
                )
            )
        return "\n".join(blocks)

    async def _invoke_messages(self, *, messages: list) -> object:
        if hasattr(self.chat_model, "ainvoke"):
            return await asyncio.wait_for(self.chat_model.ainvoke(messages), timeout=self.timeout_seconds)
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: self.chat_model.invoke(messages)),
            timeout=self.timeout_seconds,
        )

    @staticmethod
    def _response_to_text(response: object) -> str:
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
        return str(response)


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


def _extract_architecture_merge_payload(raw: str) -> dict:
    """Extract architecture merge payload from tagged sections or JSON fallback."""

    tagged = _extract_tagged_architecture_merge_payload(raw)
    if tagged is not None:
        return tagged
    return _extract_json(raw)


def _extract_tagged_architecture_merge_payload(raw: str) -> dict | None:
    """Extract architecture merge fields from tagged output."""

    overall_summary = _extract_tag_section(raw, "Overall_Summary_start", "Overall_Summary_end")
    mermaid = _extract_tag_section(raw, "Mermaid_Diagram_start", "Mermaid_Diagram_end")

    if overall_summary is None or not overall_summary.strip():
        return None
    if mermaid is None or not mermaid.strip():
        return None

    return {
        "overall_summary": overall_summary.strip(),
        "mermaid_diagram": mermaid.strip(),
    }


def _extract_tag_section(raw: str, start_tag: str, end_tag: str) -> str | None:
    pattern = re.compile(rf"\[{re.escape(start_tag)}\](.*?)\[{re.escape(end_tag)}\]", flags=re.DOTALL)
    match = pattern.search(raw)
    if not match:
        return None
    return match.group(1).strip()


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


def _classify_llm_failure(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "repo_architecture_merge_timeout"
    if isinstance(error, json.JSONDecodeError):
        return "repo_architecture_merge_invalid_json"
    if isinstance(error, ValidationError):
        return "repo_architecture_merge_schema_validation_failed"
    if isinstance(error, ValueError):
        return "repo_architecture_merge_invalid_output"
    return "repo_architecture_merge_invoke_failed"