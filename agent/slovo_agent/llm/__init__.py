"""
LLM Provider Abstraction Layer for Slovo Agent Runtime.

Provides a unified interface for interacting with different LLM providers
(OpenAI, Anthropic) with support for structured outputs using Pydantic.
"""

from slovo_agent.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from slovo_agent.llm.factory import create_llm_provider, get_default_provider
from slovo_agent.llm.providers.anthropic import AnthropicProvider
from slovo_agent.llm.providers.openai import OpenAIProvider

__all__ = [
    # Base types
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "MessageRole",
    # Providers
    "AnthropicProvider",
    "OpenAIProvider",
    # Factory
    "create_llm_provider",
    "get_default_provider",
]
