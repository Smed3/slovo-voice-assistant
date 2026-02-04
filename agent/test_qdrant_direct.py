"""Test Qdrant search directly."""
import asyncio
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI
from slovo_agent.config import settings
from slovo_agent.memory.encryption import get_encryption_service, initialize_encryption

async def test():
    print("Initializing...")
    initialize_encryption()
    encryption = get_encryption_service()
    
    client = AsyncQdrantClient(url=settings.qdrant_url)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # Generate embedding for query
    print("\nGenerating query embedding...")
    query = "What is my name?"
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    query_vector = response.data[0].embedding
    print(f"Query vector dimension: {len(query_vector)}")
    
    # Search Qdrant directly
    print("\nSearching Qdrant...")
    try:
        results = await client.query_points(
            collection_name="semantic_memory",
            query=query_vector,
            limit=5,
            with_payload=True,
        )
        print(f"Found {len(results.points)} results")
        for point in results.points:
            print(f"\n  Point ID: {point.id}")
            print(f"  Score: {point.score}")
            # Decrypt summary
            encrypted_summary = point.payload.get("summary_encrypted", "")
            if encrypted_summary:
                try:
                    summary = encryption.decrypt(encrypted_summary)
                    print(f"  Summary: {summary[:100]}...")
                except Exception as e:
                    print(f"  Decryption failed: {e}")
            else:
                print(f"  Payload: {point.payload}")
    except Exception as e:
        print(f"Search failed: {type(e).__name__}: {e}")
    
    await client.close()

asyncio.run(test())
