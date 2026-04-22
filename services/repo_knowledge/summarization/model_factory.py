from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config.settings import Settings

logger = logging.getLogger(__name__)


class SummaryModelFactoryError(Exception):
    """Raised when summary model selection or provider configuration fails."""


def create_summary_chat_model(
    *,
    settings: Settings,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model for summary file_summary."""
    provider = (provider_override or settings.REPO_SUMMARY_MODEL_PROVIDER or settings.MODEL).strip().lower()
    model_name = (model_override or settings.REPO_SUMMARY_MODEL_NAME).strip()
    temperature = settings.REPO_SUMMARY_TEMPERATURE
    timeout = settings.REPO_SUMMARY_TIMEOUT_SECONDS

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise SummaryModelFactoryError("OPENAI_API_KEY is not configured")
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model_name or "gpt-4o-mini",
            temperature=temperature,
            timeout=timeout,
        )

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise SummaryModelFactoryError("GEMINI_API_KEY is not configured")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise SummaryModelFactoryError(
                "langchain-google-genai is required for provider=gemini"
            ) from exc
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY,
            model=model_name or "gemini-3.1-flash-lite-preview",
            temperature=temperature,
            timeout=timeout,
        )

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise SummaryModelFactoryError("ANTHROPIC_API_KEY is not configured")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise SummaryModelFactoryError(
                "langchain-anthropic is required for provider=anthropic"
            ) from exc
        return ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model=model_name or "claude-3-5-haiku-latest",
            temperature=temperature,
            timeout=timeout,
        )

    raise SummaryModelFactoryError(f"Unsupported summary model provider: {provider}")
