"""Quick test script for memory operations."""
import asyncio
from slovo_agent.config import settings
from slovo_agent.memory import create_memory_manager


async def test():
    print("Creating memory manager...")
    m = await create_memory_manager(
        settings.redis_url,
        settings.qdrant_url,
        settings.database_url,
    )
    
    print("\nHealth check...")
    health = await m.health_check()
    print(f"Health: {health}")
    
    print("\nStoring test turn...")
    await m.store_turn("test123", "user", "Hello, my name is Alex")
    print("Turn stored!")
    
    print("\nRetrieving turns...")
    turns = await m.get_recent_turns("test123")
    print(f"Turns: {turns}")
    
    print("\nRetrieving memory context...")
    context = await m.retrieve_context(
        user_message="What is my name?",
        conversation_id="test123",
    )
    print(f"Profile summary: {context.user_profile_summary}")
    print(f"Conversation summary: {context.recent_conversation_summary}")
    print(f"Semantic summary: {context.relevant_memories_summary}")
    print(f"Total tokens: {context.total_token_estimate}")


if __name__ == "__main__":
    asyncio.run(test())
