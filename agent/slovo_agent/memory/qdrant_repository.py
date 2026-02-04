"""
Qdrant Repository for Long-Term Semantic Memory.

Phase 3: Semantic recall only
- Local Qdrant instance
- Single collection: semantic_memory
- Fixed embedding model
- Encryption at repository boundary
"""

from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from slovo_agent.memory.encryption import EncryptionService, get_encryption_service
from slovo_agent.models import (
    MemorySource,
    SemanticMemoryEntry,
    SemanticMetadata,
    SemanticSearchResult,
)

logger = structlog.get_logger(__name__)

# Collection configuration
COLLECTION_NAME: Final[str] = "semantic_memory"
VECTOR_SIZE: Final[int] = 1536  # OpenAI ada-002 / text-embedding-3-small


class QdrantRepository:
    """
    Repository for long-term semantic memory in Qdrant.

    Used for:
    - Conversation embeddings
    - Learned user preferences (semantic search)
    - Tool usage patterns

    Security:
    - Encryption at repository boundary
    - Never store raw text blobs longer than needed
    - Never store secrets or credentials
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        encryption: EncryptionService | None = None,
        vector_size: int = VECTOR_SIZE,
    ) -> None:
        """
        Initialize Qdrant repository.

        Args:
            client: Async Qdrant client
            encryption: Optional encryption service (auto-resolved if None)
            vector_size: Vector dimension size
        """
        self._client = client
        self._encryption = encryption or get_encryption_service()
        self._vector_size = vector_size
        self._collection_initialized = False
        logger.info("Qdrant repository initialized", vector_size=vector_size)

    async def ensure_collection(self) -> None:
        """Ensure the semantic_memory collection exists."""
        if self._collection_initialized:
            return

        collections = await self._client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if COLLECTION_NAME not in collection_names:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created semantic_memory collection")
        
        self._collection_initialized = True

    # =========================================================================
    # Memory Operations
    # =========================================================================

    async def store(self, entry: SemanticMemoryEntry) -> SemanticMemoryEntry:
        """
        Store a semantic memory entry.

        Content is encrypted before storage.

        Args:
            entry: Memory entry to store

        Returns:
            Stored entry with ID
        """
        await self.ensure_collection()

        # Encrypt the summary for storage
        encrypted_summary = self._encryption.encrypt(entry.metadata.summary)

        # Prepare payload (metadata)
        payload = {
            "source": entry.metadata.source.value,
            "timestamp": entry.metadata.timestamp.isoformat(),
            "confidence": entry.metadata.confidence,
            "summary_encrypted": encrypted_summary,
            "conversation_id": entry.metadata.conversation_id,
            "tool_name": entry.metadata.tool_name,
            "reference_id": str(entry.reference_id),
            "created_at": entry.created_at.isoformat(),
        }

        point = PointStruct(
            id=str(entry.id),
            vector=entry.vector,
            payload=payload,
        )

        await self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )

        logger.debug(
            "Semantic memory stored",
            memory_id=str(entry.id),
            source=entry.metadata.source.value,
        )
        return entry

    async def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        source_filter: MemorySource | None = None,
        min_confidence: float = 0.0,
    ) -> list[SemanticSearchResult]:
        """
        Search for similar semantic memories.

        Args:
            query_vector: Query embedding vector
            limit: Maximum results to return
            source_filter: Optional filter by source
            min_confidence: Minimum confidence threshold

        Returns:
            List of search results with decrypted summaries
        """
        await self.ensure_collection()

        # Build filter conditions
        filter_conditions: list[FieldCondition] = []

        if source_filter:
            filter_conditions.append(
                FieldCondition(
                    key="source",
                    match=MatchValue(value=source_filter.value),
                )
            )

        if min_confidence > 0:
            filter_conditions.append(
                FieldCondition(
                    key="confidence",
                    range={"gte": min_confidence},
                )
            )

        search_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Use query_points (qdrant-client v1.16+) instead of deprecated search()
        response = await self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True,
        )

        search_results: list[SemanticSearchResult] = []
        for result in response.points:
            try:
                # Decrypt summary
                encrypted_summary = result.payload.get("summary_encrypted", "")  # type: ignore
                summary = self._encryption.decrypt(encrypted_summary) if encrypted_summary else ""

                metadata = SemanticMetadata(
                    source=MemorySource(result.payload.get("source", "conversation")),  # type: ignore
                    timestamp=datetime.fromisoformat(result.payload.get("timestamp", datetime.utcnow().isoformat())),  # type: ignore
                    confidence=float(result.payload.get("confidence", 0.5)),  # type: ignore
                    summary=summary,
                    conversation_id=result.payload.get("conversation_id"),  # type: ignore
                    tool_name=result.payload.get("tool_name"),  # type: ignore
                )

                search_results.append(
                    SemanticSearchResult(
                        id=UUID(str(result.id)),
                        score=result.score,
                        metadata=metadata,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to parse search result",
                    error=str(e),
                    result_id=str(result.id),
                )

        return search_results

    async def get(self, memory_id: UUID) -> SemanticMemoryEntry | None:
        """
        Get a specific semantic memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory entry or None if not found
        """
        await self.ensure_collection()

        results = await self._client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[str(memory_id)],
            with_vectors=True,
        )

        if not results:
            return None

        point = results[0]
        payload = point.payload or {}

        # Decrypt summary
        encrypted_summary = payload.get("summary_encrypted", "")
        summary = self._encryption.decrypt(encrypted_summary) if encrypted_summary else ""

        metadata = SemanticMetadata(
            source=MemorySource(payload.get("source", "conversation")),
            timestamp=datetime.fromisoformat(payload.get("timestamp", datetime.utcnow().isoformat())),
            confidence=float(payload.get("confidence", 0.5)),
            summary=summary,
            conversation_id=payload.get("conversation_id"),
            tool_name=payload.get("tool_name"),
        )

        return SemanticMemoryEntry(
            id=UUID(str(point.id)),
            vector=point.vector if isinstance(point.vector, list) else [],  # type: ignore
            metadata=metadata,
            reference_id=UUID(payload.get("reference_id", str(uuid4()))),
            created_at=datetime.fromisoformat(payload.get("created_at", datetime.utcnow().isoformat())),
            confidence=metadata.confidence,
        )

    async def update(
        self,
        memory_id: UUID,
        summary: str | None = None,
        confidence: float | None = None,
    ) -> bool:
        """
        Update a semantic memory entry.

        Args:
            memory_id: Memory ID
            summary: New summary (will be encrypted)
            confidence: New confidence score

        Returns:
            True if updated
        """
        await self.ensure_collection()

        payload_updates: dict[str, str | float] = {}

        if summary is not None:
            payload_updates["summary_encrypted"] = self._encryption.encrypt(summary)

        if confidence is not None:
            payload_updates["confidence"] = confidence

        if not payload_updates:
            return False

        await self._client.set_payload(
            collection_name=COLLECTION_NAME,
            payload=payload_updates,
            points=[str(memory_id)],
        )

        logger.debug("Semantic memory updated", memory_id=str(memory_id))
        return True

    async def delete(self, memory_id: UUID) -> bool:
        """
        Delete a semantic memory entry.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        await self.ensure_collection()

        await self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(memory_id)]),
        )

        logger.debug("Semantic memory deleted", memory_id=str(memory_id))
        return True

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SemanticSearchResult], int]:
        """
        List all semantic memories (for Memory Inspector).

        Args:
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            Tuple of (results, total_count)
        """
        await self.ensure_collection()

        # Get collection info for total count
        collection_info = await self._client.get_collection(COLLECTION_NAME)
        total_count = collection_info.points_count or 0

        # Scroll through all points
        records, _ = await self._client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            offset=offset,
            with_vectors=False,
        )

        results: list[SemanticSearchResult] = []
        for record in records:
            payload = record.payload or {}

            try:
                encrypted_summary = payload.get("summary_encrypted", "")
                summary = self._encryption.decrypt(encrypted_summary) if encrypted_summary else ""

                metadata = SemanticMetadata(
                    source=MemorySource(payload.get("source", "conversation")),
                    timestamp=datetime.fromisoformat(payload.get("timestamp", datetime.utcnow().isoformat())),
                    confidence=float(payload.get("confidence", 0.5)),
                    summary=summary,
                    conversation_id=payload.get("conversation_id"),
                    tool_name=payload.get("tool_name"),
                )

                results.append(
                    SemanticSearchResult(
                        id=UUID(str(record.id)),
                        score=1.0,  # Not a search, so score is 1.0
                        metadata=metadata,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to parse record",
                    error=str(e),
                    record_id=str(record.id),
                )

        return results, total_count

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def clear_all(self) -> bool:
        """
        Clear all semantic memories (for full reset).

        Returns:
            True if cleared
        """
        try:
            # Delete and recreate collection
            await self._client.delete_collection(COLLECTION_NAME)
            self._collection_initialized = False
            await self.ensure_collection()

            logger.info("Qdrant collection cleared and recreated")
            return True
        except Exception as e:
            logger.error("Failed to clear Qdrant", error=str(e))
            return False

    async def health_check(self) -> bool:
        """
        Check Qdrant connection health.

        Returns:
            True if healthy
        """
        try:
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.error("Qdrant health check failed", error=str(e))
            return False
