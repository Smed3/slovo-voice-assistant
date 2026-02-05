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

from slovo_agent.models.memory import (
    # Enums
    MemoryType,
    MemorySource,
    StoreLocation,
    PreferenceSource,
    EpisodicActionType,
    # Base models
    MemoryEntry,
    MemoryMetadata,
    # Semantic memory
    SemanticMetadata,
    SemanticMemoryEntry,
    SemanticSearchResult,
    # Episodic memory
    EpisodicLogMetadata,
    EpisodicLogEntry,
    # Preferences
    UserPreference,
    UserProfile,
    # Short-term memory
    ConversationTurn,
    SessionContext,
    WorkingMemoryState,
    # Retrieval
    MemoryContext,
    MemoryRetrievalRequest,
    # Write
    MemoryWriteRequest,
    MemoryWriteResult,
    VerifierMemoryApproval,
    # Inspector API
    MemoryListRequest,
    MemoryListItem,
    MemoryListResponse,
    MemoryDetailResponse,
    MemoryUpdateRequest,
    MemoryDeleteRequest,
    MemoryResetRequest,
    MemoryResetResponse,
)

from slovo_agent.models.tools import (
    # Enums
    ToolStatus,
    ToolSourceType,
    PermissionType,
    ExecutionStatus,
    DiscoveryStatus,
    # Manifest models
    ToolCapability,
    ToolManifestDB,
    ToolManifestCreate,
    ToolManifestUpdate,
    # Permission models
    ToolPermissionDB,
    ToolPermissionCreate,
    ToolPermissionSet,
    # Execution models
    ToolExecutionLogDB,
    ToolExecutionCreate,
    ToolExecutionUpdate,
    # State models
    ToolStateDB,
    ToolStateCreate,
    ToolStateUpdate,
    # Volume models
    ToolVolumeDB,
    ToolVolumeCreate,
    # Discovery models
    ToolDiscoveryQueueDB,
    ToolDiscoveryRequest,
    ToolDiscoveryUpdate,
    # API response models
    ToolInfo,
    ToolDetail,
    ToolExecutionResult,
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
    # Memory models - Enums
    "MemoryType",
    "MemorySource",
    "StoreLocation",
    "PreferenceSource",
    "EpisodicActionType",
    # Memory models - Base
    "MemoryEntry",
    "MemoryMetadata",
    # Memory models - Semantic
    "SemanticMetadata",
    "SemanticMemoryEntry",
    "SemanticSearchResult",
    # Memory models - Episodic
    "EpisodicLogMetadata",
    "EpisodicLogEntry",
    # Memory models - Preferences
    "UserPreference",
    "UserProfile",
    # Memory models - Short-term
    "ConversationTurn",
    "SessionContext",
    "WorkingMemoryState",
    # Memory models - Retrieval
    "MemoryContext",
    "MemoryRetrievalRequest",
    # Memory models - Write
    "MemoryWriteRequest",
    "MemoryWriteResult",
    "VerifierMemoryApproval",
    # Memory models - Inspector API
    "MemoryListRequest",
    "MemoryListItem",
    "MemoryListResponse",
    "MemoryDetailResponse",
    "MemoryUpdateRequest",
    "MemoryDeleteRequest",
    "MemoryResetRequest",
    "MemoryResetResponse",
    # Tool models - Enums
    "ToolStatus",
    "ToolSourceType",
    "PermissionType",
    "ExecutionStatus",
    "DiscoveryStatus",
    # Tool models - Manifest
    "ToolCapability",
    "ToolManifestDB",
    "ToolManifestCreate",
    "ToolManifestUpdate",
    # Tool models - Permission
    "ToolPermissionDB",
    "ToolPermissionCreate",
    "ToolPermissionSet",
    # Tool models - Execution
    "ToolExecutionLogDB",
    "ToolExecutionCreate",
    "ToolExecutionUpdate",
    # Tool models - State
    "ToolStateDB",
    "ToolStateCreate",
    "ToolStateUpdate",
    # Tool models - Volume
    "ToolVolumeDB",
    "ToolVolumeCreate",
    # Tool models - Discovery
    "ToolDiscoveryQueueDB",
    "ToolDiscoveryRequest",
    "ToolDiscoveryUpdate",
    # Tool models - API response
    "ToolInfo",
    "ToolDetail",
    "ToolExecutionResult",
]
