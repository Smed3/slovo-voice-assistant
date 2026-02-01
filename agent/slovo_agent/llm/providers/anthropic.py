"""
Anthropic LLM Provider implementation.

Provides integration with Anthropic's Claude models, including support for
structured outputs using tool use.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from slovo_agent.llm.base import LLMConfig, LLMMessage, LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider using the official Anthropic Python SDK."""

    def __init__(self, config: LLMConfig, api_key: str) -> None:
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=api_key, timeout=config.timeout)
        logger.info("Anthropic provider initialized", model=config.model)

    @property
    def name(self) -> str:
        return "anthropic"

    def _format_messages_for_anthropic(
        self,
        messages: list[LLMMessage],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Format messages for Anthropic's API.
        
        Anthropic requires system prompt to be separate from messages.
        """
        system_prompt = None
        formatted_messages: list[dict[str, str]] = []

        for msg in messages:
            if msg.role.value == "system":
                system_prompt = msg.content
            else:
                formatted_messages.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })

        return system_prompt, formatted_messages

    async def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse[Any]:
        """Generate a response using Anthropic's message API."""
        api_system, formatted_messages = self._format_messages_for_anthropic(messages)
        
        # Use provided system prompt or extracted one
        final_system = system_prompt or api_system

        logger.debug(
            "Generating Anthropic response",
            model=self.config.model,
            message_count=len(formatted_messages),
        )

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
        }

        # Only include parameters if explicitly set
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        else:
            # Anthropic requires max_tokens, use a sensible default
            kwargs["max_tokens"] = 4096
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            kwargs["top_p"] = self.config.top_p

        if final_system:
            kwargs["system"] = final_system

        response = await self.client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        usage: dict[str, int] = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

        logger.debug("Anthropic response generated", tokens=usage.get("total_tokens", 0))

        return LLMResponse(
            content=content,
            structured_output=None,
            model=response.model,
            usage=usage,
            finish_reason=response.stop_reason,
        )

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """Generate a structured response using Anthropic's tool use feature."""
        api_system, formatted_messages = self._format_messages_for_anthropic(messages)
        
        # Use provided system prompt or extracted one
        final_system = system_prompt or api_system

        # Build the tool schema from the Pydantic model
        schema = output_schema.model_json_schema()
        schema_name = output_schema.__name__

        # Define a tool that returns the structured output
        tool: dict[str, Any] = {
            "name": f"respond_with_{schema_name.lower()}",
            "description": f"Respond with a structured {schema_name} object",
            "input_schema": schema,
        }

        # Add instruction to system prompt
        schema_instruction = (
            f"\n\nYou must use the respond_with_{schema_name.lower()} tool to provide "
            f"your response in a structured format."
        )

        enhanced_system = (final_system or "You are a helpful assistant.") + schema_instruction

        logger.debug(
            "Generating structured Anthropic response",
            model=self.config.model,
            schema=schema_name,
        )

        # Build kwargs conditionally
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
            "system": enhanced_system,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": f"respond_with_{schema_name.lower()}"},
        }

        # Only include parameters if explicitly set
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        else:
            # Anthropic requires max_tokens, use a sensible default
            kwargs["max_tokens"] = 4096
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            kwargs["top_p"] = self.config.top_p

        response = await self.client.messages.create(**kwargs)

        usage: dict[str, int] = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

        # Extract the tool use result
        structured_output: T | None = None
        content = ""

        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
            elif hasattr(block, "input") and hasattr(block, "name"):
                # This is a tool use block
                try:
                    tool_input = block.input
                    structured_output = output_schema.model_validate(tool_input)
                    content = json.dumps(tool_input)
                except Exception as e:
                    logger.warning("Failed to parse structured output", error=str(e))

        logger.debug(
            "Structured Anthropic response generated",
            schema=schema_name,
            tokens=usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            structured_output=structured_output,
            model=response.model,
            usage=usage,
            finish_reason=response.stop_reason,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from Anthropic."""
        api_system, formatted_messages = self._format_messages_for_anthropic(messages)
        final_system = system_prompt or api_system

        logger.debug(
            "Streaming Anthropic response",
            model=self.config.model,
            message_count=len(formatted_messages),
        )

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }

        if final_system:
            kwargs["system"] = final_system

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
