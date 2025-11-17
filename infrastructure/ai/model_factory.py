from __future__ import annotations

from typing import Any

from config import settings
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrockConverse

def _resolve_provider(model_name: str | None) -> str:
    """Infer provider from model name or fallback provider setting."""
    name = (model_name or "").lower()
    if name.startswith("claude") or name.startswith("anthropic"):
        return "anthropic"
    if name.startswith(("gpt", "text-", "o1")) or "openai" in name:
        return "openai"
    if name.startswith(("aws", "bedrock", "amazon")):
        return "aws"

    fallback = (settings.LLM_PROVIDER or "").lower()
    if fallback.startswith("anthropic") or fallback.startswith("claude"):
        return "anthropic"
    if fallback.startswith("openai") or fallback.startswith("gpt"):
        return "openai"
    if fallback.startswith("aws") or fallback.startswith("bedrock"):
        return "aws"
    return fallback


def build_chat_model(
    model_name: str,
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Create a chat model instance for the requested provider."""
    resolved_provider = _resolve_provider(model_name)

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
