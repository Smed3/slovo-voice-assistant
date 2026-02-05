"""
Memory Manager for Slovo Agent Runtime.

Phase 3: Central memory management service
- Coordinates all memory operations
- Manages full reset logic
- Provides unified interface for agents and API
"""

from uuid import UUID

import structlog
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from slovo_agent.memory.encryption import (
    EncryptionService,
    get_encryption_service,
    initialize_encryption,
)
from slovo_agent.memory.postgres_repository import PostgresRepository
from slovo_agent.memory.qdrant_repository import QdrantRepository
from slovo_agent.memory.redis_repository import RedisRepository
from slovo_agent.memory.retrieval import EmbeddingFunction, MemoryRetrievalPipeline
from slovo_agent.memory.writer import MemoryWriteService
from slovo_agent.models import (
    ConversationTurn,
    MemoryContext,
    MemoryDetailResponse,
    MemoryListItem,
    MemoryListRequest,
    MemoryListResponse,
    MemoryResetRequest,
    MemoryResetResponse,
    MemoryRetrievalRequest,
    MemoryType,
    MemoryUpdateRequest,
    MemoryWriteRequest,
    MemoryWriteResult,
    StoreLocation,
    UserProfile,
    VerifierMemoryApproval,
)

logger = structlog.get_logger(__name__)


