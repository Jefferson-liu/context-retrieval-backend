from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from services.repo_knowledge.group_summarization.errors import TraceableLLMError
from services.repo_knowledge.prompt_loader import load_prompt, render_prompt
from services.repo_knowledge.group_summarization.types import GroupSummaryInput, GroupSummaryOutput

GROUP_SUMMARY_SYSTEM_PROMPT = load_prompt("group_summary_system")


@dataclass(slots=True)
class GroupSummaryResult:
    """Structured summary output plus raw model response payload."""

    output: GroupSummaryOutput
    raw_output: dict
    input_hash: str


class RepoGroupSummarizer:
    """LLM summarizer for deterministic groups with strict JSON validation."""

    def __init__(
        self,
        *,
        chat_model: BaseChatModel,
        prompt_version: str,
        max_input_chars: int,
        retry_count: int,
        timeout_seconds: int,
    ) -> None:
        self.chat_model = chat_model
        self.prompt_version = prompt_version
        self.max_input_chars = max(3000, max_input_chars)
        self.retry_count = max(1, retry_count)
        self.timeout_seconds = max(5, timeout_seconds)

    async def summarize(self, *, payload: GroupSummaryInput) -> GroupSummaryResult:
        material = [
            payload.source_run_id,
            payload.source_file_summary_run_id,
            payload.group_id,
            payload.group_key,
            payload.layer_hint,
            str(payload.is_infrastructure_seed),
            *payload.representative_subject_ids,
            *[member.subject_id for member in payload.members],
            self.prompt_version,
        ]
        input_hash = sha256("\n".join(material).encode("utf-8")).hexdigest()

        if not payload.members:
            output = GroupSummaryOutput(
                name=f"{payload.group_label} group",
                overall_summary="Deterministic group has no members to summarize.",
                business_purpose="No business-purpose evidence was available for this empty group.",
                responsibilities=[],
                tags=["empty-group"],
                representative_subject_ids=[],
                mermaid_diagram="flowchart TB\n    Empty[\"No members\"]",
                is_infrastructure=payload.is_infrastructure_seed,
                confidence=0.0,
            )
            return GroupSummaryResult(
                output=output,
                raw_output={"mode": "deterministic_empty", "prompt_version": self.prompt_version},
                input_hash=input_hash,
            )

        prompt_body = self._build_prompt(payload)
        output, raw_text = await self._invoke_structured(user_prompt=prompt_body)
        valid_member_ids = {member.subject_id for member in payload.members}
        sanitized_ids = [subject_id for subject_id in output.representative_subject_ids if subject_id in valid_member_ids]
        output = output.model_copy(update={"representative_subject_ids": sanitized_ids})
        return GroupSummaryResult(
            output=output,
            raw_output={"mode": "single_pass", "raw_text": raw_text},
            input_hash=input_hash,
        )

    def _build_prompt(self, payload: GroupSummaryInput) -> str:
        member_lines: list[str] = []
        for member in payload.members:
            member_lines.append(f"- subject_id: {member.subject_id}")
            member_lines.append(f"  subject_path: {member.subject_path}")
            member_lines.append(f"  language: {member.language or 'unknown'}")
            member_lines.append(f"  representative: {member.is_representative}")
            member_lines.append(f"  rank: {member.rank}")
            member_lines.append(f"  overall_summary: {member.overall_summary}")
            if member.group_function:
                member_lines.append(f"  group_function: {member.group_function}")
            if member.important_relationships:
                member_lines.append("  important_relationships:")
                for rel in member.important_relationships[:4]:
                    member_lines.append(f"    - {rel}")

        full_text = render_prompt(
            "group_summary_user",
            prompt_version=self.prompt_version,
            group_id=payload.group_id,
            group_key=payload.group_key,
            group_label=payload.group_label,
            layer_hint=payload.layer_hint,
            is_infrastructure_seed=str(payload.is_infrastructure_seed),
            representative_subject_ids=str(payload.representative_subject_ids),
            dependency_neighbor_paths=str(payload.dependency_neighbor_paths),
            heuristics_json=json.dumps(payload.heuristics, ensure_ascii=True),
            member_evidence="\n".join(member_lines),
        )

        if len(full_text) <= self.max_input_chars:
            return full_text
        return full_text[: self.max_input_chars]

    async def _invoke_structured(self, *, user_prompt: str) -> tuple[GroupSummaryOutput, str]:
        last_error: Exception | None = None
        last_raw_text: str | None = None
        for _ in range(self.retry_count):
            try:
                response = await self._invoke_messages(
                    messages=[
                        SystemMessage(content=GROUP_SUMMARY_SYSTEM_PROMPT),
                        HumanMessage(content=user_prompt),
                    ]
                )
                raw_text = self._response_to_text(response)
                last_raw_text = raw_text
                payload = _normalize_group_summary_payload(_extract_json(raw_text))
                output = GroupSummaryOutput.model_validate(payload)
                return output, raw_text
            except Exception as exc:  # pragma: no cover - runtime LLM failures
                last_error = exc
        assert last_error is not None
        raise TraceableLLMError(
            stage="repo_manager_segment",
            diagnostic_code=_classify_llm_failure(last_error),
            message="repo_manager_segment_llm_failed",
            raw_text=last_raw_text,
            details={
                "error": str(last_error),
                "error_type": type(last_error).__name__,
            },
        ) from last_error

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



def _normalize_group_summary_payload(payload: dict) -> dict:
    if "mermaid_diagram" in payload:
        return payload
    label = str(payload.get("name") or "Segment").replace('"', "'")
    payload = dict(payload)
    payload["mermaid_diagram"] = f'flowchart TB\n    Segment["{label}"]'
    return payload


def _classify_llm_failure(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "repo_manager_segment_timeout"
    if isinstance(error, json.JSONDecodeError):
        return "repo_manager_segment_invalid_json"
    if isinstance(error, ValidationError):
        return "repo_manager_segment_schema_validation_failed"
    if isinstance(error, ValueError):
        return "repo_manager_segment_invalid_output"
    return "repo_manager_segment_invoke_failed"
