"""
LLM Provider Interface

This module defines an abstract interface for LLM providers and concrete implementations
for Anthropic and OpenAI, allowing easy switching between providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from infrastructure.external.anthropic_interface import get_anthropic_response, get_anthropic_response_safe, get_anthropic_response_with_tools
from infrastructure.external.openai_interface import get_openai_response, get_openai_response_safe, get_openai_response_with_tools
from config import settings

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def get_response(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        pass
    
    @abstractmethod
    async def get_response_safe(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        pass
    
    @abstractmethod
    async def get_response_with_tools(self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None, max_tokens: int = 2048):
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""
    
    def __init__(self, default_model: str = "claude-3-haiku-20240307"):
        self.default_model = default_model
    
    async def get_response(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        model = model or self.default_model
        return await get_anthropic_response(message, system_prompt, model, max_tokens)
    
    async def get_response_safe(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        model = model or self.default_model
        return await get_anthropic_response_safe(message, system_prompt, model, max_tokens)
    
    async def get_response_with_tools(self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None, max_tokens: int = 2048):
        model = model or self.default_model
        return await get_anthropic_response_with_tools(messages, system_prompt, tools, model, max_tokens)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation."""
    
    def __init__(self, default_model: str = "gpt-3.5-turbo"):
        self.default_model = default_model
    
    async def get_response(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        model = model or self.default_model
        return await get_openai_response(message, system_prompt, model, max_tokens)
    
    async def get_response_safe(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024) -> str:
        model = model or self.default_model
        return await get_openai_response_safe(message, system_prompt, model, max_tokens)
    
    async def get_response_with_tools(self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None, max_tokens: int = 2048):
        model = model or self.default_model
        return await get_openai_response_with_tools(messages, system_prompt, tools, model, max_tokens)


provider = settings.LLM_PROVIDER

def get_llm_provider(provider_name: str = provider) -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Args:
        provider_name: Name of the provider ("anthropic" or "openai")
        
    Returns:
        LLMProvider instance
        
    Raises:
        ValueError: If provider_name is not supported
    """
    if provider_name.lower() == "anthropic":
        return AnthropicProvider()
    elif provider_name.lower() == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}. Supported: anthropic, openai")