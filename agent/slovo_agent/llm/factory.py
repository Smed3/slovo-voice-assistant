"""
LLM Provider Factory.

Provides factory functions for creating LLM providers based on configuration
and available API keys.
"""

from functools import lru_cache

import structlog

from slovo_agent.config import settings
from slovo_agent.llm.base import LLMConfig, LLMProvider
from slovo_agent.llm.providers.anthropic import AnthropicProvider
from slovo_agent.llm.providers.openai import OpenAIProvider

logger = structlog.get_logger(__name__)

class LLMProviderError(Exception):
    """Raised when there's an error creating an LLM provider."""

    pass


def create_llm_provider(
    provider_name: str,
    model: str | None = settings.llm_model,
    temperature: float = settings.llm_temperature,
    max_tokens: int = settings.llm_max_tokens,
) -> LLMProvider:
    """
    Create an LLM provider instance.

    Args:
        provider_name: Name of the provider ('openai' or 'anthropic')
        model: Optional model name override
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate

    Returns:
        Configured LLM provider instance

    Raises:
        LLMProviderError: If the provider cannot be created
    """
    provider_name = provider_name.lower()

    config = LLMConfig(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise LLMProviderError("OpenAI API key not configured")

        return OpenAIProvider(config, settings.openai_api_key)

    elif provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMProviderError("Anthropic API key not configured")

        return AnthropicProvider(config, settings.anthropic_api_key)

    else:
        raise LLMProviderError(f"Unknown provider: {provider_name}")


@lru_cache
def get_default_provider() -> LLMProvider:
    """
    Get the default LLM provider based on available API keys.

    Priority: Anthropic > OpenAI

    Returns:
        Default LLM provider instance

    Raises:
        LLMProviderError: If no provider can be configured
    """
    # Prefer Anthropic if available
    if settings.anthropic_api_key:
        logger.info("Using Anthropic as default LLM provider")
        return create_llm_provider("anthropic")

    # Fall back to OpenAI
    if settings.openai_api_key:
        logger.info("Using OpenAI as default LLM provider")
        return create_llm_provider("openai")

    raise LLMProviderError(
        "No LLM provider configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY."
    )


def get_available_providers() -> list[str]:
    """Get list of available providers based on configured API keys."""
    providers = []

    if settings.openai_api_key:
        providers.append("openai")

    if settings.anthropic_api_key:
        providers.append("anthropic")

    return providers
