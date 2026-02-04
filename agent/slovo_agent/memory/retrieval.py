"""
Memory Retrieval Pipeline for Slovo Agent Runtime.

Phase 3: Pre-LLM memory retrieval
- Retrieval happens BEFORE LLM invocation
- Memory is summarized before prompt injection
- Hard token limit enforced
- Never inject raw logs

Retrieval Order (Fixed):
1. User Profile (Postgres)
2. Recent Session Context (Redis)
3. Semantic Recall (Qdrant)
4. Episodic Summaries (Postgres)
"""

import asyncio
from typing import Final

import structlog

from slovo_agent.memory.postgres_repository import PostgresRepository
from slovo_agent.memory.qdrant_repository import QdrantRepository
from slovo_agent.memory.redis_repository import RedisRepository
from slovo_agent.models import (
    ConversationTurn,
    EpisodicLogEntry,
    MemoryContext,
    MemoryRetrievalRequest,
    SemanticSearchResult,
    UserProfile,
)

logger = structlog.get_logger(__name__)

# Token estimation (rough approximation: ~4 chars per token)
CHARS_PER_TOKEN: Final[int] = 4

# Section token budgets (adjustable)
PROFILE_TOKEN_BUDGET: Final[int] = 200
CONVERSATION_TOKEN_BUDGET: Final[int] = 500
SEMANTIC_TOKEN_BUDGET: Final[int] = 800
EPISODIC_TOKEN_BUDGET: Final[int] = 300


