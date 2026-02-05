"""
Chat API endpoints.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from slovo_agent.agents.orchestrator import AgentOrchestrator
from slovo_agent.models import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
)

if TYPE_CHECKING:
    from slovo_agent.memory import MemoryManager

logger = structlog.get_logger(__name__)
router = APIRouter()

# Global orchestrator instance (will be properly initialized in lifespan)
_orchestrator: AgentOrchestrator | None = None
_memory_manager: "MemoryManager | None" = None


def set_chat_memory_manager(manager: "MemoryManager") -> None:
    """Set the memory manager for chat (called during app init)."""
    global _memory_manager, _orchestrator
    _memory_manager = manager
    # Also update the orchestrator if it exists
    if _orchestrator is not None:
        _orchestrator.set_memory_manager(manager)


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the agent orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(memory_manager=_memory_manager)
    return _orchestrator


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a chat message and receive a response.
    """
    logger.info("Chat request received", message_length=len(request.message))

    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Get orchestrator and process message
    orchestrator = get_orchestrator()
    result = await orchestrator.process_message(
        message=request.message,
        conversation_id=conversation_id,
    )

    response_id = str(uuid.uuid4())

    logger.info("Chat response generated", response_id=response_id)

    return ChatResponse(
        id=response_id,
        response=result.response,
        conversation_id=conversation_id,
        reasoning=result.reasoning,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Stream a chat response for long-running queries.
    """
    logger.info("Chat stream request received", message_length=len(request.message))

    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    async def generate() -> AsyncGenerator[str, None]:
        orchestrator = get_orchestrator()
        async for chunk in orchestrator.process_message_stream(
            message=request.message,
            conversation_id=conversation_id,
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.get("/conversation/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(conversation_id: str) -> ConversationHistoryResponse:
    """
    Get conversation history by ID.
    """
    logger.info("Fetching conversation", conversation_id=conversation_id)

    # Check if memory manager is available
    if _memory_manager is None:
        logger.warning("Memory manager not available", conversation_id=conversation_id)
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[],
        )

    try:
        # Get full conversation turns from memory manager
        turns = await _memory_manager.get_conversation_turns(
            conversation_id=conversation_id,
            limit=100,  # Get up to 100 recent messages
        )

        # Convert ConversationTurn objects to ConversationMessage format
        from slovo_agent.models import ConversationMessage
        messages = [
            ConversationMessage(
                id=str(turn.id),
                role=turn.role,
                content=turn.content,
                timestamp=turn.timestamp.isoformat() if turn.timestamp else None,
                reasoning=None,  # Reasoning is not stored in turns
            )
            for turn in turns
        ]

        logger.info(
            "Conversation retrieved",
            conversation_id=conversation_id,
            message_count=len(messages),
        )

        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=messages,
        )
    except Exception as e:
        logger.error(
            "Failed to retrieve conversation",
            conversation_id=conversation_id,
            error=str(e),
        )
        # Return empty messages on error to avoid breaking the API
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[],
        )
