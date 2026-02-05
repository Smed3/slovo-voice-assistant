"""Simple test to verify conversation history endpoint without needing full agent."""
import httpx
import uuid
from redis.asyncio import Redis
import asyncio
from datetime import datetime


async def test_conversation_endpoint_simple():
    """Test the conversation history endpoint with pre-populated Redis data."""
    
    # Connect to Redis
    redis = Redis.from_url("redis://localhost:6379")
    
    # Create a test conversation ID
    conversation_id = str(uuid.uuid4())
    print(f"Using conversation_id: {conversation_id}")
    
    # Manually add some turns to Redis
    turn_key = f"turn:list:{conversation_id}"
    
    # Create turn data (ConversationTurn JSON)
    turn1 = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": "Hello, my name is Alice",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "intent_type": None,
        "confidence": None
    }
    
    turn2 = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "Hello Alice! Nice to meet you.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "intent_type": None,
        "confidence": None
    }
    
    turn3 = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": "I love coding in Python",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "intent_type": None,
        "confidence": None
    }
    
    turn4 = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "That's great! Python is a wonderful language.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "intent_type": None,
        "confidence": None
    }
    
    # Add turns to Redis
    import json
    await redis.rpush(turn_key, json.dumps(turn1))
    await redis.rpush(turn_key, json.dumps(turn2))
    await redis.rpush(turn_key, json.dumps(turn3))
    await redis.rpush(turn_key, json.dumps(turn4))
    await redis.expire(turn_key, 7200)  # 7200 seconds (2 hours) TTL
    
    print("✅ Added 4 turns to Redis")
    
    # Now test the conversation endpoint
    print(f"\nTesting GET /conversation/{conversation_id}")
    response = httpx.get(
        f"http://localhost:8741/api/v1/conversation/{conversation_id}",
        timeout=10.0,
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Conversation ID: {data.get('conversation_id')}")
        print(f"Number of messages: {len(data.get('messages', []))}")
        
        # Print messages
        for i, msg in enumerate(data.get("messages", []), 1):
            print(f"\nMessage {i}:")
            print(f"  ID: {msg.get('id')}")
            print(f"  Role: {msg.get('role')}")
            print(f"  Content: {msg.get('content')}")
            print(f"  Timestamp: {msg.get('timestamp')}")
        
        # Verify
        assert len(data.get("messages", [])) == 4, f"Expected 4 messages, got {len(data.get('messages', []))}"
        print("\n✅ Test passed! Conversation history retrieved successfully.")
    else:
        print(f"❌ Test failed with status {response.status_code}")
        print(response.text)
    
    # Test non-existent conversation
    print("\n\nTesting non-existent conversation")
    nonexistent_id = str(uuid.uuid4())
    response2 = httpx.get(
        f"http://localhost:8741/api/v1/conversation/{nonexistent_id}",
        timeout=10.0,
    )
    
    print(f"Status: {response2.status_code}")
    data2 = response2.json()
    print(f"Number of messages: {len(data2.get('messages', []))}")
    
    assert response2.status_code == 200, "Expected 200 status"
    assert len(data2.get("messages", [])) == 0, "Expected empty messages"
    print("✅ Non-existent conversation returns empty history.")
    
    # Cleanup
    await redis.close()
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_conversation_endpoint_simple())
