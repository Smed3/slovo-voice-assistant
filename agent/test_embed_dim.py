"""Test OpenAI embedding dimension."""
import asyncio
from openai import AsyncOpenAI
from slovo_agent.config import settings

async def test():
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input="test"
    )
    dim = len(response.data[0].embedding)
    print(f"Embedding dimension: {dim}")
    
    # Compare with expected
    EXPECTED_DIM = 1536
    if dim != EXPECTED_DIM:
        print(f"ERROR: Expected {EXPECTED_DIM}, got {dim}")
    else:
        print("OK: Dimension matches Qdrant collection config")

asyncio.run(test())
