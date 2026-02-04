# Memory System Documentation

## Phase 3: Memory System

The memory system provides persistent, local-only memory for the Slovo Voice Assistant.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Memory Manager                               │
├─────────────────┬─────────────────┬─────────────────────────────┤
│                 │                 │                              │
│  Redis          │   Qdrant        │      PostgreSQL              │
│  (Short-Term)   │   (Semantic)    │      (Structured)            │
│                 │                 │                              │
│  - Session      │  - Embeddings   │  - User Profile              │
│  - Conv. Turns  │  - Context      │  - Preferences               │
│  - Tool Output  │  - Recall       │  - Episodic Logs             │
│                 │                 │  - Metadata                  │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Memory Types

| Type       | Store      | Purpose                          | TTL        |
|------------|------------|----------------------------------|------------|
| Semantic   | Qdrant     | Context recall via embeddings    | Permanent  |
| Episodic   | PostgreSQL | Agent action logs                | Permanent  |
| Preference | PostgreSQL | User preferences (key-value)     | Permanent  |
| Session    | Redis      | Active conversation context      | 2 hours    |

### Key Principles

1. **Single-user, local-only**: No cloud persistence
2. **Pre-LLM retrieval**: Memory is retrieved and summarized before LLM calls
3. **Verifier approval**: Memory writes require verifier agent approval
4. **Encryption at rest**: AES-256 for all persistent data
5. **User control**: Full Memory Inspector for browsing/editing/deleting

### Memory Write Rules

Memory is NOT automatically written. A write occurs only when:

1. ✅ Verifier agent approves the write
2. ✅ Confidence score >= threshold (default 0.7)
3. ✅ User has not disabled memory capture

### Memory Retrieval Pipeline

Order (fixed):
1. User Profile (PostgreSQL)
2. Recent Session Context (Redis)
3. Semantic Recall (Qdrant)
4. Episodic Summaries (PostgreSQL)

Token budgets are enforced. Raw database content is never sent to LLM.

### API Reference

See `agent/slovo_agent/api/memory.py` for endpoint implementations.

### Configuration

```env
# Memory Services
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://slovo:slovo_local_dev@localhost:5432/slovo

# Memory Settings
MEMORY_REDIS_TTL=7200
MEMORY_CONFIDENCE_THRESHOLD=0.7
MEMORY_TOKEN_LIMIT=2000

# Encryption
SLOVO_ENCRYPTION_KEY=your-secure-key
```

### Full Reset Procedure

A full reset must:
1. Stop agent execution
2. Clear Redis (all session data)
3. Drop Qdrant collections (all semantic memory)
4. Truncate PostgreSQL tables (all structured memory)
5. Restart agent runtime

⚠️ No partial reset is allowed - it's all or nothing.

### Security Notes

- Redis is excluded from encryption (non-persistent)
- Agent never logs plaintext memory to disk
- Decrypted content exists only in memory
- Encryption/decryption happens at repository boundary
