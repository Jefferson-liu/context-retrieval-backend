from __future__ import annotations

from typing import Any
import os

from config import settings
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import ParrotFakeChatModel
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrockConverse
from langchain_core.runnables import RunnableLambda
from typing import Callable, Type
import logging
import threading

logger = logging.getLogger(__name__)

_DUMMY_CALL_COUNT = 0
_DUMMY_LOCK = threading.Lock()


def reset_dummy_call_count() -> None:
    """Reset the global dummy call counter (helpful per request/run)."""
    global _DUMMY_CALL_COUNT
    with _DUMMY_LOCK:
        _DUMMY_CALL_COUNT = 0


def get_dummy_call_count() -> int:
    """Return the total number of DummyChatModel invocations."""
    with _DUMMY_LOCK:
        return _DUMMY_CALL_COUNT


def _increment_dummy_calls() -> int:
    global _DUMMY_CALL_COUNT
    with _DUMMY_LOCK:
        _DUMMY_CALL_COUNT += 1
        return _DUMMY_CALL_COUNT


class CountingParrotFakeChatModel(ParrotFakeChatModel):
    """Fake chat model that echoes inputs and tracks call counts without external traffic."""

    call_count: int = 0
    log_calls: bool = True

    def __init__(self, *args, log_calls: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "call_count", 0)
        object.__setattr__(self, "log_calls", log_calls)

    @property
    def _llm_type(self) -> str:
        return "dummy"

    def _generate(self, messages, stop=None, **kwargs):
        self.call_count += 1
        total_calls = _increment_dummy_calls()
        if self.log_calls:
            logger.info(
                "CountingParrotFakeChatModel call #%s (total=%s) messages=%s",
                self.call_count,
                total_calls,
                messages,
            )
            print(
                "CountingParrotFakeChatModel call #%s (total=%s) messages=%s"
                % (self.call_count, total_calls, messages)
            )
        return super()._generate(messages, stop=stop, **kwargs)

    async def _agenerate(self, messages, stop=None, **kwargs):
        # Mirror sync path
        self.call_count += 1
        total_calls = _increment_dummy_calls()
        if self.log_calls:
            logger.info(
                "CountingParrotFakeChatModel async call #%s (total=%s) messages=%s",
                self.call_count,
                total_calls,
                messages,
            )
            print(
                "CountingParrotFakeChatModel async call #%s (total=%s) messages=%s"
                % (self.call_count, total_calls, messages)
            )
        return await super()._agenerate(messages, stop=stop, **kwargs)

    def with_structured_output(self, schema: Any | Type[Any], **kwargs):
        """
        Provide a structured-output runnable for the fake model so chains don't fail.

        Returns a Runnable that converts the last message content into the requested schema
        when possible, otherwise instantiates the schema with defaults.
        """
        def _to_schema(_input):
            total_calls = _increment_dummy_calls()
            if self.log_calls:
                logger.info(
                    "CountingParrotFakeChatModel structured call #%s input=%s",
                    total_calls,
                    _input,
                )
                print(
                    "CountingParrotFakeChatModel structured call #%s input=%s"
                    % (total_calls, _input)
                )
            # Best-effort conversion: try pydantic model_validate/model_construct, else call/instantiate.
            try:
                if hasattr(schema, "model_validate"):
                    return schema.model_validate({})
                if callable(schema):
                    return schema()
            except Exception:
                return schema
            return schema

        return RunnableLambda(lambda x: _to_schema(x))


def _resolve_provider(model_name: str | None) -> str:
    """Infer provider from model name or fallback provider setting."""
    # Hard override via env for testing without external calls.
    if os.getenv("USE_DUMMY_LLM", "").strip().lower() in {"1", "true", "yes"}:
        return "dummy"

    # Primary signal: the model name itself.
    name = (model_name or "").lower()
    if name.startswith("dummy"):
        return "dummy"
    if name.startswith("claude") or name.startswith("anthropic"):
        return "anthropic"
    if name.startswith(("gpt", "text-", "o1")) or "openai" in name:
        return "openai"
    if name.startswith(("aws", "bedrock", "amazon")):
        return "aws"

    # Secondary: global fallback when model name doesn't encode provider.
    fallback = (settings.LLM_PROVIDER or "").lower()
    if fallback.startswith("dummy"):
        return "dummy"
    if fallback.startswith("anthropic") or fallback.startswith("claude"):
        return "anthropic"
    if fallback.startswith("openai") or fallback.startswith("gpt"):
        return "openai"
    if fallback.startswith(("aws", "bedrock", "amazon")):
        return "aws"

    return fallback


def build_chat_model(
    model_name: str,
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Create a chat model instance for the requested provider."""
    resolved_provider = _resolve_provider(model_name)

    if resolved_provider == "dummy":
        # Skip external calls; Parrot echoes input and tracks counts.
        log_calls = kwargs.pop("log_calls", True)
        return CountingParrotFakeChatModel(log_calls=log_calls, **kwargs)

    if resolved_provider == "anthropic":
        api_key = kwargs.pop("api_key", settings.ANTHROPIC_API_KEY)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        return ChatAnthropic(
            model_name=model_name,
            temperature=temperature,
            api_key=api_key,
            **kwargs,
        )

    if resolved_provider == "openai":
        api_key = kwargs.pop("api_key", settings.OPENAI_API_KEY)
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=api_key,
            store=True,
            **kwargs,
        )

    if resolved_provider == "aws":
        return ChatBedrockConverse(
            model=model_name,
            temperature=temperature,
            region_name="us-east-1",
            **kwargs,
        )

    raise ValueError(
        f"Unsupported model name'{model_name}'. "
        "Can only build models for 'anthropic', 'openai', or 'aws'"
    )
