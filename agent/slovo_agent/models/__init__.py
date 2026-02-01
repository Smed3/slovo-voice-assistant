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

from slovo_agent.models.reasoning import (
    # Uncertainty & Clarification
    UncertaintyLevel,
    ClarificationReason,
    ClarificationRequest,
    # Intent Analysis
    DetectedLanguage,
    ExtractedEntity,
    IntentAnalysis,
    # Planning
    PlannedAction,
    RiskAssessment,
    ExecutionPlanAnalysis,
    # Verification
    VerificationIssue,
    VerificationAnalysis,
    # Response Generation
    ResponseTone,
    ExplanationDetail,
    ResponseGeneration,
    # Context
    ConversationContext,
    AgentState,
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
    # Reasoning models - Uncertainty & Clarification
    "UncertaintyLevel",
    "ClarificationReason",
    "ClarificationRequest",
    # Reasoning models - Intent Analysis
    "DetectedLanguage",
    "ExtractedEntity",
    "IntentAnalysis",
    # Reasoning models - Planning
    "PlannedAction",
    "RiskAssessment",
    "ExecutionPlanAnalysis",
    # Reasoning models - Verification
    "VerificationIssue",
    "VerificationAnalysis",
    # Reasoning models - Response Generation
    "ResponseTone",
    "ExplanationDetail",
    "ResponseGeneration",
    # Reasoning models - Context
    "ConversationContext",
    "AgentState",
]
