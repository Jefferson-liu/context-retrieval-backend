from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

try:
    from langgraph.prebuilt import create_react_agent as create_agent
except Exception:  # pragma: no cover - optional dependency in constrained envs
    create_agent = None

_DEPENDENCIES_LOGGED = False


class AgentProtocolError(Exception):
    """Raised when model tool-calling violates required protocol semantics."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ReActAgentResult:
    """Final text and full LangGraph state returned by one ReAct run."""

    raw_text: str
    state: dict[str, Any]


def log_react_agent_dependency_versions(logger: logging.Logger) -> None:
    """Log one-time dependency versions for reproducible runtime debugging."""

    global _DEPENDENCIES_LOGGED
    if _DEPENDENCIES_LOGGED:
        return
    versions = _resolved_dependency_versions()
    logger.info("ReAct agent dependency versions: %s", versions)
    _DEPENDENCIES_LOGGED = True


async def invoke_react_agent(
    *,
    chat_model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
    max_iterations: int,
) -> ReActAgentResult:
    """Invoke a LangGraph ReAct agent and return extracted final assistant text."""

    if create_agent is None:
        raise RuntimeError("langchain create_agent is unavailable")
    if not hasattr(chat_model, "bind_tools"):
        raise RuntimeError("Configured chat model does not support tool binding")

    agent = create_agent(chat_model, tools)
    recursion_limit = max(10, max_iterations * 3)

    try:
        state = await asyncio.wait_for(
            agent.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ]
                },
                config={"recursion_limit": recursion_limit},
            ),
            timeout=max(5, timeout_seconds),
        )
    except Exception as exc:
        raw = str(exc)
        if _is_tool_protocol_error(raw):
            raise AgentProtocolError(
                code="thought_signature_missing",
                message=raw,
            ) from exc
        raise

    if not isinstance(state, dict):
        raise ValueError(f"Unexpected agent state type: {type(state)!r}")

    raw_text = extract_agent_response_text(state)
    if not raw_text.strip():
        raise ValueError("Agent completed without a non-empty assistant response")
    return ReActAgentResult(raw_text=raw_text, state=state)


def extract_agent_response_text(state: dict[str, Any]) -> str:
    """Return latest non-tool message text from LangGraph state."""

    messages = state.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            message_type = getattr(message, "type", "")
            if message_type == "tool":
                continue
            text = response_to_text(message)
            if text.strip():
                return text
    return str(state)


def response_to_text(response: object) -> str:
    """Convert LangChain response content into a plain text payload."""

    if isinstance(response, BaseMessage):
        content = response.content
    else:
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


@lru_cache(maxsize=1)
def _resolved_dependency_versions() -> dict[str, str]:
    package_names = (
        "langchain",
        "langchain-core",
        "langchain-google-genai",
        "langgraph",
        "langgraph-prebuilt",
    )
    versions: dict[str, str] = {}
    for package in package_names:
        try:
            versions[package] = metadata.version(package)
        except Exception:
            versions[package] = "unavailable"
    return versions


def _is_tool_protocol_error(raw_error: str) -> bool:
    normalized = raw_error.lower()
    return (
        "thought_signature" in normalized
        or "function call is missing a thought_signature" in normalized
    )


_TOOL_CONTENT_PREVIEW_MAX = 2000


def extract_full_trace_from_state(state: dict[str, Any]) -> dict:
    """Extract ordered step trace with per-step token usage from LangGraph state.

    Returns a dict with aggregate token totals and an ordered ``steps`` list
    containing every message in the agent conversation.  AI messages include
    per-step token breakdown, reasoning content, and tool-call decisions.  Tool
    messages include a truncated content preview.
    """

    messages = state.get("messages")
    if not isinstance(messages, list):
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "cached_input_tokens": 0,
            "reasoning_tokens": 0,
            "llm_step_count": 0,
            "tool_call_count": 0,
            "steps": [],
        }

    agg_input = 0
    agg_output = 0
    agg_total = 0
    agg_cached = 0
    agg_reasoning = 0
    llm_steps = 0
    tool_calls = 0
    steps: list[dict] = []

    for idx, message in enumerate(messages):
        msg_type = getattr(message, "type", "")

        if msg_type == "ai":
            usage = getattr(message, "usage_metadata", None) or {}
            resp_meta = getattr(message, "response_metadata", None) or {}
            raw_tool_calls = getattr(message, "tool_calls", None) or []

            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            total_tokens_step = usage.get("total_tokens", 0) or 0
            input_details = usage.get("input_token_details") or {}
            output_details = usage.get("output_token_details") or {}
            cached = input_details.get("cache_read", 0) or 0
            reasoning = output_details.get("reasoning", 0) or 0

            agg_input += input_tokens
            agg_output += output_tokens
            agg_total += total_tokens_step
            agg_cached += cached
            agg_reasoning += reasoning
            llm_steps += 1
            tool_calls += len(raw_tool_calls)

            tc_list = [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "arguments": tc.get("args", {}),
                }
                for tc in raw_tool_calls
            ]

            steps.append({
                "step_index": idx,
                "role": "ai",
                "content": response_to_text(message),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens_step,
                "cached_input_tokens": cached,
                "reasoning_tokens": reasoning,
                "finish_reason": resp_meta.get("finish_reason"),
                "model_name": resp_meta.get("model_name"),
                "tool_calls": tc_list,
            })

        elif msg_type == "tool":
            content_raw = getattr(message, "content", "")
            if not isinstance(content_raw, str):
                content_raw = str(content_raw)
            preview = content_raw[:_TOOL_CONTENT_PREVIEW_MAX]

            steps.append({
                "step_index": idx,
                "role": "tool",
                "name": getattr(message, "name", None),
                "tool_call_id": getattr(message, "tool_call_id", None),
                "content_preview": preview,
            })

        elif msg_type in {"system", "human"}:
            steps.append({
                "step_index": idx,
                "role": msg_type,
                "content": response_to_text(message),
            })

        else:
            steps.append({
                "step_index": idx,
                "role": msg_type or "unknown",
                "content": response_to_text(message),
            })

    return {
        "total_input_tokens": agg_input,
        "total_output_tokens": agg_output,
        "total_tokens": agg_total,
        "cached_input_tokens": agg_cached,
        "reasoning_tokens": agg_reasoning,
        "llm_step_count": llm_steps,
        "tool_call_count": tool_calls,
        "steps": steps,
    }
