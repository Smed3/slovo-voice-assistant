"""
Shared Pydantic models for Slovo Agent Runtime.

This module provides centralized model definitions to avoid circular imports
and ensure consistent typing across the agent system.
"""

from slovo_agent.models.base import (
    # Intent models
    IntentType,
    Intent,
    # Plan models
    StepType,
    PlanStep,
    ExecutionPlan,
    # Execution models
    StepResult,
    ExecutionResult,
    # Verification models
    Verification,
    # Explanation models
    Explanation,
    # Orchestrator models
    AgentResult,
    # API models
    HealthResponse,
    ChatRequest,
    ChatResponse,
    ConversationMessage,
    ConversationHistoryResponse,
    # Tool models
    ToolManifest,
)

__all__ = [
    # Intent models
    "IntentType",
    "Intent",
    # Plan models
    "StepType",
    "PlanStep",
    "ExecutionPlan",
    # Execution models
    "StepResult",
    "ExecutionResult",
    # Verification models
    "Verification",
    # Explanation models
    "Explanation",
    # Orchestrator models
    "AgentResult",
    # API models
    "HealthResponse",
    "ChatRequest",
    "ChatResponse",
    "ConversationMessage",
    "ConversationHistoryResponse",
    # Tool models
    "ToolManifest",
]
