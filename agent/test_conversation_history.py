"""Test conversation history endpoint."""
import uuid

import httpx

# Base URL for the API
BASE_URL = "http://localhost:8741/api/v1"

# Use a fixed conversation_id to maintain context
CONVERSATION_ID = str(uuid.uuid4())
print(f"Using conversation_id: {CONVERSATION_ID}")


def test_conversation_history():
    """Test the conversation history endpoint."""
    print("\n=== Test 1: Send first message ===")
    # Send first message
    response1 = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Hello, my name is Alice",
            "conversation_id": CONVERSATION_ID,
        },
        timeout=60.0,
    )
    print(f"Status: {response1.status_code}")
    data1 = response1.json()
    print(f"Response: {data1.get('response', data1)}")

    print("\n=== Test 2: Send second message ===")
    # Send second message
    response2 = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "message": "I love coding in Python",
            "conversation_id": CONVERSATION_ID,
        },
        timeout=60.0,
    )
    print(f"Status: {response2.status_code}")
    data2 = response2.json()
    print(f"Response: {data2.get('response', data2)}")

    print("\n=== Test 3: Get conversation history ===")
    # Get conversation history
    response3 = httpx.get(
        f"{BASE_URL}/conversation/{CONVERSATION_ID}",
        timeout=60.0,
    )
    print(f"Status: {response3.status_code}")
    data3 = response3.json()
    print(f"Conversation ID: {data3.get('conversation_id')}")
    print(f"Number of messages: {len(data3.get('messages', []))}")

    # Print messages
    for i, msg in enumerate(data3.get("messages", []), 1):
        print(f"\nMessage {i}:")
        print(f"  ID: {msg.get('id')}")
        print(f"  Role: {msg.get('role')}")
        print(f"  Content: {msg.get('content')[:50]}...")
        print(f"  Timestamp: {msg.get('timestamp')}")

    # Verify we have messages
    assert len(data3.get("messages", [])) >= 2, "Expected at least 2 messages"
    print("\n✅ Test passed! Conversation history retrieved successfully.")


def test_nonexistent_conversation():
    """Test getting a conversation that doesn't exist."""
    print("\n=== Test 4: Get non-existent conversation ===")
    nonexistent_id = str(uuid.uuid4())
    response = httpx.get(
        f"{BASE_URL}/conversation/{nonexistent_id}",
        timeout=60.0,
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Conversation ID: {data.get('conversation_id')}")
    print(f"Number of messages: {len(data.get('messages', []))}")

    # Should return empty messages, not an error
    assert response.status_code == 200, "Expected 200 status"
    assert len(data.get("messages", [])) == 0, "Expected empty messages"
    print("✅ Test passed! Non-existent conversation returns empty history.")


if __name__ == "__main__":
    try:
        test_conversation_history()
        test_nonexistent_conversation()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
