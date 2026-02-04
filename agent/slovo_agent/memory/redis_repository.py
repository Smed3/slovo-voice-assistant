"""
Redis Repository for Short-Term Working Memory.

Phase 3: Session/working memory only
- Non-authoritative and non-persistent
- TTL: Default 2 hours, configurable
- Namespace all keys with session:{uuid}
"""

import json
from datetime import datetime
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from slovo_agent.models import (
    ConversationTurn,
    SessionContext,
    WorkingMemoryState,
)

logger = structlog.get_logger(__name__)

# Key prefixes for namespacing
SESSION_PREFIX: Final[str] = "session"
TURN_PREFIX: Final[str] = "turn"
TOOL_OUTPUT_PREFIX: Final[str] = "tool_output"

# Default TTL: 2 hours
DEFAULT_TTL_SECONDS: Final[int] = 7200


class RedisRepository:
    """
    Repository for short-term working memory in Redis.

    All data is non-persistent and expires after TTL.
    Used for:
    - Current conversation turns
    - Active agent state
    - Temporary tool outputs
    """

    def __init__(self, redis_client: Redis, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """
        Initialize Redis repository.

        Args:
            redis_client: Async Redis client
            ttl_seconds: Default TTL for all keys
        """
        self._redis = redis_client
        self._ttl = ttl_seconds
        logger.info("Redis repository initialized", ttl_seconds=ttl_seconds)

    # =========================================================================
    # Session Management
    # =========================================================================

    def _session_key(self, session_id: UUID | str) -> str:
        """Generate session key."""
        return f"{SESSION_PREFIX}:{session_id}"

    async def create_session(self, session: SessionContext) -> SessionContext:
        """
        Create a new session context.

        Args:
            session: Session context to create

        Returns:
            Created session context
        """
        key = self._session_key(session.session_id)
        session.created_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()

        ttl = session.ttl_seconds or self._ttl
        await self._redis.setex(
            key,
            ttl,
            session.model_dump_json(),
        )

        logger.debug(
            "Session created",
            session_id=str(session.session_id),
            conversation_id=session.conversation_id,
        )
        return session

    async def get_session(self, session_id: UUID | str) -> SessionContext | None:
        """
        Get session context by ID.

        Args:
            session_id: Session ID

        Returns:
            Session context or None if not found/expired
        """
        key = self._session_key(session_id)
        data = await self._redis.get(key)

        if data is None:
            return None

        return SessionContext.model_validate_json(data)

    async def update_session(self, session: SessionContext) -> SessionContext:
        """
        Update an existing session context.

        Args:
            session: Updated session context

        Returns:
            Updated session context
        """
        key = self._session_key(session.session_id)
        session.updated_at = datetime.utcnow()

        ttl = session.ttl_seconds or self._ttl
        await self._redis.setex(
            key,
            ttl,
            session.model_dump_json(),
        )

        logger.debug("Session updated", session_id=str(session.session_id))
        return session

    async def delete_session(self, session_id: UUID | str) -> bool:
        """
        Delete a session context.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        key = self._session_key(session_id)
        result = await self._redis.delete(key)
        return result > 0

    async def extend_session_ttl(
        self, session_id: UUID | str, ttl_seconds: int | None = None
    ) -> bool:
        """
        Extend session TTL.

        Args:
            session_id: Session ID
            ttl_seconds: New TTL (uses default if None)

        Returns:
            True if extended, False if session not found
        """
        key = self._session_key(session_id)
        ttl = ttl_seconds or self._ttl
        return await self._redis.expire(key, ttl)

    # =========================================================================
    # Conversation Turns
    # =========================================================================

    def _turn_list_key(self, conversation_id: str) -> str:
        """Generate turn list key."""
        return f"{TURN_PREFIX}:list:{conversation_id}"

    async def add_turn(
        self, conversation_id: str, turn: ConversationTurn
    ) -> ConversationTurn:
        """
        Add a conversation turn.

        Args:
            conversation_id: Conversation ID
            turn: Turn to add

        Returns:
            Added turn
        """
        key = self._turn_list_key(conversation_id)
        await self._redis.rpush(key, turn.model_dump_json())
        await self._redis.expire(key, self._ttl)

        logger.debug(
            "Turn added",
            conversation_id=conversation_id,
            role=turn.role,
        )
        return turn

    async def get_recent_turns(
        self, conversation_id: str, limit: int = 10
    ) -> list[ConversationTurn]:
        """
        Get recent conversation turns.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of turns to retrieve

        Returns:
            List of recent turns (newest last)
        """
        key = self._turn_list_key(conversation_id)
        # Get last N items
        data = await self._redis.lrange(key, -limit, -1)

        turns: list[ConversationTurn] = []
        for item in data:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            turns.append(ConversationTurn.model_validate_json(item))

        return turns

    async def clear_turns(self, conversation_id: str) -> int:
        """
        Clear all turns for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of turns cleared
        """
        key = self._turn_list_key(conversation_id)
        length = await self._redis.llen(key)
        await self._redis.delete(key)
        return length

    # =========================================================================
    # Tool Outputs
    # =========================================================================

    def _tool_output_key(self, session_id: UUID | str, tool_name: str) -> str:
        """Generate tool output key."""
        return f"{TOOL_OUTPUT_PREFIX}:{session_id}:{tool_name}"

    async def store_tool_output(
        self,
        session_id: UUID | str,
        tool_name: str,
        output: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store a tool output.

        Args:
            session_id: Session ID
            tool_name: Tool name
            output: Tool output string
            ttl_seconds: Optional custom TTL
        """
        key = self._tool_output_key(session_id, tool_name)
        ttl = ttl_seconds or self._ttl
        await self._redis.setex(key, ttl, output)

        logger.debug(
            "Tool output stored",
            session_id=str(session_id),
            tool_name=tool_name,
        )

    async def get_tool_output(
        self, session_id: UUID | str, tool_name: str
    ) -> str | None:
        """
        Get a tool output.

        Args:
            session_id: Session ID
            tool_name: Tool name

        Returns:
            Tool output or None if not found/expired
        """
        key = self._tool_output_key(session_id, tool_name)
        data = await self._redis.get(key)

        if data is None:
            return None

        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data

    async def get_all_tool_outputs(
        self, session_id: UUID | str
    ) -> dict[str, str]:
        """
        Get all tool outputs for a session.

        Args:
            session_id: Session ID

        Returns:
            Dict of tool_name -> output
        """
        pattern = f"{TOOL_OUTPUT_PREFIX}:{session_id}:*"
        outputs: dict[str, str] = {}

        async for key in self._redis.scan_iter(match=pattern):
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            tool_name = key.split(":")[-1]
            data = await self._redis.get(key)
            if data:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                outputs[tool_name] = data

        return outputs

    # =========================================================================
    # Working Memory State
    # =========================================================================

    async def get_working_memory(
        self,
        session_id: UUID | str,
        conversation_id: str | None = None,
    ) -> WorkingMemoryState:
        """
        Get complete working memory state.

        Args:
            session_id: Session ID
            conversation_id: Optional conversation ID for turns

        Returns:
            Complete working memory state
        """
        session = await self.get_session(session_id)

        # Get conversation turns if conversation_id provided
        recent_turns: list[ConversationTurn] = []
        if conversation_id or (session and session.conversation_id):
            conv_id = conversation_id or session.conversation_id  # type: ignore
            recent_turns = await self.get_recent_turns(conv_id)

        # Get tool outputs
        tool_outputs = await self.get_all_tool_outputs(session_id)

        return WorkingMemoryState(
            session=session,
            recent_turns=recent_turns,
            pending_tool_outputs=tool_outputs,
        )

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def clear_all(self) -> int:
        """
        Clear all Redis data (for full reset).

        Returns:
            Number of keys deleted
        """
        count = 0
        patterns = [
            f"{SESSION_PREFIX}:*",
            f"{TURN_PREFIX}:*",
            f"{TOOL_OUTPUT_PREFIX}:*",
        ]

        for pattern in patterns:
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
                count += 1

        logger.info("Redis cleared", keys_deleted=count)
        return count

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if healthy
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False
