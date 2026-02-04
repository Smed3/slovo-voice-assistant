"""
OpenAI LLM Provider implementation.

Provides integration with OpenAI's GPT models, including support for
structured outputs using function calling.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from slovo_agent.llm.base import LLMConfig, LLMMessage, LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using the official OpenAI Python SDK."""

    def __init__(self, config: LLMConfig, api_key: str) -> None:
        super().__init__(config)
        self.client = AsyncOpenAI(api_key=api_key, timeout=config.timeout)
        logger.info("OpenAI provider initialized", model=config.model)

    @property
    def name(self) -> str:
        return "openai"

    def _build_request_args(
        self,
        formatted_messages: list[dict[str, str]],
        **extra_args: Any,
    ) -> dict[str, Any]:
        """Build request arguments, only including explicitly set parameters."""
        args: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
        }

        # Only include parameters if explicitly set
        if self.config.max_tokens is not None:
            args["max_tokens"] = self.config.max_tokens
        if self.config.temperature is not None:
            args["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            args["top_p"] = self.config.top_p

        # Add any extra arguments
        args.update(extra_args)
        return args

    async def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse[Any]:
        """Generate a response using OpenAI's chat completion API."""
        formatted_messages = self._build_messages(messages, system_prompt)

        logger.debug(
            "Generating OpenAI response",
            model=self.config.model,
            message_count=len(formatted_messages),
        )

        request_args = self._build_request_args(formatted_messages)
        response = await self.client.chat.completions.create(**request_args)

        choice = response.choices[0]
        content = choice.message.content or ""

        usage: dict[str, int] = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        logger.debug("OpenAI response generated", tokens=usage.get("total_tokens", 0))

        return LLMResponse(
            content=content,
            structured_output=None,
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
        )

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """Generate a structured response using OpenAI's function calling."""
        formatted_messages = self._build_messages(messages, system_prompt)

        # Build the function schema from the Pydantic model
        schema = output_schema.model_json_schema()
        schema_name = output_schema.__name__

        # Add instruction to system prompt for structured output
        # Include full schema for nested objects, but with clear instructions
        schema_instruction = (
            f"\n\n**OUTPUT FORMAT REQUIREMENT**\n"
            f"You MUST respond with a JSON object that conforms to the following schema.\n"
            f"The schema below describes the STRUCTURE your response must follow.\n"
            f"Do NOT return the schema itself - return actual DATA that fits this structure.\n\n"
            f"Schema:\n```json\n{json.dumps(schema, indent=2)}\n```\n\n"
            f"Remember: Output a JSON object with real values, not the schema definition."
        )

        if system_prompt:
            enhanced_system = system_prompt + schema_instruction
        else:
            enhanced_system = f"You are a helpful assistant.{schema_instruction}"

        # Update the system message
        for msg in formatted_messages:
            if msg["role"] == "system":
                msg["content"] = enhanced_system
                break
        else:
            formatted_messages.insert(0, {"role": "system", "content": enhanced_system})

        logger.debug(
            "Generating structured OpenAI response",
            model=self.config.model,
            schema=schema_name,
        )

        request_args = self._build_request_args(
            formatted_messages,
            response_format={"type": "json_object"},
        )
        response = await self.client.chat.completions.create(**request_args)

        choice = response.choices[0]
        content = choice.message.content or "{}"

        usage: dict[str, int] = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Parse the structured output
        try:
            parsed_data = json.loads(content)
            structured_output: T | None = output_schema.model_validate(parsed_data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse structured output", error=str(e))
            # Return with None structured output on parse failure
            return LLMResponse(
                content=content,
                structured_output=None,
                model=response.model,
                usage=usage,
                finish_reason=choice.finish_reason,
            )

        logger.debug(
            "Structured OpenAI response generated",
            schema=schema_name,
            tokens=usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            structured_output=structured_output,
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from OpenAI."""
        formatted_messages = self._build_messages(messages, system_prompt)

        logger.debug(
            "Streaming OpenAI response",
            model=self.config.model,
            message_count=len(formatted_messages),
        )

        request_args = self._build_request_args(formatted_messages, stream=True)
        stream = await self.client.chat.completions.create(**request_args)

        async for chunk in stream:  # type: ignore
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
