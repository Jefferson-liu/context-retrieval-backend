"""
OpenAI Interface Module

This module provides a centralized async interface for interacting with OpenAI's GPT API.
It serves as the single source of truth for OpenAI API calls, preventing circular imports
and ensuring consistent async API usage across the application.
"""

import os
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from infrastructure.utils.prompt_loader import load_prompt
from config import settings

# Initialize async OpenAI client only if API key is available
client = None
if settings.OPENAI_API_KEY:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def get_openai_response(message: str, system_prompt: Optional[str] = None, model: str = "gpt-3.5-turbo", max_tokens: int = 1024) -> str:
    """
    Send a message to OpenAI's GPT API and return the response (async).
    
    Args:
        message: The user message to send to GPT
        system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
        model: GPT model to use (default: gpt-3.5-turbo for speed/cost)
        max_tokens: Maximum tokens in response
        
    Returns:
        GPT's response text
        
    Raises:
        Exception: If API call fails or API key is not configured
    """
    if not client:
        raise Exception("OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.")
    
    # Use provided system prompt or load default
    if system_prompt is None:
        system_prompt = load_prompt("simple_assistant")

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )
    
    return response.choices[0].message.content


async def get_openai_response_safe(message: str, system_prompt: Optional[str] = None, model: str = "gpt-3.5-turbo", max_tokens: int = 1024) -> str:
    """
    Safe async wrapper for get_openai_response that returns error messages instead of raising exceptions.
    
    Args:
        message: The user message to send to GPT
        system_prompt: Optional system prompt. If None, uses "simple_assistant" prompt
        model: GPT model to use (default: gpt-3.5-turbo for speed/cost)
        max_tokens: Maximum tokens in response
        
    Returns:
        GPT's response text or error message string
    """
    try:
        return await get_openai_response(message, system_prompt, model, max_tokens)
    except Exception as e:
        return f"Error: {str(e)}"


async def get_openai_response_with_tools(messages: List[Dict[str, Any]], system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, model: str = "gpt-3.5-turbo", max_tokens: int = 2048):
    """
    Send messages to OpenAI's GPT API with tool support and return the full response object.
    
    Args:
        messages: List of message dictionaries with role and content
        system_prompt: Optional system prompt
        tools: Optional list of tool definitions
        model: GPT model to use
        max_tokens: Maximum tokens in response
        
    Returns:
        Full GPT response object
        
    Raises:
        Exception: If API call fails or API key is not configured
    """
    if not client:
        raise Exception("OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.")
    
    # Use provided system prompt or load default
    if system_prompt is None:
        system_prompt = load_prompt("simple_assistant")
    
    # Prepare the request parameters
    request_params = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system_prompt}] + messages
    }
    
    if tools:
        request_params["tools"] = tools
    
    response = await client.chat.completions.create(**request_params)
    
    return response
