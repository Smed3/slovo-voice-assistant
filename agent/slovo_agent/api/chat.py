"""
Chat API endpoints.
"""

import uuid
from typing import TYPE_CHECKING, AsyncGenerator, Optional

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
_orchestrator: Optional[AgentOrchestrator] = None
_memory_manager: "Optional[MemoryManager]" = None


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
    
    # TODO: Implement actual conversation retrieval from memory
    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=[],
    )
