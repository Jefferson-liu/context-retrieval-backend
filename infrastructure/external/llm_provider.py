from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, List, Protocol, runtime_checkable

from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI  
from langchain_anthropic import ChatAnthropic
from config import settings

class LLMProvider(Protocol):
    """Protocol for LLM providers"""

    async def get_response(self, prompt: str) -> str:
        ...

def get_chat_provider(model_name: str, provider_name: Optional[str] = None) -> BaseLanguageModel:
    selected = (provider_name or settings.LLM_PROVIDER or "").lower()

    if selected == "openai":
        model = ChatOpenAI(model=model_name) if model_name else ChatOpenAI()
        return model

    if selected == "anthropic":
        model = ChatAnthropic(model=model_name) if model_name else ChatAnthropic()
        return model

    raise ValueError("Unsupported LLM provider. Set LLM_PROVIDER to 'openai' or 'anthropic'.")