class MemoryRetrievalPipeline:
    """
    Pre-LLM memory retrieval pipeline.

    Retrieves and summarizes memory from all stores
    before injecting into LLM prompt.

    LLM receives:
    - User request
    - Minimal memory summary
    - NO direct DB content
    """

    def __init__(
        self,
        redis: RedisRepository,
        qdrant: QdrantRepository,
        postgres: PostgresRepository,
        embedding_fn: "EmbeddingFunction | None" = None,
    ) -> None:
        """
        Initialize retrieval pipeline.

        Args:
            redis: Redis repository for short-term memory
            qdrant: Qdrant repository for semantic memory
            postgres: PostgreSQL repository for structured memory
            embedding_fn: Function to generate embeddings for semantic search
        """
        self._redis = redis
        self._qdrant = qdrant
        self._postgres = postgres
        self._embedding_fn = embedding_fn
        logger.info("Memory retrieval pipeline initialized")

    def set_embedding_function(self, fn: "EmbeddingFunction") -> None:
        """Set the embedding function for semantic search."""
        self._embedding_fn = fn

    async def retrieve(self, request: MemoryRetrievalRequest) -> MemoryContext:
        """
        Execute the full retrieval pipeline.

        Order:
        1. User Profile (Postgres)
        2. Recent Session Context (Redis)
        3. Semantic Recall (Qdrant)
        4. Episodic Summaries (Postgres)

        Args:
            request: Retrieval request with query and limits

        Returns:
            Aggregated memory context ready for LLM
        """
        logger.debug(
            "Starting memory retrieval",
            conversation_id=request.conversation_id,
            token_limit=request.token_limit,
        )

        # Track token usage
        remaining_tokens = request.token_limit
        total_tokens = 0

        # Parallelize all 4 memory retrievals using asyncio.gather
        (
            (profile_summary, profile_tokens),
            (conversation_summary, conv_tokens),
            (semantic_summary, semantic_tokens),
            (episodic_summary, episodic_tokens),
        ) = await asyncio.gather(
            self._retrieve_profile(min(PROFILE_TOKEN_BUDGET, remaining_tokens)),
            self._retrieve_session(
                request.conversation_id,
                min(CONVERSATION_TOKEN_BUDGET, remaining_tokens),
            ),
            self._retrieve_semantic(
                request.user_message,
                request.max_semantic_results,
                min(SEMANTIC_TOKEN_BUDGET, remaining_tokens),
            ),
            self._retrieve_episodic(
                request.max_episodic_results,
                min(EPISODIC_TOKEN_BUDGET, remaining_tokens),
            ),
        )

        total_tokens = profile_tokens + conv_tokens + semantic_tokens + episodic_tokens

        context = MemoryContext(
            user_profile_summary=profile_summary,
            recent_conversation_summary=conversation_summary,
            relevant_memories_summary=semantic_summary,
            episodic_context_summary=episodic_summary,
            total_token_estimate=total_tokens,
        )

        logger.debug(
            "Memory retrieval complete",
            total_tokens=total_tokens,
            has_profile=bool(profile_summary),
            has_conversation=bool(conversation_summary),
            has_semantic=bool(semantic_summary),
            has_episodic=bool(episodic_summary),
        )

        return context

    async def _retrieve_profile(self, token_budget: int) -> tuple[str, int]:
        """
        Retrieve and summarize user profile.

        Args:
            token_budget: Maximum tokens for this section

        Returns:
            Tuple of (summary, tokens_used)
        """
        if token_budget <= 0:
            return "", 0

        try:
            profile = await self._postgres.get_user_profile()
            summary = self._summarize_profile(profile)
            tokens = self._estimate_tokens(summary)

            # Truncate if over budget
            if tokens > token_budget:
                summary = self._truncate_to_tokens(summary, token_budget)
                tokens = token_budget

            return summary, tokens
        except Exception as e:
            logger.warning("Failed to retrieve profile", error=str(e))
            return "", 0

    def _summarize_profile(self, profile: UserProfile) -> str:
        """Create concise profile summary."""
        parts: list[str] = []

        if profile.preferred_languages:
            langs = ", ".join(profile.preferred_languages)
            parts.append(f"Languages: {langs}")

        if profile.communication_style:
            parts.append(f"Style: {profile.communication_style}")

        if not profile.memory_capture_enabled:
            parts.append("Memory capture: disabled")

        if not parts:
            return ""

        return "User preferences: " + "; ".join(parts) + "."

    async def _retrieve_session(
        self, conversation_id: str | None, token_budget: int
    ) -> tuple[str, int]:
        """
        Retrieve and summarize recent session context.

        Args:
            conversation_id: Current conversation ID
            token_budget: Maximum tokens for this section

        Returns:
            Tuple of (summary, tokens_used)
        """
        if token_budget <= 0 or not conversation_id:
            return "", 0

        try:
            turns = await self._redis.get_recent_turns(conversation_id, limit=10)

            if not turns:
                return "", 0

            summary = self._summarize_turns(turns, token_budget)
            tokens = self._estimate_tokens(summary)

            return summary, tokens
        except Exception as e:
            logger.warning("Failed to retrieve session", error=str(e))
            return "", 0

    def _summarize_turns(
        self, turns: list[ConversationTurn], token_budget: int
    ) -> str:
        """Create concise conversation summary."""
        if not turns:
            return ""

        # Build summary from most recent turns
        lines: list[str] = ["Recent conversation:"]
        total_chars = len(lines[0])
        max_chars = token_budget * CHARS_PER_TOKEN

        for turn in turns[-5:]:  # Last 5 turns max
            role = "User" if turn.role == "user" else "Assistant"
            # Truncate long content
            content = turn.content[:200] + "..." if len(turn.content) > 200 else turn.content
            line = f"- {role}: {content}"

            if total_chars + len(line) > max_chars:
                break

            lines.append(line)
            total_chars += len(line)

        return "\n".join(lines)

    async def _retrieve_semantic(
        self, query: str, max_results: int, token_budget: int
    ) -> tuple[str, int]:
        """
        Retrieve and summarize semantic memories.

        Args:
            query: User query for semantic search
            max_results: Maximum semantic results
            token_budget: Maximum tokens for this section

        Returns:
            Tuple of (summary, tokens_used)
        """
        if token_budget <= 0 or not self._embedding_fn:
            return "", 0

        try:
            # Generate query embedding
            query_vector = await self._embedding_fn(query)

            # Search semantic memory
            # Note: cosine similarity for embeddings typically ranges 0.2-0.5 for related content
            # Use a lower threshold (0.25) to avoid filtering out relevant memories
            results = await self._qdrant.search(
                query_vector=query_vector,
                limit=max_results,
                min_confidence=0.25,
            )

            if not results:
                return "", 0

            summary = self._summarize_semantic(results, token_budget)
            tokens = self._estimate_tokens(summary)

            return summary, tokens
        except Exception as e:
            logger.warning("Failed to retrieve semantic memory", error=str(e))
            return "", 0

    def _summarize_semantic(
        self, results: list[SemanticSearchResult], token_budget: int
    ) -> str:
        """Create concise semantic memory summary."""
        if not results:
            return ""

        lines: list[str] = ["Relevant context:"]
        total_chars = len(lines[0])
        max_chars = token_budget * CHARS_PER_TOKEN

        for result in results:
            # Cosine similarity for semantic embeddings is typically 0.2-0.5 for related content
            # Use 0.25 as minimum to include reasonably relevant memories
            if result.score < 0.25:
                continue

            line = f"- {result.metadata.summary}"

            if total_chars + len(line) > max_chars:
                break

            lines.append(line)
            total_chars += len(line)

        if len(lines) == 1:
            return ""

        return "\n".join(lines)

    async def _retrieve_episodic(
        self, max_results: int, token_budget: int
    ) -> tuple[str, int]:
        """
        Retrieve and summarize episodic logs.

        Args:
            max_results: Maximum episodic results
            token_budget: Maximum tokens for this section

        Returns:
            Tuple of (summary, tokens_used)
        """
        if token_budget <= 0:
            return "", 0

        try:
            logs = await self._postgres.get_recent_episodic_logs(limit=max_results)

            if not logs:
                return "", 0

            summary = self._summarize_episodic(logs, token_budget)
            tokens = self._estimate_tokens(summary)

            return summary, tokens
        except Exception as e:
            logger.warning("Failed to retrieve episodic logs", error=str(e))
            return "", 0

    def _summarize_episodic(
        self, logs: list[EpisodicLogEntry], token_budget: int
    ) -> str:
        """Create concise episodic summary."""
        if not logs:
            return ""

        # Only include high-confidence, relevant logs
        filtered = [log for log in logs if log.confidence >= 0.7][:3]

        if not filtered:
            return ""

        lines: list[str] = ["Recent actions:"]
        total_chars = len(lines[0])
        max_chars = token_budget * CHARS_PER_TOKEN

        for log in filtered:
            line = f"- [{log.agent}] {log.summary}"

            if total_chars + len(line) > max_chars:
                break

            lines.append(line)
            total_chars += len(line)

        if len(lines) == 1:
            return ""

        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // CHARS_PER_TOKEN

    def _truncate_to_tokens(self, text: str, token_limit: int) -> str:
        """Truncate text to fit token limit."""
        max_chars = token_limit * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."


# Type alias for embedding function
from typing import Awaitable, Callable

EmbeddingFunction = Callable[[str], Awaitable[list[float]]]
