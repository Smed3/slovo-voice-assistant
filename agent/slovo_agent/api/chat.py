"""
Chat API endpoints.
"""

import uuid
from typing import AsyncGenerator, Optional

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from slovo_agent.agents.orchestrator import AgentOrchestrator

logger = structlog.get_logger()
router = APIRouter()

# Global orchestrator instance (will be properly initialized in lifespan)
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the agent orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


class ChatRequest(BaseModel):
    """Chat request model."""
    
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = Field(default=None)


class ChatResponse(BaseModel):
    """Chat response model."""
    
    id: str
    response: str
    conversation_id: str
    reasoning: Optional[str] = None


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


class ConversationHistoryResponse(BaseModel):
    """Conversation history response model."""
    
    conversation_id: str
    messages: list[dict]


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
