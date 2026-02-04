"""
Memory Domain Models for Slovo Agent Runtime.

All memory objects are strictly typed Pydantic models.
No untyped dicts crossing boundaries.

Phase 3: Memory System Implementation
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class MemoryType(str, Enum):
    """Types of memory entries."""

    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PREFERENCE = "preference"


class MemorySource(str, Enum):
    """Source of memory entry creation."""

    CONVERSATION = "conversation"
    TOOL = "tool"
    USER_EDIT = "user_edit"
    VERIFIER = "verifier"


class StoreLocation(str, Enum):
    """Physical storage location of memory."""

    QDRANT = "qdrant"
    POSTGRES = "postgres"
    REDIS = "redis"


class PreferenceSource(str, Enum):
    """Source of preference creation."""

    USER_EDIT = "user_edit"
    VERIFIER_APPROVED = "verifier_approved"
    SYSTEM_DEFAULT = "system_default"


# =============================================================================
# Base Memory Models
# =============================================================================


class MemoryEntry(BaseModel):
    """Base memory entry with required fields."""

    id: UUID = Field(default_factory=uuid4)
    type: MemoryType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(ge=0.0, le=1.0)


class MemoryMetadata(BaseModel):
    """Metadata for tracking memory entries across stores."""

    id: UUID = Field(default_factory=uuid4)
    memory_type: MemoryType
    store_location: StoreLocation
    summary: str = Field(min_length=1, max_length=1000)
    source: MemorySource
    confidence: float = Field(ge=0.0, le=1.0)
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Semantic Memory Models (Qdrant)
# =============================================================================


class SemanticMetadata(BaseModel):
    """Typed metadata for Qdrant semantic memory vectors."""

    source: MemorySource
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=500)
    conversation_id: str | None = None
    tool_name: str | None = None


class SemanticMemoryEntry(MemoryEntry):
    """Semantic memory entry stored in Qdrant."""

    type: Literal[MemoryType.SEMANTIC] = MemoryType.SEMANTIC
    vector: list[float] = Field(min_length=1)
    metadata: SemanticMetadata
    reference_id: UUID = Field(default_factory=uuid4)


class SemanticSearchResult(BaseModel):
    """Result from semantic memory search."""

    id: UUID
    score: float = Field(ge=0.0, le=1.0)
    metadata: SemanticMetadata


# =============================================================================
# Episodic Memory Models (PostgreSQL)
# =============================================================================


class EpisodicActionType(str, Enum):
    """Types of episodic actions to log."""

    INTENT_PARSED = "intent_parsed"
    PLAN_CREATED = "plan_created"
    TOOL_EXECUTED = "tool_executed"
    VERIFICATION_COMPLETED = "verification_completed"
    EXPLANATION_GENERATED = "explanation_generated"
    MEMORY_WRITTEN = "memory_written"
    ERROR_OCCURRED = "error_occurred"
    SELF_CORRECTION = "self_correction"


class EpisodicLogMetadata(BaseModel):
    """Typed metadata for episodic log entries."""

    conversation_id: str | None = None
    step_index: int | None = None
    tool_name: str | None = None
    error_type: str | None = None
    correction_reason: str | None = None


class EpisodicLogEntry(MemoryEntry):
    """Episodic log entry stored in PostgreSQL."""

    type: Literal[MemoryType.EPISODIC] = MemoryType.EPISODIC
    agent: str = Field(min_length=1, max_length=100)
    action_type: EpisodicActionType
    summary: str = Field(min_length=1, max_length=2000)
    metadata: EpisodicLogMetadata = Field(default_factory=EpisodicLogMetadata)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Preference Models (PostgreSQL)
# =============================================================================


class UserPreference(MemoryEntry):
    """User preference stored in PostgreSQL."""

    type: Literal[MemoryType.PREFERENCE] = MemoryType.PREFERENCE
    key: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=10000)
    source: PreferenceSource
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    """User profile with core preferences."""

    id: int = 1
    preferred_languages: list[str] = Field(default_factory=lambda: ["en"])
    communication_style: str | None = "friendly"
    privacy_level: str = "standard"
    memory_capture_enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Short-Term Memory Models (Redis)
# =============================================================================


class ConversationTurn(BaseModel):
    """A single turn in the conversation stored in Redis."""

    id: UUID = Field(default_factory=uuid4)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent_type: str | None = None
    confidence: float | None = None


class SessionContext(BaseModel):
    """Current session context stored in Redis."""

    session_id: UUID = Field(default_factory=uuid4)
    conversation_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    active_plan_id: str | None = None
    agent_state: dict[str, str] = Field(default_factory=dict)
    tool_outputs: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: int = 7200  # 2 hours default


class WorkingMemoryState(BaseModel):
    """Complete working memory state from Redis."""

    session: SessionContext | None = None
    recent_turns: list[ConversationTurn] = Field(default_factory=list)
    pending_tool_outputs: dict[str, str] = Field(default_factory=dict)


# =============================================================================
# Memory Retrieval Models
# =============================================================================


class MemoryContext(BaseModel):
    """Aggregated memory context for LLM prompt injection.

    This is the final output of the memory retrieval pipeline.
    Contains summarized, minimal context - never raw database content.
    """

    user_profile_summary: str = Field(default="", max_length=500)
    recent_conversation_summary: str = Field(default="", max_length=1000)
    relevant_memories_summary: str = Field(default="", max_length=1500)
    episodic_context_summary: str = Field(default="", max_length=500)
    total_token_estimate: int = Field(default=0, ge=0)


class MemoryRetrievalRequest(BaseModel):
    """Request for memory retrieval pipeline."""

    user_message: str = Field(min_length=1)
    conversation_id: str | None = None
    max_semantic_results: int = Field(default=5, ge=1, le=20)
    max_episodic_results: int = Field(default=3, ge=1, le=10)
    token_limit: int = Field(default=2000, ge=100, le=8000)


# =============================================================================
# Memory Write Models
# =============================================================================


class MemoryWriteRequest(BaseModel):
    """Request to write memory (requires verifier approval)."""

    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=10000)
    source: MemorySource
    confidence: float = Field(ge=0.0, le=1.0)
    conversation_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class MemoryWriteResult(BaseModel):
    """Result of a memory write operation."""

    success: bool
    memory_id: UUID | None = None
    memory_type: MemoryType | None = None
    error: str | None = None
    verifier_approved: bool = False


class VerifierMemoryApproval(BaseModel):
    """Verifier decision on whether to write memory."""

    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=500)
    adjusted_content: str | None = None


# =============================================================================
# Memory Inspector Models (API)
# =============================================================================


class MemoryListRequest(BaseModel):
    """Request to list memory entries."""

    memory_type: MemoryType | None = None
    source: MemorySource | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    include_deleted: bool = False


class MemoryListItem(BaseModel):
    """Single item in memory list response."""

    id: UUID
    memory_type: MemoryType
    summary: str
    source: MemorySource
    confidence: float
    created_at: datetime
    is_deleted: bool = False


class MemoryListResponse(BaseModel):
    """Response for memory listing."""

    items: list[MemoryListItem]
    total_count: int
    limit: int
    offset: int


class MemoryDetailResponse(BaseModel):
    """Detailed memory entry for viewing/editing."""

    id: UUID
    memory_type: MemoryType
    content: str
    summary: str
    source: MemorySource
    confidence: float
    store_location: StoreLocation
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)


class MemoryUpdateRequest(BaseModel):
    """Request to update a memory entry."""

    content: str | None = Field(default=None, max_length=10000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryDeleteRequest(BaseModel):
    """Request to delete a memory entry."""

    confirm: bool = Field(
        description="Must be True to confirm deletion"
    )


class MemoryResetRequest(BaseModel):
    """Request to reset all memory."""

    confirm_full_reset: bool = Field(
        description="Must be True to confirm full memory reset"
    )
    preserve_user_profile: bool = Field(
        default=True,
        description="Whether to preserve basic user profile settings"
    )


class MemoryResetResponse(BaseModel):
    """Response for memory reset operation."""

    success: bool
    redis_cleared: bool
    qdrant_cleared: bool
    postgres_cleared: bool
    error: str | None = None
