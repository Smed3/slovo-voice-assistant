"""
Memory subsystem for Slovo Agent Runtime.

Phase 3: Memory System Implementation
- Local-only, single-user
- No cloud persistence
- Pre-LLM memory retrieval
- Encryption at rest
"""

from slovo_agent.memory.encryption import (
    EncryptionError,
    EncryptionService,
    get_encryption_service,
    initialize_encryption,
    shutdown_encryption,
)
from slovo_agent.memory.redis_repository import (
    RedisRepository,
)
from slovo_agent.memory.qdrant_repository import (
    QdrantRepository,
)
from slovo_agent.memory.postgres_repository import (
    PostgresRepository,
    create_postgres_repository,
)
from slovo_agent.memory.retrieval import (
    EmbeddingFunction,
    MemoryRetrievalPipeline,
)
from slovo_agent.memory.writer import (
    MemoryWriteService,
)
from slovo_agent.memory.manager import (
    MemoryManager,
    create_memory_manager,
)

__all__ = [
    # Encryption
    "EncryptionError",
    "EncryptionService",
    "get_encryption_service",
    "initialize_encryption",
    "shutdown_encryption",
    # Repositories
    "RedisRepository",
    "QdrantRepository",
    "PostgresRepository",
    "create_postgres_repository",
    # Retrieval
    "EmbeddingFunction",
    "MemoryRetrievalPipeline",
    # Writer
    "MemoryWriteService",
    # Manager
    "MemoryManager",
    "create_memory_manager",
]
