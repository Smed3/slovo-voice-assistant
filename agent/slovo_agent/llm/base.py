"""
Base LLM provider interface and types.

Defines the abstract interface that all LLM providers must implement,
along with common data structures for messages and responses.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessage(BaseModel):
    """A single message in an LLM conversation."""

    role: MessageRole
    content: str


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""

    model: str
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    timeout: float = Field(default=60.0, ge=1.0)


class LLMResponse(BaseModel, Generic[T]):
    """Response from an LLM provider."""

    content: str
    structured_output: T | None = None
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str | None = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers (OpenAI, Anthropic, etc.) must implement this interface
    to ensure consistent behavior across the agent runtime.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> "LLMResponse[Any]":
        """
        Generate a response from the LLM.

        Args:
            messages: List of conversation messages
            system_prompt: Optional system prompt to prepend

        Returns:
            LLM response with generated content
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """
        Generate a structured response that conforms to a Pydantic schema.

        Args:
            messages: List of conversation messages
            output_schema: Pydantic model class for the expected output
            system_prompt: Optional system prompt to prepend

        Returns:
            LLM response with structured output parsed into the schema
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream a response from the LLM.

        Args:
            messages: List of conversation messages
            system_prompt: Optional system prompt to prepend

        Yields:
            Chunks of the response as they become available
        """
        ...
        # Yield statement to make this an async generator
        yield ""  # type: ignore

    def _build_messages(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        """Build message list with optional system prompt."""
        result: list[dict[str, str]] = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            result.append({"role": msg.role.value, "content": msg.content})

        return result