class MemoryManager:
    """
    Central manager for all memory operations.

    Provides:
    - Unified interface for memory retrieval and writes
    - Memory Inspector operations
    - Full reset logic
    - Health checks
    """

    def __init__(
        self,
        redis: RedisRepository,
        qdrant: QdrantRepository,
        postgres: PostgresRepository,
        encryption: EncryptionService | None = None,
    ) -> None:
        """
        Initialize memory manager.

        Args:
            redis: Redis repository
            qdrant: Qdrant repository
            postgres: PostgreSQL repository
            encryption: Optional encryption service
        """
        self._redis = redis
        self._qdrant = qdrant
        self._postgres = postgres
        self._encryption = encryption or get_encryption_service()

        # Initialize pipeline and writer
        self._retrieval = MemoryRetrievalPipeline(redis, qdrant, postgres)
        self._writer = MemoryWriteService(qdrant, postgres)

        self._embedding_fn: EmbeddingFunction | None = None
        logger.info("Memory manager initialized")

    def set_embedding_function(self, fn: EmbeddingFunction) -> None:
        """Set embedding function for semantic operations."""
        self._embedding_fn = fn
        self._retrieval.set_embedding_function(fn)
        self._writer.set_embedding_function(fn)

    # =========================================================================
    # Memory Retrieval (Pre-LLM)
    # =========================================================================

    async def retrieve_context(
        self,
        user_message: str,
        conversation_id: str | None = None,
        token_limit: int = 2000,
    ) -> MemoryContext:
        """
        Retrieve memory context for LLM prompt injection.

        This is the main entry point for pre-LLM memory retrieval.

        Args:
            user_message: User's message for semantic search
            conversation_id: Current conversation ID
            token_limit: Maximum tokens for memory context

        Returns:
            Aggregated memory context
        """
        request = MemoryRetrievalRequest(
            user_message=user_message,
            conversation_id=conversation_id,
            token_limit=token_limit,
        )
        return await self._retrieval.retrieve(request)

    # =========================================================================
    # Short-Term Memory (Conversation Turns)
    # =========================================================================

    async def store_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Store a conversation turn in short-term memory (Redis).

        Args:
            conversation_id: Conversation identifier
            role: 'user' or 'assistant'
            content: Message content
        """
        from typing import Literal, cast

        from slovo_agent.models import ConversationTurn

        # Cast to literal type (runtime validated by Pydantic)
        typed_role = cast(Literal["user", "assistant"], role)
        turn = ConversationTurn(role=typed_role, content=content)
        await self._redis.add_turn(
            conversation_id=conversation_id,
            turn=turn,
        )
        logger.debug(
            "Turn stored",
            conversation_id=conversation_id,
            role=role,
            content_length=len(content),
        )

    async def get_recent_turns(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Get recent turns from short-term memory.

        Args:
            conversation_id: Conversation identifier
            limit: Maximum turns to return

        Returns:
            List of turns with 'role' and 'content'
        """
        turns = await self._redis.get_recent_turns(conversation_id, limit)
        return [{"role": t.role, "content": t.content} for t in turns]

    async def get_conversation_turns(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[ConversationTurn]:
        """
        Get full conversation turns from short-term memory.

        This method returns complete ConversationTurn objects including
        IDs, timestamps, and all metadata, suitable for API responses.

        Args:
            conversation_id: Conversation identifier
            limit: Maximum turns to return (default: 100)

        Returns:
            List of ConversationTurn objects
        """
        return await self._redis.get_recent_turns(conversation_id, limit)

    # =========================================================================
    # Memory Writes (Requires Verifier Approval)
    # =========================================================================

    async def write_memory(
        self,
        request: MemoryWriteRequest,
        approval: VerifierMemoryApproval,
    ) -> MemoryWriteResult:
        """
        Write memory with verifier approval.

        Args:
            request: Write request
            approval: Verifier approval decision

        Returns:
            Write result
        """
        return await self._writer.write(request, approval)

    async def write_memory_direct(
        self,
        request: MemoryWriteRequest,
    ) -> MemoryWriteResult:
        """
        Write memory directly (for user edits via Memory Inspector).

        Args:
            request: Write request

        Returns:
            Write result
        """
        return await self._writer.write_without_approval(request)

    # =========================================================================
    # User Profile
    # =========================================================================

    async def get_user_profile(self) -> UserProfile:
        """Get user profile."""
        return await self._postgres.get_user_profile()

    async def update_user_profile(
        self,
        preferred_languages: list[str] | None = None,
        communication_style: str | None = None,
        privacy_level: str | None = None,
        memory_capture_enabled: bool | None = None,
    ) -> UserProfile:
        """Update user profile."""
        return await self._postgres.update_user_profile(
            preferred_languages=preferred_languages,
            communication_style=communication_style,
            privacy_level=privacy_level,
            memory_capture_enabled=memory_capture_enabled,
        )

    # =========================================================================
    # Memory Inspector Operations
    # =========================================================================

    async def list_memories(
        self,
        request: MemoryListRequest,
    ) -> MemoryListResponse:
        """
        List memory entries for Memory Inspector.

        Args:
            request: List request with filters

        Returns:
            Paginated list of memory entries
        """
        metadata_list, total = await self._postgres.list_memory_metadata(
            memory_type=request.memory_type,
            source=request.source,
            include_deleted=request.include_deleted,
            limit=request.limit,
            offset=request.offset,
        )

        items = [
            MemoryListItem(
                id=m.id,
                memory_type=m.memory_type,
                summary=m.summary,
                source=m.source,
                confidence=m.confidence,
                created_at=m.created_at,
                is_deleted=m.is_deleted,
            )
            for m in metadata_list
        ]

        return MemoryListResponse(
            items=items,
            total_count=total,
            limit=request.limit,
            offset=request.offset,
        )

    async def get_memory_detail(
        self,
        memory_id: UUID,
    ) -> MemoryDetailResponse | None:
        """
        Get detailed memory entry for viewing/editing.

        Args:
            memory_id: Memory ID

        Returns:
            Detailed memory entry or None
        """
        # Get metadata first
        metadata = await self._postgres.get_memory_metadata(memory_id)
        if metadata is None:
            return None

        # Fetch actual content based on store location
        content = ""
        extra_metadata: dict[str, str] = {}

        if metadata.store_location == StoreLocation.QDRANT:
            entry = await self._qdrant.get(memory_id)
            if entry:
                content = entry.metadata.summary
                if entry.metadata.conversation_id:
                    extra_metadata["conversation_id"] = entry.metadata.conversation_id
                if entry.metadata.tool_name:
                    extra_metadata["tool_name"] = entry.metadata.tool_name

        elif metadata.store_location == StoreLocation.POSTGRES:
            if metadata.memory_type == MemoryType.PREFERENCE:
                # Get preference by iterating (could be optimized)
                prefs = await self._postgres.list_preferences()
                for pref in prefs:
                    if pref.id == memory_id:
                        content = f"{pref.key}: {pref.value}"
                        extra_metadata["preference_key"] = pref.key
                        break

            elif metadata.memory_type == MemoryType.EPISODIC:
                log = await self._postgres.get_episodic_log(memory_id)
                if log:
                    content = log.summary
                    extra_metadata["agent"] = log.agent
                    extra_metadata["action_type"] = log.action_type.value

        return MemoryDetailResponse(
            id=metadata.id,
            memory_type=metadata.memory_type,
            content=content,
            summary=metadata.summary,
            source=metadata.source,
            confidence=metadata.confidence,
            store_location=metadata.store_location,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            metadata=extra_metadata,
        )

    async def update_memory(
        self,
        memory_id: UUID,
        update: MemoryUpdateRequest,
    ) -> bool:
        """
        Update a memory entry.

        Args:
            memory_id: Memory ID
            update: Update request

        Returns:
            True if updated
        """
        metadata = await self._postgres.get_memory_metadata(memory_id)
        if metadata is None:
            return False

        # Update in appropriate store
        if metadata.store_location == StoreLocation.QDRANT:
            success = await self._qdrant.update(
                memory_id,
                summary=update.content,
                confidence=update.confidence,
            )
            if success and update.content:
                # Update metadata summary
                metadata.summary = update.content[:200]
                await self._postgres.track_memory(metadata)
            return success

        elif metadata.store_location == StoreLocation.POSTGRES:
            if metadata.memory_type == MemoryType.PREFERENCE:
                if update.content:
                    # Parse key:value
                    if ":" in update.content:
                        key, value = update.content.split(":", 1)
                        await self._postgres.set_preference(
                            key=key.strip(),
                            value=value.strip(),
                            source=metadata.source,  # type: ignore
                            confidence=update.confidence or metadata.confidence,
                        )
                        return True
            # Episodic logs are immutable

        return False

    async def delete_memory(self, memory_id: UUID) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        metadata = await self._postgres.get_memory_metadata(memory_id)
        if metadata is None:
            return False

        # Delete from appropriate store
        if metadata.store_location == StoreLocation.QDRANT:
            await self._qdrant.delete(memory_id)

        elif metadata.store_location == StoreLocation.POSTGRES:
            if metadata.memory_type == MemoryType.PREFERENCE:
                # Get preference key and delete
                detail = await self.get_memory_detail(memory_id)
                if detail and "preference_key" in detail.metadata:
                    await self._postgres.delete_preference(detail.metadata["preference_key"])

        # Soft-delete in metadata
        return await self._postgres.soft_delete_memory(memory_id)

    # =========================================================================
    # Full Reset Logic
    # =========================================================================

    async def full_reset(
        self,
        request: MemoryResetRequest,
    ) -> MemoryResetResponse:
        """
        Execute full memory reset.

        Reset must:
        1. Stop agent execution (caller responsibility)
        2. Clear Redis
        3. Drop Qdrant collections
        4. Truncate Postgres tables
        5. Restart agent runtime (caller responsibility)

        Args:
            request: Reset request with confirmation

        Returns:
            Reset result
        """
        if not request.confirm_full_reset:
            return MemoryResetResponse(
                success=False,
                redis_cleared=False,
                qdrant_cleared=False,
                postgres_cleared=False,
                error="Reset not confirmed",
            )

        logger.warning("Starting full memory reset")

        redis_cleared = False
        qdrant_cleared = False
        postgres_cleared = False
        errors: list[str] = []

        # 1. Clear Redis
        try:
            await self._redis.clear_all()
            redis_cleared = True
            logger.info("Redis cleared")
        except Exception as e:
            errors.append(f"Redis: {e}")
            logger.error("Failed to clear Redis", error=str(e))

        # 2. Clear Qdrant
        try:
            await self._qdrant.clear_all()
            qdrant_cleared = True
            logger.info("Qdrant cleared")
        except Exception as e:
            errors.append(f"Qdrant: {e}")
            logger.error("Failed to clear Qdrant", error=str(e))

        # 3. Clear PostgreSQL
        try:
            await self._postgres.clear_all(
                preserve_profile=request.preserve_user_profile
            )
            postgres_cleared = True
            logger.info(
                "PostgreSQL cleared",
                preserve_profile=request.preserve_user_profile,
            )
        except Exception as e:
            errors.append(f"PostgreSQL: {e}")
            logger.error("Failed to clear PostgreSQL", error=str(e))

        success = redis_cleared and qdrant_cleared and postgres_cleared
        error = "; ".join(errors) if errors else None

        if success:
            logger.warning("Full memory reset completed successfully")
        else:
            logger.error("Full memory reset completed with errors", errors=errors)

        return MemoryResetResponse(
            success=success,
            redis_cleared=redis_cleared,
            qdrant_cleared=qdrant_cleared,
            postgres_cleared=postgres_cleared,
            error=error,
        )

    # =========================================================================
    # Health Checks
    # =========================================================================

    async def health_check(self) -> dict[str, bool]:
        """
        Check health of all memory services.

        Returns:
            Dict with service health status
        """
        return {
            "redis": await self._redis.health_check(),
            "qdrant": await self._qdrant.health_check(),
            "postgres": await self._postgres.health_check(),
        }


# =============================================================================
# Factory Function
# =============================================================================


async def _create_openai_embedding_function() -> EmbeddingFunction | None:
    """Create an embedding function using OpenAI if available."""
    try:
        from slovo_agent.config import settings

        if not settings.openai_api_key:
            logger.warning("No OpenAI API key - semantic memory disabled")
            return None

        from openai import APIConnectionError, APIError, AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        async def embed(text: str) -> list[float]:
            """Generate embedding for text using OpenAI."""
            try:
                response = await client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                )
                return response.data[0].embedding
            except APIConnectionError as e:
                # Network connectivity issues - log and return empty vector
                # This allows the system to gracefully degrade without semantic memory
                logger.warning(
                    "OpenAI API connection failed - semantic memory unavailable",
                    error=str(e),
                )
                raise  # Re-raise so caller can handle gracefully
            except APIError as e:
                logger.warning("OpenAI API error", error=str(e))
                raise

        logger.info("OpenAI embedding function initialized")
        return embed
    except Exception as e:
        logger.warning("Failed to create embedding function", error=str(e))
        return None


async def create_memory_manager(
    redis_url: str,
    qdrant_url: str,
    database_url: str,
    encryption_password: str | None = None,
) -> MemoryManager:
    """
    Create and initialize memory manager with all dependencies.

    Args:
        redis_url: Redis connection URL
        qdrant_url: Qdrant connection URL
        database_url: PostgreSQL connection URL
        encryption_password: Optional encryption password

    Returns:
        Configured memory manager
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    # Initialize encryption
    encryption = initialize_encryption(password=encryption_password)

    # Create Redis client
    redis_client = Redis.from_url(redis_url)
    redis_repo = RedisRepository(redis_client)

    # Create Qdrant client
    qdrant_client = AsyncQdrantClient(url=qdrant_url)
    qdrant_repo = QdrantRepository(qdrant_client, encryption)

    # Create PostgreSQL connection
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    postgres_repo = PostgresRepository(session_factory, encryption)

    manager = MemoryManager(
        redis=redis_repo,
        qdrant=qdrant_repo,
        postgres=postgres_repo,
        encryption=encryption,
    )

    # Initialize embedding function for semantic memory
    embedding_fn = await _create_openai_embedding_function()
    if embedding_fn:
        manager.set_embedding_function(embedding_fn)

    return manager
