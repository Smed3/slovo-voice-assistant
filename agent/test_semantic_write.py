"""Test semantic memory write end-to-end."""
import asyncio
from slovo_agent.config import settings
from slovo_agent.memory import create_memory_manager
from slovo_agent.models import (
    MemoryType,
    MemorySource,
    MemoryWriteRequest,
    VerifierMemoryApproval,
)

async def test():
    print("Creating memory manager...")
    manager = await create_memory_manager(
        redis_url=settings.redis_url,
        qdrant_url=settings.qdrant_url,
        database_url=settings.database_url,
    )
    
    # Check if embedding function is set
    print(f"Embedding function set: {manager._embedding_fn is not None}")
    print(f"Writer embedding function: {manager._writer._embedding_fn is not None}")
    print(f"Retrieval embedding function: {manager._retrieval._embedding_fn is not None}")
    
    # Try to write a semantic memory
    request = MemoryWriteRequest(
        content="My name is Alex and I love Python programming",
        memory_type=MemoryType.SEMANTIC,
        source=MemorySource.CONVERSATION,
        confidence=0.9,
    )
    approval = VerifierMemoryApproval(
        approved=True,
        reason="Test write",
        confidence=0.9,
    )
    
    print("\nWriting semantic memory...")
    result = await manager.write_memory(request, approval)
    print(f"Write result: success={result.success}, error={result.error}, memory_id={result.memory_id}")
    
    if result.success:
        print("\nSearching for the memory...")
        # Now try to retrieve it
        context = await manager.retrieve_context(
            user_message="What is my name?",
            conversation_id="test-123",
        )
        print(f"Profile summary: {context.user_profile_summary[:100] if context.user_profile_summary else 'None'}...")
        print(f"Conversation summary: {context.recent_conversation_summary[:100] if context.recent_conversation_summary else 'None'}...")
        print(f"Semantic summary: {context.relevant_memories_summary[:200] if context.relevant_memories_summary else 'None'}...")
        print(f"Total tokens: {context.total_token_estimate}")

asyncio.run(test())
