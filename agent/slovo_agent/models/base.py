"""
Base Pydantic models for Slovo Agent Runtime.

All models are defined here to avoid circular imports and provide
a single source of truth for type definitions.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Intent Models
# =============================================================================

class IntentType(str, Enum):
    """Types of user intents."""
    
    QUESTION = "question"
    COMMAND = "command"
    CONVERSATION = "conversation"
    TOOL_REQUEST = "tool_request"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class Intent(BaseModel):
    """Parsed user intent."""
    
    type: IntentType
    text: str
    language: str = "en"
    entities: dict[str, Any] = {}
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    requires_tool: bool = False
    tool_hint: Optional[str] = None


# =============================================================================
# Plan Models
# =============================================================================

class StepType(str, Enum):
    """Types of execution steps."""
    
    LLM_RESPONSE = "llm_response"
    TOOL_EXECUTION = "tool_execution"
    TOOL_DISCOVERY = "tool_discovery"
    MEMORY_RETRIEVAL = "memory_retrieval"
    CLARIFICATION = "clarification"


class PlanStep(BaseModel):
    """A single step in an execution plan."""
    
    type: StepType
    description: str
    tool_name: Optional[str] = None
    tool_params: dict[str, Any] = {}
    depends_on: list[int] = []


class ExecutionPlan(BaseModel):
    """Complete execution plan for handling a user request."""
    
    intent: Intent
    steps: list["PlanStep"] = []
    requires_approval: bool = False
    estimated_complexity: str = "simple"
    requires_verification: bool = True
    requires_explanation: bool = True


# =============================================================================
# Execution Models
# =============================================================================

class StepResult(BaseModel):
    """Result of executing a single step."""
    
    step_index: int
    success: bool
    output: Any = None
    error: Optional[str] = None


class ExecutionResult(BaseModel):
    """Complete result of plan execution."""
    
    plan: ExecutionPlan
    success: bool
    step_results: list["StepResult"] = []
    final_output: Any = None
    error: Optional[str] = None


# =============================================================================
# Verification Models
# =============================================================================

class Verification(BaseModel):
    """Result of verifying execution output."""
    
    is_valid: bool
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    issues: list[str] = []
    suggestions: list[str] = []
    requires_correction: bool = False
    correction_hint: Optional[str] = None


# =============================================================================
# Explanation Models
# =============================================================================

class Explanation(BaseModel):
    """User-facing explanation of agent actions."""
    
    response: str
    reasoning: Optional[str] = None
    actions_taken: list[str] = []
    confidence_note: Optional[str] = None


# =============================================================================
# Orchestrator Models
# =============================================================================

class AgentResult(BaseModel):
    """Result from agent processing."""
    
    response: str
    reasoning: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# =============================================================================
# API Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str
    version: str
    uptime: float


class ChatRequest(BaseModel):
    """Chat request model."""
    
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    
    id: str
    response: str
    conversation_id: str
    reasoning: Optional[str] = None


class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    
    id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None
    reasoning: Optional[str] = None


class ConversationHistoryResponse(BaseModel):
    """Conversation history response model."""
    
    conversation_id: str
    messages: list["ConversationMessage"] = []


# =============================================================================
# Tool Models
# =============================================================================

class ToolManifest(BaseModel):
    """Tool manifest describing a tool's capabilities."""
    
    name: str
    version: str
    description: str
    permissions: list[str] = []
    parameters: dict[str, Any] = {}
