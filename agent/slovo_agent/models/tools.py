"""
Tool models for Phase 4: Autonomous Tooling.

These models define the structure for tool manifests, permissions,
execution logs, and state management.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Tool Status and Types
# =============================================================================


class ToolStatus(str, Enum):
    """Tool lifecycle status."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"


class ToolSourceType(str, Enum):
    """Source of tool manifest."""

    LOCAL = "local"  # Local manifest file
    OPENAPI_URL = "openapi_url"  # OpenAPI spec from URL
    DISCOVERED = "discovered"  # Discovered via API search


class PermissionType(str, Enum):
    """Types of tool permissions."""

    INTERNET_ACCESS = "internet_access"
    STORAGE = "storage"
    CPU_LIMIT = "cpu_limit"
    MEMORY_LIMIT = "memory_limit"


class ExecutionStatus(str, Enum):
    """Tool execution status."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# =============================================================================
# Tool Manifest Models
# =============================================================================


class ToolCapability(BaseModel):
    """A specific capability provided by a tool."""

    name: str = Field(description="Capability name")
    description: str = Field(description="What this capability does")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters schema"
    )


class ToolManifestDB(BaseModel):
    """Tool manifest as stored in database."""

    id: UUID
    name: str
    version: str
    description: str
    source_type: ToolSourceType
    source_location: str
    status: ToolStatus
    openapi_spec: dict[str, Any] | None = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    # Execution configuration
    execution_type: str | None = Field(
        default="docker", description="Execution type: docker or wasm"
    )
    docker_image: str | None = Field(
        default=None, description="Docker image name for execution"
    )
    docker_entrypoint: str | list[str] | None = Field(
        default=None, description="Docker entrypoint command (string or list)"
    )
    execution_timeout: int | None = Field(
        default=30, description="Execution timeout in seconds"
    )
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    revoked_at: datetime | None = None

    class Config:
        from_attributes = True


class ToolManifestCreate(BaseModel):
    """Model for creating a new tool manifest."""

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1)
    source_type: ToolSourceType
    source_location: str = Field(min_length=1)
    openapi_spec: dict[str, Any] | None = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    # Execution configuration
    execution_type: str | None = Field(
        default="docker", description="Execution type: docker or wasm"
    )
    docker_image: str | None = Field(
        default=None, description="Docker image name for execution"
    )
    docker_entrypoint: str | list[str] | None = Field(
        default=None, description="Docker entrypoint command (string or list)"
    )
    execution_timeout: int | None = Field(
        default=30, description="Execution timeout in seconds"
    )


class ToolManifestUpdate(BaseModel):
    """Model for updating a tool manifest."""

    version: str | None = None
    description: str | None = None
    status: ToolStatus | None = None
    openapi_spec: dict[str, Any] | None = None
    capabilities: list[dict[str, Any]] | None = None
    parameters_schema: dict[str, Any] | None = None
    # Execution configuration
    execution_type: str | None = None
    docker_image: str | None = None
    docker_entrypoint: str | list[str] | None = None
    execution_timeout: int | None = None


# =============================================================================
# Tool Permission Models
# =============================================================================


class ToolPermissionDB(BaseModel):
    """Tool permission as stored in database."""

    id: UUID
    tool_id: UUID
    permission_type: PermissionType
    permission_value: str
    granted_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class ToolPermissionCreate(BaseModel):
    """Model for creating a tool permission."""

    tool_id: UUID
    permission_type: PermissionType
    permission_value: str
    granted_by: str = "user"


class ToolPermissionSet(BaseModel):
    """Complete set of permissions for a tool."""

    internet_access: bool = False
    storage_quota_mb: int = 100
    cpu_limit_percent: int = 50
    memory_limit_mb: int = 512


# =============================================================================
# Tool Execution Models
# =============================================================================


class ToolExecutionLogDB(BaseModel):
    """Tool execution log as stored in database."""

    id: UUID
    tool_id: UUID
    conversation_id: str | None = None
    turn_id: str | None = None
    input_params: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    error_message: str | None = None
    exit_code: int | None = None
    cpu_usage_ms: int | None = None
    memory_peak_mb: int | None = None
    container_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ToolExecutionCreate(BaseModel):
    """Model for creating a tool execution log."""

    tool_id: UUID
    conversation_id: str | None = None
    turn_id: str | None = None
    input_params: dict[str, Any]


class ToolExecutionUpdate(BaseModel):
    """Model for updating a tool execution log."""

    completed_at: datetime | None = None
    duration_ms: int | None = None
    status: ExecutionStatus | None = None
    output: dict[str, Any] | None = None
    error_message: str | None = None
    exit_code: int | None = None
    cpu_usage_ms: int | None = None
    memory_peak_mb: int | None = None
    container_id: str | None = None


# =============================================================================
# Tool State Models
# =============================================================================


class ToolStateDB(BaseModel):
    """Tool state as stored in database."""

    id: UUID
    tool_id: UUID
    state_key: str
    state_value: dict[str, Any]
    size_bytes: int
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ToolStateCreate(BaseModel):
    """Model for creating tool state."""

    tool_id: UUID
    state_key: str
    state_value: dict[str, Any]
    size_bytes: int


class ToolStateUpdate(BaseModel):
    """Model for updating tool state."""

    state_value: dict[str, Any]
    size_bytes: int


# =============================================================================
# Tool Volume Models
# =============================================================================


class ToolVolumeDB(BaseModel):
    """Tool volume as stored in database."""

    id: UUID
    tool_id: UUID
    volume_name: str
    mount_path: str
    size_mb: int | None = None
    quota_mb: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ToolVolumeCreate(BaseModel):
    """Model for creating a tool volume."""

    tool_id: UUID
    volume_name: str
    mount_path: str = "/data"
    quota_mb: int = 1024


# =============================================================================
# Tool Discovery Models
# =============================================================================


class DiscoveryStatus(str, Enum):
    """Tool discovery status."""

    PENDING = "pending"
    SEARCHING = "searching"
    FOUND = "found"
    FAILED = "failed"
    REJECTED = "rejected"


class ToolDiscoveryQueueDB(BaseModel):
    """Tool discovery queue entry as stored in database."""

    id: UUID
    capability_description: str
    requested_by: str
    search_query: str | None = None
    status: DiscoveryStatus
    discovered_apis: dict[str, Any] | None = None
    selected_api: str | None = None
    tool_manifest_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class ToolDiscoveryRequest(BaseModel):
    """Request to discover a new tool."""

    capability_description: str = Field(min_length=1)
    requested_by: str = "planner"
    search_query: str | None = None


class ToolDiscoveryUpdate(BaseModel):
    """Model for updating a tool discovery request."""

    status: DiscoveryStatus | None = None
    discovered_apis: dict[str, Any] | None = None
    selected_api: str | None = None
    tool_manifest_id: UUID | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


# =============================================================================
# API Response Models
# =============================================================================


class ToolInfo(BaseModel):
    """Lightweight tool information for API responses."""

    id: UUID
    name: str
    version: str
    description: str
    status: ToolStatus
    source_type: ToolSourceType
    capabilities_count: int = 0
    created_at: datetime


class ToolDetail(BaseModel):
    """Detailed tool information with permissions and capabilities."""

    manifest: ToolManifestDB
    permissions: list[ToolPermissionDB]
    volumes: list[ToolVolumeDB]
    recent_executions: list[ToolExecutionLogDB] = Field(default_factory=list)


class ToolExecutionResult(BaseModel):
    """Result of a tool execution."""

    execution_id: UUID
    tool_name: str
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
