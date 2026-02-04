"""
Memory Inspector API Routes for Slovo Agent Runtime.

Phase 3: Memory Inspector UI (Required)

API Endpoints:
- GET /memory?type=semantic - List memories
- GET /memory/{id} - Get memory detail
- PUT /memory/{id} - Update memory
- DELETE /memory/{id} - Delete memory
- POST /memory/reset - Full reset

All endpoints:
- Typed request/response
- No bulk unsafe deletes
- Confirmation flags required
"""

from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from slovo_agent.models import (
    MemoryDeleteRequest,
    MemoryDetailResponse,
    MemoryListRequest,
    MemoryListResponse,
    MemoryResetRequest,
    MemoryResetResponse,
    MemorySource,
    MemoryType,
    MemoryUpdateRequest,
    UserProfile,
)

if TYPE_CHECKING:
    from slovo_agent.memory import MemoryManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# =============================================================================
# Dependency for Memory Manager
# =============================================================================

# Will be set during app initialization
_memory_manager: "MemoryManager | None" = None


def set_memory_manager(manager: "MemoryManager") -> None:
    """Set the global memory manager (called during app init)."""
    global _memory_manager
    _memory_manager = manager


def get_memory_manager() -> "MemoryManager":
    """Get the memory manager dependency."""
    if _memory_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service not initialized",
        )
    return _memory_manager


# =============================================================================
# Memory List Endpoint
# =============================================================================


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    type: MemoryType | None = Query(default=None, description="Filter by memory type"),
    source: MemorySource | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    include_deleted: bool = Query(default=False, description="Include deleted entries"),
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> MemoryListResponse:
    """
    List memory entries for the Memory Inspector.

    Filter by type (semantic, episodic, preference) and source.
    Supports pagination with limit and offset.
    """
    logger.debug(
        "Listing memories",
        type=type.value if type else None,
        source=source.value if source else None,
        limit=limit,
        offset=offset,
    )

    request = MemoryListRequest(
        memory_type=type,
        source=source,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
    )

    return await manager.list_memories(request)


# =============================================================================
# Memory Detail Endpoint
# =============================================================================


@router.get("/{memory_id}", response_model=MemoryDetailResponse)
async def get_memory(
    memory_id: UUID,
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> MemoryDetailResponse:
    """
    Get detailed memory entry for viewing or editing.

    Returns full content and metadata for a specific memory entry.
    """
    logger.debug("Getting memory detail", memory_id=str(memory_id))

    detail = await manager.get_memory_detail(memory_id)

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return detail


# =============================================================================
# Memory Update Endpoint
# =============================================================================


@router.put("/{memory_id}", response_model=dict[str, bool])
async def update_memory(
    memory_id: UUID,
    update: MemoryUpdateRequest,
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> dict[str, bool]:
    """
    Update a memory entry.

    Allows editing content and confidence score.
    Note: Episodic logs are immutable and cannot be edited.
    """
    logger.info(
        "Updating memory",
        memory_id=str(memory_id),
        has_content=update.content is not None,
        has_confidence=update.confidence is not None,
    )

    success = await manager.update_memory(memory_id, update)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found or cannot be updated",
        )

    return {"success": True}


# =============================================================================
# Memory Delete Endpoint
# =============================================================================


@router.delete("/{memory_id}", response_model=dict[str, bool])
async def delete_memory(
    memory_id: UUID,
    request: MemoryDeleteRequest,
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> dict[str, bool]:
    """
    Delete a memory entry.

    Requires explicit confirmation (confirm=true) to delete.
    Performs soft-delete in metadata tracking.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion requires confirm=true",
        )

    logger.info("Deleting memory", memory_id=str(memory_id))

    success = await manager.delete_memory(memory_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return {"success": True}


# =============================================================================
# Memory Reset Endpoint
# =============================================================================


@router.post("/reset", response_model=MemoryResetResponse)
async def reset_memory(
    request: MemoryResetRequest,
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> MemoryResetResponse:
    """
    Perform full memory reset.

    CAUTION: This will delete ALL memory data.

    Reset must:
    1. Clear Redis (session data)
    2. Drop Qdrant collections (semantic memory)
    3. Truncate PostgreSQL tables (structured memory)

    Requires explicit confirmation (confirm_full_reset=true).
    Optionally preserves basic user profile settings.
    """
    if not request.confirm_full_reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full reset requires confirm_full_reset=true",
        )

    logger.warning(
        "Full memory reset requested",
        preserve_user_profile=request.preserve_user_profile,
    )

    return await manager.full_reset(request)


# =============================================================================
# User Profile Endpoints
# =============================================================================


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> UserProfile:
    """
    Get user profile with preferences.

    Returns language preferences, communication style, and memory settings.
    """
    return await manager.get_user_profile()


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    preferred_languages: list[str] | None = None,
    communication_style: str | None = None,
    privacy_level: str | None = None,
    memory_capture_enabled: bool | None = None,
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> UserProfile:
    """
    Update user profile settings.

    Allows setting:
    - Preferred languages
    - Communication style
    - Privacy level
    - Memory capture enabled/disabled
    """
    logger.info(
        "Updating user profile",
        languages=preferred_languages,
        style=communication_style,
        privacy=privacy_level,
        capture=memory_capture_enabled,
    )

    return await manager.update_user_profile(
        preferred_languages=preferred_languages,
        communication_style=communication_style,
        privacy_level=privacy_level,
        memory_capture_enabled=memory_capture_enabled,
    )


# =============================================================================
# Health Check Endpoint
# =============================================================================


@router.get("/health", response_model=dict[str, bool])
async def memory_health(
    manager: "MemoryManager" = Depends(get_memory_manager),  # type: ignore
) -> dict[str, bool]:
    """
    Check health of all memory services.

    Returns status of:
    - Redis (short-term memory)
    - Qdrant (semantic memory)
    - PostgreSQL (structured memory)
    """
    return await manager.health_check()
