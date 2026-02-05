"""
Test script for executor memory retrieval functionality.

This script verifies that the ExecutorAgent can properly retrieve
memory context using the MemoryManager when executing MEMORY_RETRIEVAL steps.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from slovo_agent.agents.executor import ExecutorAgent
from slovo_agent.models import (
    ExecutionPlan,
    IntentType,
    Intent,
    MemoryContext,
    PlanStep,
    StepType,
)


async def test_memory_retrieval_without_manager():
    """Test memory retrieval when memory manager is not available."""
    print("\n=== Test 1: Memory Retrieval Without Manager ===")
    
    executor = ExecutorAgent()
    
    # Create a plan with memory retrieval step
    plan = ExecutionPlan(
        intent=Intent(text="What is my name?", type=IntentType.QUESTION),
        steps=[
            PlanStep(
                type=StepType.MEMORY_RETRIEVAL,
                description="Retrieve user profile and preferences",
            )
        ],
        estimated_complexity="simple",
    )
    
    result = await executor.execute(plan, conversation_history=[])
    
    print(f"Success: {result.success}")
    print(f"Step results: {len(result.step_results)}")
    if result.step_results:
        step_result = result.step_results[0]
        print(f"Step success: {step_result.success}")
        print(f"Memories: {step_result.output.get('memories', [])}")
        print(f"Context: {step_result.output.get('relevant_context', '')}")
    
    assert result.success, "Execution should succeed even without memory manager"
    assert result.step_results[0].output["memories"] == [], "Should return empty memories"
    print("✓ Test passed: Returns empty memories gracefully")


async def test_memory_retrieval_with_manager():
    """Test memory retrieval with a mock memory manager."""
    print("\n=== Test 2: Memory Retrieval With Mock Manager ===")
    
    # Create mock memory manager
    mock_memory = MagicMock()
    mock_memory.retrieve_context = AsyncMock()
    
    # Mock the returned memory context
    mock_context = MemoryContext(
        user_profile_summary="User prefers friendly communication",
        relevant_memories_summary="User mentioned their name is Alex",
        recent_conversation_summary="Recent discussion about preferences",
        episodic_context_summary="Previously asked about weather",
        total_token_estimate=150,
    )
    mock_memory.retrieve_context.return_value = mock_context
    
    # Create executor with memory manager
    executor = ExecutorAgent(memory_manager=mock_memory)
    
    # Create a plan with memory retrieval step
    plan = ExecutionPlan(
        intent=Intent(text="What is my name?", type=IntentType.QUESTION),
        steps=[
            PlanStep(
                type=StepType.MEMORY_RETRIEVAL,
                description="Retrieve user profile and preferences",
            )
        ],
        estimated_complexity="simple",
    )
    
    result = await executor.execute(plan, conversation_history=[])
    
    print(f"Success: {result.success}")
    print(f"Step results: {len(result.step_results)}")
    if result.step_results:
        step_result = result.step_results[0]
        print(f"Step success: {step_result.success}")
        memories = step_result.output.get("memories", [])
        print(f"Memories count: {len(memories)}")
        print(f"Profile: {memories[0][:50] if memories and memories[0] else 'None'}...")
        print(f"Context: {step_result.output.get('relevant_context', '')[:100]}...")
    
    # Verify memory manager was called
    assert mock_memory.retrieve_context.called, "Memory manager should be called"
    call_args = mock_memory.retrieve_context.call_args
    print(f"\nMemory manager called with:")
    print(f"  user_message: {call_args.kwargs.get('user_message')}")
    print(f"  conversation_id: {call_args.kwargs.get('conversation_id')}")
    print(f"  token_limit: {call_args.kwargs.get('token_limit')}")
    
    assert result.success, "Execution should succeed"
    assert len(result.step_results[0].output["memories"]) > 0, "Should return memories"
    assert "Alex" in result.step_results[0].output["relevant_context"], "Should include user name"
    print("✓ Test passed: Successfully retrieves and formats memory context")


async def test_memory_retrieval_empty_intent():
    """Test memory retrieval with empty intent."""
    print("\n=== Test 3: Memory Retrieval With Empty Intent ===")
    
    mock_memory = MagicMock()
    mock_memory.retrieve_context = AsyncMock()
    executor = ExecutorAgent(memory_manager=mock_memory)
    
    # Create a plan with memory retrieval but no intent
    plan = ExecutionPlan(
        intent=Intent(text="", type=IntentType.QUESTION),
        steps=[
            PlanStep(
                type=StepType.MEMORY_RETRIEVAL,
                description="Retrieve memories",
            )
        ],
        estimated_complexity="simple",
    )
    
    result = await executor.execute(plan, conversation_history=[])
    
    print(f"Success: {result.success}")
    
    # Memory manager should NOT be called with empty intent
    assert not mock_memory.retrieve_context.called, "Should not call memory manager with empty intent"
    assert result.success, "Should succeed gracefully"
    print("✓ Test passed: Handles empty intent gracefully")


async def main():
    """Run all tests."""
    print("Testing Executor Memory Retrieval Implementation")
    print("=" * 60)
    
    try:
        await test_memory_retrieval_without_manager()
        await test_memory_retrieval_with_manager()
        await test_memory_retrieval_empty_intent()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
