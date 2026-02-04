"""
Memory Write Service for Slovo Agent Runtime.

Phase 3: Memory write rules (Critical)
- Memory writes are NOT automatic
- A memory entry is written only if:
  1. Verifier agent approves
  2. Confidence score >= threshold
  3. User has not disabled memory capture

Write paths:
- Semantic -> Qdrant
- Preferences -> Postgres
- Reasoning -> Episodic log
"""

from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

import structlog

from slovo_agent.memory.postgres_repository import PostgresRepository
from slovo_agent.memory.qdrant_repository import QdrantRepository
from slovo_agent.models import (
    EpisodicActionType,
    EpisodicLogEntry,
    EpisodicLogMetadata,
    MemoryMetadata,
    MemorySource,
    MemoryType,
    MemoryWriteRequest,
    MemoryWriteResult,
    PreferenceSource,
    SemanticMemoryEntry,
    SemanticMetadata,
    StoreLocation,
    UserProfile,
    VerifierMemoryApproval,
)

logger = structlog.get_logger(__name__)

# Minimum confidence threshold for memory writes
MIN_CONFIDENCE_THRESHOLD: Final[float] = 0.7


class MemoryWriteService:
    """
    Service for writing memories with verifier approval.

    Memory writes require:
    1. Verifier agent approval
    2. Confidence >= threshold (0.7)
    3. User memory capture enabled
    """

    def __init__(
        self,
        qdrant: QdrantRepository,
        postgres: PostgresRepository,
        embedding_fn: "EmbeddingFunction | None" = None,
        confidence_threshold: float = MIN_CONFIDENCE_THRESHOLD,
    ) -> None:
        """
        Initialize memory write service.

        Args:
            qdrant: Qdrant repository for semantic memory
            postgres: PostgreSQL repository for structured memory
            embedding_fn: Function to generate embeddings
            confidence_threshold: Minimum confidence for writes
        """
        self._qdrant = qdrant
        self._postgres = postgres
        self._embedding_fn = embedding_fn
        self._confidence_threshold = confidence_threshold
        logger.info(
            "Memory write service initialized",
            confidence_threshold=confidence_threshold,
        )

    def set_embedding_function(self, fn: "EmbeddingFunction") -> None:
        """Set the embedding function for semantic memory."""
        self._embedding_fn = fn

    async def write(
        self,
        request: MemoryWriteRequest,
        approval: VerifierMemoryApproval,
    ) -> MemoryWriteResult:
        """
        Write memory with verifier approval.

        Args:
            request: Memory write request
            approval: Verifier approval decision

        Returns:
            Write result
        """
        logger.debug(
            "Processing memory write request",
            memory_type=request.memory_type.value,
            approved=approval.approved,
        )

        # Check verifier approval
        if not approval.approved:
            logger.info(
                "Memory write rejected by verifier",
                reason=approval.reason,
            )
            return MemoryWriteResult(
                success=False,
                error=f"Verifier rejected: {approval.reason}",
                verifier_approved=False,
            )

        # Check confidence threshold
        effective_confidence = min(request.confidence, approval.confidence)
        if effective_confidence < self._confidence_threshold:
            logger.info(
                "Memory write rejected: low confidence",
                confidence=effective_confidence,
                threshold=self._confidence_threshold,
            )
            return MemoryWriteResult(
                success=False,
                error=f"Confidence {effective_confidence:.2f} below threshold {self._confidence_threshold:.2f}",
                verifier_approved=True,
            )

        # Check user preference
        try:
            profile = await self._postgres.get_user_profile()
            if not profile.memory_capture_enabled:
                logger.info("Memory write skipped: user disabled memory capture")
                return MemoryWriteResult(
                    success=False,
                    error="Memory capture is disabled by user",
                    verifier_approved=True,
                )
        except Exception as e:
            logger.warning("Failed to check user profile", error=str(e))
            # Proceed if we can't check (fail open for local-only system)

        # Use adjusted content if provided by verifier
        content = approval.adjusted_content or request.content

        # Route to appropriate store
        if request.memory_type == MemoryType.SEMANTIC:
            return await self._write_semantic(
                content=content,
                source=request.source,
                confidence=effective_confidence,
                conversation_id=request.conversation_id,
                metadata=request.metadata,
            )
        elif request.memory_type == MemoryType.PREFERENCE:
            return await self._write_preference(
                content=content,
                source=request.source,
                confidence=effective_confidence,
                metadata=request.metadata,
            )
        elif request.memory_type == MemoryType.EPISODIC:
            return await self._write_episodic(
                content=content,
                source=request.source,
                confidence=effective_confidence,
                conversation_id=request.conversation_id,
                metadata=request.metadata,
            )
        else:
            return MemoryWriteResult(
                success=False,
                error=f"Unknown memory type: {request.memory_type}",
                verifier_approved=True,
            )

    async def _write_semantic(
        self,
        content: str,
        source: MemorySource,
        confidence: float,
        conversation_id: str | None,
        metadata: dict[str, str],
    ) -> MemoryWriteResult:
        """Write to semantic memory (Qdrant)."""
        if not self._embedding_fn:
            return MemoryWriteResult(
                success=False,
                error="Embedding function not configured",
                verifier_approved=True,
            )

        try:
            # Generate embedding
            vector = await self._embedding_fn(content)

            memory_id = uuid4()
            entry = SemanticMemoryEntry(
                id=memory_id,
                vector=vector,
                metadata=SemanticMetadata(
                    source=source,
                    confidence=confidence,
                    summary=content[:500],  # Limit summary length
                    conversation_id=conversation_id,
                    tool_name=metadata.get("tool_name"),
                ),
                confidence=confidence,
            )

            await self._qdrant.store(entry)

            # Track in metadata table
            await self._postgres.track_memory(
                MemoryMetadata(
                    id=memory_id,
                    memory_type=MemoryType.SEMANTIC,
                    store_location=StoreLocation.QDRANT,
                    summary=content[:200],
                    source=source,
                    confidence=confidence,
                )
            )

            logger.info(
                "Semantic memory written",
                memory_id=str(memory_id),
                source=source.value,
            )

            return MemoryWriteResult(
                success=True,
                memory_id=memory_id,
                memory_type=MemoryType.SEMANTIC,
                verifier_approved=True,
            )
        except Exception as e:
            logger.error("Failed to write semantic memory", error=str(e))
            return MemoryWriteResult(
                success=False,
                error=str(e),
                verifier_approved=True,
            )

    async def _write_preference(
        self,
        content: str,
        source: MemorySource,
        confidence: float,
        metadata: dict[str, str],
    ) -> MemoryWriteResult:
        """Write to preference store (PostgreSQL)."""
        try:
            # Extract key from metadata or content
            key = metadata.get("preference_key")
            if not key:
                # Try to parse key:value format
                if ":" in content:
                    key, value = content.split(":", 1)
                    key = key.strip()
                    content = value.strip()
                else:
                    return MemoryWriteResult(
                        success=False,
                        error="Preference key not provided",
                        verifier_approved=True,
                    )

            # Map source to preference source
            pref_source = PreferenceSource.VERIFIER_APPROVED
            if source == MemorySource.USER_EDIT:
                pref_source = PreferenceSource.USER_EDIT

            preference = await self._postgres.set_preference(
                key=key,
                value=content,
                source=pref_source,
                confidence=confidence,
            )

            # Track in metadata table
            await self._postgres.track_memory(
                MemoryMetadata(
                    id=preference.id,
                    memory_type=MemoryType.PREFERENCE,
                    store_location=StoreLocation.POSTGRES,
                    summary=f"{key}: {content[:100]}",
                    source=source,
                    confidence=confidence,
                )
            )

            logger.info(
                "Preference written",
                preference_id=str(preference.id),
                key=key,
            )

            return MemoryWriteResult(
                success=True,
                memory_id=preference.id,
                memory_type=MemoryType.PREFERENCE,
                verifier_approved=True,
            )
        except Exception as e:
            logger.error("Failed to write preference", error=str(e))
            return MemoryWriteResult(
                success=False,
                error=str(e),
                verifier_approved=True,
            )

    async def _write_episodic(
        self,
        content: str,
        source: MemorySource,
        confidence: float,
        conversation_id: str | None,
        metadata: dict[str, str],
    ) -> MemoryWriteResult:
        """Write to episodic log (PostgreSQL)."""
        try:
            memory_id = uuid4()

            # Determine action type from metadata
            action_type_str = metadata.get("action_type", "memory_written")
            try:
                action_type = EpisodicActionType(action_type_str)
            except ValueError:
                action_type = EpisodicActionType.MEMORY_WRITTEN

            agent = metadata.get("agent", "unknown")

            entry = EpisodicLogEntry(
                id=memory_id,
                agent=agent,
                action_type=action_type,
                summary=content,
                confidence=confidence,
                metadata=EpisodicLogMetadata(
                    conversation_id=conversation_id,
                    step_index=int(metadata["step_index"]) if "step_index" in metadata else None,
                    tool_name=metadata.get("tool_name"),
                    error_type=metadata.get("error_type"),
                    correction_reason=metadata.get("correction_reason"),
                ),
            )

            await self._postgres.add_episodic_log(entry)

            # Track in metadata table
            await self._postgres.track_memory(
                MemoryMetadata(
                    id=memory_id,
                    memory_type=MemoryType.EPISODIC,
                    store_location=StoreLocation.POSTGRES,
                    summary=content[:200],
                    source=source,
                    confidence=confidence,
                )
            )

            logger.info(
                "Episodic log written",
                log_id=str(memory_id),
                agent=agent,
                action_type=action_type.value,
            )

            return MemoryWriteResult(
                success=True,
                memory_id=memory_id,
                memory_type=MemoryType.EPISODIC,
                verifier_approved=True,
            )
        except Exception as e:
            logger.error("Failed to write episodic log", error=str(e))
            return MemoryWriteResult(
                success=False,
                error=str(e),
                verifier_approved=True,
            )

    async def write_without_approval(
        self,
        request: MemoryWriteRequest,
    ) -> MemoryWriteResult:
        """
        Write memory without verifier approval (for system-level writes only).

        USE WITH CAUTION - only for:
        - User-initiated edits through Memory Inspector
        - System-level logs

        Args:
            request: Memory write request

        Returns:
            Write result
        """
        # Create auto-approval
        approval = VerifierMemoryApproval(
            approved=True,
            confidence=request.confidence,
            reason="System-level write (no verifier required)",
        )

        return await self.write(request, approval)


# Type alias for embedding function
from typing import Awaitable, Callable

EmbeddingFunction = Callable[[str], Awaitable[list[float]]]
