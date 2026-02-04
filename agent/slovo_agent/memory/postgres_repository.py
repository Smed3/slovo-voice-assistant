"""
PostgreSQL Repository for Structured Memory.

Phase 3: Deterministic facts & preferences
- Local-only Postgres instance
- Single user (no auth tables, no multi-tenant logic)
- Encryption at repository boundary
"""

from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from slovo_agent.memory.encryption import EncryptionService, get_encryption_service
from slovo_agent.models import (
    EpisodicActionType,
    EpisodicLogEntry,
    EpisodicLogMetadata,
    MemoryMetadata,
    MemorySource,
    MemoryType,
    PreferenceSource,
    StoreLocation,
    UserPreference,
    UserProfile,
)

logger = structlog.get_logger(__name__)

# Single user ID (enforced by CHECK constraint)
SINGLE_USER_ID: Final[int] = 1


class PostgresRepository:
    """
    Repository for structured memory in PostgreSQL.

    Used for:
    - User profile and preferences
    - Episodic logs
    - Memory metadata tracking

    Security:
    - Encryption at repository boundary
    - Single user only
    - No auth tables, no multi-tenant logic
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        encryption: EncryptionService | None = None,
    ) -> None:
        """
        Initialize PostgreSQL repository.

        Args:
            session_factory: SQLAlchemy async session factory
            encryption: Optional encryption service (auto-resolved if None)
        """
        self._session_factory = session_factory
        self._encryption = encryption or get_encryption_service()
        logger.info("PostgreSQL repository initialized")

    # =========================================================================
    # User Profile
    # =========================================================================

    async def get_user_profile(self) -> UserProfile:
        """
        Get the single user profile.

        Returns:
            User profile (creates default if not exists)
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, preferred_languages, communication_style,
                           privacy_level, memory_capture_enabled,
                           created_at, updated_at
                    FROM user_profile
                    WHERE id = :id
                """),
                {"id": SINGLE_USER_ID},
            )
            row = result.fetchone()

            if row is None:
                # Create default profile
                return await self._create_default_profile(session)

            return UserProfile(
                id=row[0],
                preferred_languages=row[1] or ["en"],
                communication_style=row[2],
                privacy_level=row[3] or "standard",
                memory_capture_enabled=row[4] if row[4] is not None else True,
                created_at=row[5],
                updated_at=row[6],
            )

    async def _create_default_profile(self, session: AsyncSession) -> UserProfile:
        """Create default user profile."""
        await session.execute(
            text("""
                INSERT INTO user_profile (id, preferred_languages, communication_style, 
                                          privacy_level, memory_capture_enabled, created_at, updated_at)
                VALUES (:id, :languages, :style, :privacy, :capture, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": SINGLE_USER_ID,
                "languages": ["en"],
                "style": "friendly",
                "privacy": "standard",
                "capture": True,
            },
        )
        await session.commit()

        return UserProfile(
            id=SINGLE_USER_ID,
            preferred_languages=["en"],
            communication_style="friendly",
            privacy_level="standard",
            memory_capture_enabled=True,
        )

    async def update_user_profile(
        self,
        preferred_languages: list[str] | None = None,
        communication_style: str | None = None,
        privacy_level: str | None = None,
        memory_capture_enabled: bool | None = None,
    ) -> UserProfile:
        """
        Update user profile.

        Args:
            preferred_languages: New language preferences
            communication_style: New communication style
            privacy_level: New privacy level
            memory_capture_enabled: Enable/disable memory capture

        Returns:
            Updated profile
        """
        async with self._session_factory() as session:
            # Build update parts
            updates: list[str] = []
            params: dict[str, str | list[str] | bool] = {"id": SINGLE_USER_ID}

            if preferred_languages is not None:
                updates.append("preferred_languages = :languages")
                params["languages"] = preferred_languages

            if communication_style is not None:
                updates.append("communication_style = :style")
                params["style"] = communication_style

            if privacy_level is not None:
                updates.append("privacy_level = :privacy")
                params["privacy"] = privacy_level

            if memory_capture_enabled is not None:
                updates.append("memory_capture_enabled = :capture")
                params["capture"] = memory_capture_enabled

            if updates:
                updates.append("updated_at = NOW()")
                query = f"UPDATE user_profile SET {', '.join(updates)} WHERE id = :id"
                await session.execute(text(query), params)
                await session.commit()

            return await self.get_user_profile()

    # =========================================================================
    # User Preferences
    # =========================================================================

    async def get_preference(self, key: str) -> UserPreference | None:
        """
        Get a user preference by key.

        Args:
            key: Preference key

        Returns:
            Preference or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, key, value, source, confidence, created_at, updated_at
                    FROM user_preference
                    WHERE key = :key
                """),
                {"key": key},
            )
            row = result.fetchone()

            if row is None:
                return None

            # Decrypt value
            decrypted_value = self._encryption.decrypt(row[2])

            return UserPreference(
                id=row[0],
                key=row[1],
                value=decrypted_value,
                source=PreferenceSource(row[3]),
                confidence=row[4],
                created_at=row[5],
                updated_at=row[6],
            )

    async def set_preference(
        self,
        key: str,
        value: str,
        source: PreferenceSource,
        confidence: float,
    ) -> UserPreference:
        """
        Set or update a user preference.

        Args:
            key: Preference key
            value: Preference value (will be encrypted)
            source: Source of the preference
            confidence: Confidence score

        Returns:
            Created/updated preference
        """
        async with self._session_factory() as session:
            preference_id = uuid4()
            encrypted_value = self._encryption.encrypt(value)

            await session.execute(
                text("""
                    INSERT INTO user_preference (id, key, value, source, confidence, created_at, updated_at)
                    VALUES (:id, :key, :value, :source, :confidence, NOW(), NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = :value,
                        source = :source,
                        confidence = :confidence,
                        updated_at = NOW()
                """),
                {
                    "id": preference_id,
                    "key": key,
                    "value": encrypted_value,
                    "source": source.value,
                    "confidence": confidence,
                },
            )
            await session.commit()

            return UserPreference(
                id=preference_id,
                key=key,
                value=value,  # Return decrypted
                source=source,
                confidence=confidence,
            )

    async def delete_preference(self, key: str) -> bool:
        """
        Delete a user preference.

        Args:
            key: Preference key

        Returns:
            True if deleted
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("DELETE FROM user_preference WHERE key = :key"),
                {"key": key},
            )
            await session.commit()
            return result.rowcount > 0  # type: ignore

    async def list_preferences(self) -> list[UserPreference]:
        """
        List all user preferences.

        Returns:
            List of preferences
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, key, value, source, confidence, created_at, updated_at
                    FROM user_preference
                    ORDER BY key
                """)
            )

            preferences: list[UserPreference] = []
            for row in result.fetchall():
                decrypted_value = self._encryption.decrypt(row[2])
                preferences.append(
                    UserPreference(
                        id=row[0],
                        key=row[1],
                        value=decrypted_value,
                        source=PreferenceSource(row[3]),
                        confidence=row[4],
                        created_at=row[5],
                        updated_at=row[6],
                    )
                )

            return preferences

    # =========================================================================
    # Episodic Logs
    # =========================================================================

    async def add_episodic_log(self, entry: EpisodicLogEntry) -> EpisodicLogEntry:
        """
        Add an episodic log entry.

        Args:
            entry: Log entry to add

        Returns:
            Added entry
        """
        async with self._session_factory() as session:
            # Encrypt summary
            encrypted_summary = self._encryption.encrypt(entry.summary)

            await session.execute(
                text("""
                    INSERT INTO episodic_log (id, timestamp, agent, action_type, summary, confidence, metadata, created_at)
                    VALUES (:id, :timestamp, :agent, :action_type, :summary, :confidence, :metadata, NOW())
                """),
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "agent": entry.agent,
                    "action_type": entry.action_type.value,
                    "summary": encrypted_summary,
                    "confidence": entry.confidence,
                    "metadata": entry.metadata.model_dump_json(),
                },
            )
            await session.commit()

            logger.debug(
                "Episodic log added",
                log_id=str(entry.id),
                agent=entry.agent,
                action_type=entry.action_type.value,
            )
            return entry

    async def get_episodic_log(self, log_id: UUID) -> EpisodicLogEntry | None:
        """
        Get an episodic log by ID.

        Args:
            log_id: Log ID

        Returns:
            Log entry or None
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, timestamp, agent, action_type, summary, confidence, metadata, created_at
                    FROM episodic_log
                    WHERE id = :id
                """),
                {"id": log_id},
            )
            row = result.fetchone()

            if row is None:
                return None

            decrypted_summary = self._encryption.decrypt(row[4])

            return EpisodicLogEntry(
                id=row[0],
                timestamp=row[1],
                agent=row[2],
                action_type=EpisodicActionType(row[3]),
                summary=decrypted_summary,
                confidence=row[5],
                metadata=EpisodicLogMetadata.model_validate_json(row[6]) if row[6] else EpisodicLogMetadata(),
                created_at=row[7],
            )

    async def get_recent_episodic_logs(
        self,
        limit: int = 10,
        agent: str | None = None,
    ) -> list[EpisodicLogEntry]:
        """
        Get recent episodic logs.

        Args:
            limit: Maximum entries to return
            agent: Optional filter by agent

        Returns:
            List of log entries
        """
        async with self._session_factory() as session:
            if agent:
                result = await session.execute(
                    text("""
                        SELECT id, timestamp, agent, action_type, summary, confidence, metadata, created_at
                        FROM episodic_log
                        WHERE agent = :agent
                        ORDER BY timestamp DESC
                        LIMIT :limit
                    """),
                    {"agent": agent, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT id, timestamp, agent, action_type, summary, confidence, metadata, created_at
                        FROM episodic_log
                        ORDER BY timestamp DESC
                        LIMIT :limit
                    """),
                    {"limit": limit},
                )

            logs: list[EpisodicLogEntry] = []
            for row in result.fetchall():
                decrypted_summary = self._encryption.decrypt(row[4])
                logs.append(
                    EpisodicLogEntry(
                        id=row[0],
                        timestamp=row[1],
                        agent=row[2],
                        action_type=EpisodicActionType(row[3]),
                        summary=decrypted_summary,
                        confidence=row[5],
                        metadata=EpisodicLogMetadata.model_validate_json(row[6]) if row[6] else EpisodicLogMetadata(),
                        created_at=row[7],
                    )
                )

            return logs

    # =========================================================================
    # Memory Metadata (for Inspector)
    # =========================================================================

    async def track_memory(self, metadata: MemoryMetadata) -> MemoryMetadata:
        """
        Track a memory entry in metadata table.

        Args:
            metadata: Memory metadata to track

        Returns:
            Tracked metadata
        """
        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO memory_metadata 
                        (id, memory_type, store_location, summary, source, confidence, is_deleted, created_at, updated_at)
                    VALUES 
                        (:id, :memory_type, :store_location, :summary, :source, :confidence, :is_deleted, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        summary = :summary,
                        confidence = :confidence,
                        is_deleted = :is_deleted,
                        updated_at = NOW()
                """),
                {
                    "id": metadata.id,
                    "memory_type": metadata.memory_type.value,
                    "store_location": metadata.store_location.value,
                    "summary": metadata.summary,
                    "source": metadata.source.value,
                    "confidence": metadata.confidence,
                    "is_deleted": metadata.is_deleted,
                },
            )
            await session.commit()
            return metadata

    async def get_memory_metadata(self, memory_id: UUID) -> MemoryMetadata | None:
        """
        Get memory metadata by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Metadata or None
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, memory_type, store_location, summary, source, confidence, is_deleted, created_at, updated_at
                    FROM memory_metadata
                    WHERE id = :id
                """),
                {"id": memory_id},
            )
            row = result.fetchone()

            if row is None:
                return None

            return MemoryMetadata(
                id=row[0],
                memory_type=MemoryType(row[1]),
                store_location=StoreLocation(row[2]),
                summary=row[3],
                source=MemorySource(row[4]),
                confidence=row[5],
                is_deleted=row[6],
                created_at=row[7],
                updated_at=row[8],
            )

    async def list_memory_metadata(
        self,
        memory_type: MemoryType | None = None,
        source: MemorySource | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MemoryMetadata], int]:
        """
        List memory metadata for Inspector.

        Args:
            memory_type: Optional filter by type
            source: Optional filter by source
            include_deleted: Include soft-deleted entries
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            Tuple of (metadata list, total count)
        """
        async with self._session_factory() as session:
            # Build WHERE clause
            conditions: list[str] = []
            params: dict[str, str | int | bool] = {"limit": limit, "offset": offset}

            if not include_deleted:
                conditions.append("is_deleted = false")

            if memory_type:
                conditions.append("memory_type = :memory_type")
                params["memory_type"] = memory_type.value

            if source:
                conditions.append("source = :source")
                params["source"] = source.value

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count
            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM memory_metadata {where_clause}"),
                params,
            )
            total_count = count_result.scalar() or 0

            # Get paginated results
            result = await session.execute(
                text(f"""
                    SELECT id, memory_type, store_location, summary, source, confidence, is_deleted, created_at, updated_at
                    FROM memory_metadata
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )

            metadata_list: list[MemoryMetadata] = []
            for row in result.fetchall():
                metadata_list.append(
                    MemoryMetadata(
                        id=row[0],
                        memory_type=MemoryType(row[1]),
                        store_location=StoreLocation(row[2]),
                        summary=row[3],
                        source=MemorySource(row[4]),
                        confidence=row[5],
                        is_deleted=row[6],
                        created_at=row[7],
                        updated_at=row[8],
                    )
                )

            return metadata_list, total_count

    async def soft_delete_memory(self, memory_id: UUID) -> bool:
        """
        Soft-delete a memory entry.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    UPDATE memory_metadata 
                    SET is_deleted = true, updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": memory_id},
            )
            await session.commit()
            return result.rowcount > 0  # type: ignore

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def clear_all(self, preserve_profile: bool = True) -> bool:
        """
        Clear all PostgreSQL data (for full reset).

        Args:
            preserve_profile: Keep basic profile settings

        Returns:
            True if cleared
        """
        async with self._session_factory() as session:
            try:
                # Truncate tables
                await session.execute(text("TRUNCATE TABLE episodic_log"))
                await session.execute(text("TRUNCATE TABLE user_preference"))
                await session.execute(text("TRUNCATE TABLE memory_metadata"))

                if not preserve_profile:
                    await session.execute(text("TRUNCATE TABLE user_profile"))
                    # Recreate default profile
                    await self._create_default_profile(session)

                await session.commit()
                logger.info("PostgreSQL tables cleared", preserve_profile=preserve_profile)
                return True
            except Exception as e:
                logger.error("Failed to clear PostgreSQL", error=str(e))
                await session.rollback()
                return False

    async def health_check(self) -> bool:
        """
        Check PostgreSQL connection health.

        Returns:
            True if healthy
        """
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("PostgreSQL health check failed", error=str(e))
            return False


# =============================================================================
# Factory Functions
# =============================================================================


def create_postgres_repository(
    database_url: str,
    encryption: EncryptionService | None = None,
) -> PostgresRepository:
    """
    Create a PostgreSQL repository.

    Args:
        database_url: PostgreSQL connection URL
        encryption: Optional encryption service

    Returns:
        Configured PostgreSQL repository
    """
    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return PostgresRepository(session_factory, encryption)
