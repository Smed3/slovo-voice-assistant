"""Quick test of the qdrant_repository fix."""
import asyncio
from qdrant_client import AsyncQdrantClient


async def test_query():
    client = AsyncQdrantClient(host="localhost", port=6333)
    
    try:
        # Test query_points
        response = await client.query_points(
            collection_name="semantic_memory",
            query=[0.1] * 1536,  # Dummy vector
            limit=5,
            with_payload=True,
        )
        print(f"SUCCESS: query_points returned {len(response.points)} results")
        for p in response.points:
            print(f"  - Point {p.id}: score={p.score}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_query())
