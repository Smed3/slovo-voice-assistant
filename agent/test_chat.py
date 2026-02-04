"""Test chat endpoint with persistent conversation_id."""
import httpx
import uuid

# Use a FIXED conversation_id across all requests to maintain memory
CONVERSATION_ID = str(uuid.uuid4())
print(f"Using conversation_id: {CONVERSATION_ID}")

# First message - introduce yourself
print("\n=== Message 1: Introduction ===")
response1 = httpx.post(
    "http://localhost:8741/api/chat",
    json={
        "message": "Hello, my name is Alex and I love programming in Python",
        "conversation_id": CONVERSATION_ID,  # CRITICAL: must be sent!
    },
    timeout=60.0,
)
print(f"Status: {response1.status_code}")
data1 = response1.json()
print(f"Response: {data1.get('response', data1)}")

# Second message - ask if it remembers
print("\n=== Message 2: Memory Test ===")
response2 = httpx.post(
    "http://localhost:8741/api/chat",
    json={
        "message": "What is my name and what programming language do I like?",
        "conversation_id": CONVERSATION_ID,  # SAME conversation_id!
    },
    timeout=60.0,
)
print(f"Status: {response2.status_code}")
data2 = response2.json()
print(f"Response: {data2.get('response', data2)}")
