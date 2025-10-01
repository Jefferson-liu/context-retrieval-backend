"""
Anthropic Interface Module

This module provides a centralized async interface for interacting with Anthropic's Claude API.
It serves as the single source of truth for Anthropic API calls, preventing circular imports
and ensuring consistent async API usage across the application.
"""

import os
from typing import Optional, List, Dict, Any
from anthropic import AsyncAnthropic
from infrastructure.utils.prompt_loader import load_prompt
from config import settings

# Initialize async Anthropic client
client = AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY
)


async def get_anthropic_response(message: str, system_prompt: Optional[str] = None, model: str = "claude-3-haiku-20240307", max_tokens: int = 1024) -> str:
    """
    Send a message to Anthropic's Claude API and return the response (async).
    
    Args:
        message: The user message to send to Claude
        system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
        model: Claude model to use (default: haiku for speed/cost)
        max_tokens: Maximum tokens in response
        
    Returns:
        Claude's response text
        
    Raises:
        Exception: If API call fails or API key is not configured
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise Exception("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in your .env file.")
    
    # Use provided system prompt or load default
    if system_prompt is None:
        system_prompt = load_prompt("simple_assistant")

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
                {"role": "user", "content": message}
            ]
        )
    
    return response.content[0].text


async def get_anthropic_response_safe(message: str, system_prompt: Optional[str] = None, model: str = "claude-3-haiku-20240307", max_tokens: int = 1024) -> str:
    """
    Safe async wrapper for get_anthropic_response that returns error messages instead of raising exceptions.
    
    Args:
        message: The user message to send to Claude
        system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
        model: Claude model to use (default: haiku for speed/cost)
        max_tokens: Maximum tokens in response
        
    Returns:
        Claude's response text or error message string
    """
    try:
        return await get_anthropic_response(message, system_prompt, model, max_tokens)
    except Exception as e:
        return f"Error: {str(e)}"


async def get_anthropic_response_with_tools(messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: str = "claude-3-haiku-20240307", max_tokens: int = 2048):
    """
    Send messages to Anthropic's Claude API with tool support and return the full response object.
    
    Args:
        messages: List of message dictionaries with role and content
        system_prompt: Optional system prompt
        tools: Optional list of tool definitions
        model: Claude model to use
        max_tokens: Maximum tokens in response
        
    Returns:
        Full Claude response object
        
    Raises:
        Exception: If API call fails or API key is not configured
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise Exception("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in your .env file.")
    
    # Use provided system prompt or load default
    if system_prompt is None:
        system_prompt = load_prompt("simple_assistant")
    
    # Prepare the request parameters
    request_params = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages
    }
    
    if tools:
        request_params["tools"] = tools
    
    response = await client.messages.create(**request_params)
    
    return response


class AsyncAnthropicInterface:
    """
    Async class-based interface for Anthropic API with configuration options.
    Useful for cases where you need to maintain state or configuration.
    """
    
    def __init__(self, model: str = "claude-3-haiku-20240307", max_tokens: int = 1024):
        """
        Initialize the async Anthropic interface with default settings.
        
        Args:
            model: Default Claude model to use
            max_tokens: Default maximum tokens in response
        """
        self.model = model
        self.max_tokens = max_tokens
        
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise Exception("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in your .env file.")
        
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    async def get_response(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """
        Get a response from Claude using the configured or provided settings (async).
        
        Args:
            message: The user message to send to Claude
            system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
            model: Optional model override
            max_tokens: Optional max_tokens override
            
        Returns:
            Claude's response text
            
        Raises:
            Exception: If API call fails
        """
        # Use instance defaults or provided overrides
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        
        # Use provided system prompt or load default
        if system_prompt is None:
            system_prompt = load_prompt("simple_assistant")
        
        response = await self.client.messages.create(
            model=actual_model,
            max_tokens=actual_max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": message}
            ]
        )
        
        return response.content[0].text
    
    async def get_response_safe(self, message: str, system_prompt: Optional[str] = None, model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """
        Safe async wrapper for get_response that returns error messages instead of raising exceptions.
        
        Args:
            message: The user message to send to Claude
            system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
            model: Optional model override
            max_tokens: Optional max_tokens override
            
        Returns:
            Claude's response text or error message string
        """
        try:
            return await self.get_response(message, system_prompt, model, max_tokens)
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def get_response_with_tools(self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None, max_tokens: Optional[int] = None):
        """
        Get a response from Claude with tool support using the configured or provided settings (async).
        
        Args:
            messages: List of message dictionaries with role and content
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions
            model: Optional model override
            max_tokens: Optional max_tokens override
            
        Returns:
            Full Claude response object
            
        Raises:
            Exception: If API call fails
        """
        # Use instance defaults or provided overrides
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        
        # Use provided system prompt or load default
        if system_prompt is None:
            system_prompt = load_prompt("simple_assistant")
        
        # Prepare the request parameters
        request_params = {
            "model": actual_model,
            "max_tokens": actual_max_tokens,
            "system": system_prompt,
            "messages": messages
        }
        
        if tools:
            request_params["tools"] = tools
        
        response = await self.client.messages.create(**request_params)
        
        return response
