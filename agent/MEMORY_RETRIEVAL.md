# Memory Retrieval Implementation

## Overview

This document describes the implementation of memory retrieval from Qdrant/Redis in the ExecutorAgent, addressing the TODO at line 196 in `executor.py`.

## Architecture

The Slovo Voice Assistant uses a **multi-level memory retrieval** architecture:

### 1. Orchestrator-Level Memory Retrieval (Primary)
- **Location**: `orchestrator.py` lines 170-205
- **Purpose**: Pre-retrieves memory context **before** any agent execution
- **Process**:
  1. User message arrives
  2. Orchestrator retrieves memory in parallel with intent interpretation
  3. Memory context is passed to all downstream agents (Intent, Planner, Executor, Verifier, Explainer)
  4. Executor uses this pre-retrieved context for LLM response generation

### 2. Step-Based Memory Retrieval (Secondary)
- **Location**: `executor.py` `_execute_memory_retrieval()` method
- **Purpose**: Additional on-demand memory retrieval during execution
- **Use Cases**:
  - Planner explicitly requests a `MEMORY_RETRIEVAL` step
  - Additional context needed mid-execution
  - Fallback when orchestrator-level retrieval is unavailable

## Implementation Details

### Changes Made

#### 1. ExecutorAgent (`executor.py`)

**Added Parameters**:
```python
def __init__(
    self,
    llm_provider: LLMProvider | None = None,
    sandbox_manager: Any | None = None,
    tool_discovery_agent: Any | None = None,
    memory_manager: "MemoryManager | None" = None,  # NEW
)
```

**Added Method**:
```python
def set_memory_manager(self, manager: "MemoryManager") -> None:
    """Set or update the memory manager."""
```

**Implemented `_execute_memory_retrieval()`**:
- Checks if memory manager is available
- Extracts intent and conversation_id from context
- Calls `memory_manager.retrieve_context()` with 1500 token limit
- Retrieves from all 4 memory stores in parallel:
  1. User Profile (PostgreSQL)
  2. Recent Conversation (Redis)
  3. Semantic Memories (Qdrant)
  4. Episodic Logs (PostgreSQL)
- Returns structured `StepResult` with memories and context

#### 2. AgentOrchestrator (`orchestrator.py`)

**Updated Initialization**:
```python
self.executor_agent = ExecutorAgent(self.llm, memory_manager=memory_manager)
```

**Updated `set_memory_manager()`**:
```python
def set_memory_manager(self, manager: "MemoryManager") -> None:
    """Set memory manager for long-term memory support."""
    self._memory = manager
    self.executor_agent.set_memory_manager(manager)  # NEW
```

## Memory Retrieval Flow

```
User Request
    ↓
Orchestrator
    ├─→ Memory Retrieval (parallel with intent parsing)
    │   └─→ MemoryManager.retrieve_context()
    │       ├─→ User Profile (Postgres)
    │       ├─→ Recent Turns (Redis)  
    │       ├─→ Semantic Search (Qdrant)
    │       └─→ Episodic Logs (Postgres)
    ↓
Intent Agent (receives memory context)
    ↓
Planner Agent (receives memory context)
    ↓ (may request MEMORY_RETRIEVAL step)
Executor Agent
    ├─→ Pre-retrieved memory (from orchestrator)
    └─→ Step-based retrieval (if planner requests)
        └─→ MemoryManager.retrieve_context()
    ↓
Verifier Agent (receives memory context)
    ↓
Explainer Agent (receives memory context)
```

## API

### MemoryManager.retrieve_context()

```python
async def retrieve_context(
    user_message: str,
    conversation_id: str | None = None,
    token_limit: int = 2000,
) -> MemoryContext
```

**Parameters**:
- `user_message`: User's message for semantic search
- `conversation_id`: Current conversation ID for recent turns
- `token_limit`: Maximum tokens for memory context (default: 2000, step-based: 1500)

**Returns**:
```python
MemoryContext(
    user_profile_summary: str,           # User preferences and style
    recent_conversation_summary: str,    # Last 10 turns from Redis
    relevant_memories_summary: str,      # Semantic search results from Qdrant
    episodic_context_summary: str,       # Past actions from PostgreSQL
    total_token_estimate: int,           # Estimated token usage
)
```

## Testing

### Test Script: `test_executor_memory.py`

**Test Cases**:
1. **test_memory_retrieval_without_manager**: Verifies graceful handling when memory manager is unavailable
2. **test_memory_retrieval_with_manager**: Tests successful memory retrieval with mock manager
3. **test_memory_retrieval_empty_intent**: Validates handling of empty intent

**Run Tests**:
```bash
cd agent
python test_executor_memory.py
```

## Edge Cases Handled

1. **No Memory Manager**: Returns empty memories with success status
2. **Empty Intent**: Returns empty memories without calling memory manager
3. **Memory Retrieval Failure**: Returns failure status with error message
4. **Missing Context Fields**: Gracefully handles None values

## Token Budget

- **Orchestrator-level retrieval**: 2000 tokens (default)
  - Profile: 200 tokens
  - Conversation: 500 tokens
  - Semantic: 800 tokens
  - Episodic: 300 tokens

- **Step-based retrieval**: 1500 tokens (smaller for efficiency)

## Security & Privacy

- All memory is **AES-encrypted at rest**
- Only **summarized** memory is sent to LLM, never raw database content
- User can inspect, edit, and delete memories via Memory Inspector
- Memory capture can be disabled in user profile

## Future Enhancements

1. Dynamic token budgets based on query complexity
2. Caching for frequently accessed memories
3. Memory relevance scoring
4. Cross-conversation memory linking
5. Automatic memory consolidation

## References

- **Memory Manager**: `slovo_agent/memory/manager.py`
- **Retrieval Pipeline**: `slovo_agent/memory/retrieval.py`
- **Qdrant Repository**: `slovo_agent/memory/qdrant_repository.py`
- **Redis Repository**: `slovo_agent/memory/redis_repository.py`
- **Memory Models**: `slovo_agent/models/memory.py`
