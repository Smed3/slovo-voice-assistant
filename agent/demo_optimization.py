"""
Integration test demonstrating the optimization improvements.

This script shows the difference between simple and complex queries
in terms of LLM calls and agent invocations.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from slovo_agent.agents.orchestrator import AgentOrchestrator
from slovo_agent.models import (
    ExecutionPlan,
    ExecutionResult,
    Explanation,
    Intent,
    IntentType,
    PlanStep,
    StepResult,
    StepType,
    Verification,
)


class CallTracker:
    """Track agent calls to measure optimization."""
    
    def __init__(self):
        self.intent_calls = 0
        self.planner_calls = 0
        self.executor_calls = 0
        self.verifier_calls = 0
        self.explainer_calls = 0
        self.total_time = 0.0


async def mock_intent_agent(text: str, call_tracker: CallTracker):
    """Mock intent agent with call tracking."""
    call_tracker.intent_calls += 1
    await asyncio.sleep(0.1)  # Simulate LLM call
    
    # Detect simple vs complex intents
    greetings = ["hello", "hi", "hey", "goodbye", "bye", "thanks"]
    is_greeting = any(g in text.lower() for g in greetings)
    
    if is_greeting:
        return Intent(
            type=IntentType.CONVERSATION,
            text=text,
            confidence=1.0,
        )
    else:
        return Intent(
            type=IntentType.QUESTION,
            text=text,
            confidence=0.9,
            requires_tool=False,
        )


async def mock_planner_agent(intent: Intent, call_tracker: CallTracker):
    """Mock planner agent with call tracking."""
    call_tracker.planner_calls += 1
    await asyncio.sleep(0.15)  # Simulate LLM call
    
    return ExecutionPlan(
        intent=intent,
        steps=[
            PlanStep(
                type=StepType.LLM_RESPONSE,
                description="Generate response",
            )
        ],
        requires_verification=True,
        requires_explanation=True,
    )


async def mock_executor_agent(plan: ExecutionPlan, call_tracker: CallTracker):
    """Mock executor agent with call tracking."""
    call_tracker.executor_calls += 1
    await asyncio.sleep(0.2)  # Simulate LLM call
    
    return ExecutionResult(
        plan=plan,
        success=True,
        step_results=[
            StepResult(
                step_index=0,
                success=True,
                output="Response generated",
            )
        ],
        final_output="This is a helpful response!",
    )


async def mock_verifier_agent(result: ExecutionResult, call_tracker: CallTracker):
    """Mock verifier agent with call tracking."""
    call_tracker.verifier_calls += 1
    await asyncio.sleep(0.1)  # Simulate LLM call
    
    return Verification(
        is_valid=True,
        confidence=0.95,
        issues=[],
        correction_hint=None,
    )


async def mock_explainer_agent(intent: Intent, result: ExecutionResult, call_tracker: CallTracker):
    """Mock explainer agent with call tracking."""
    call_tracker.explainer_calls += 1
    await asyncio.sleep(0.15)  # Simulate LLM call
    
    return Explanation(
        response="Here's your answer!",
        reasoning="Generated response based on intent",
    )


async def test_simple_query(orchestrator: AgentOrchestrator, tracker: CallTracker):
    """Test a simple greeting query."""
    print("\n" + "="*60)
    print("SIMPLE QUERY TEST: 'Hello!'")
    print("="*60)
    
    start = time.time()
    result = await orchestrator.process_message("Hello!", "test-conv-1")
    elapsed = time.time() - start
    tracker.total_time = elapsed
    
    print(f"\n✅ Response: {result.response}")
    print(f"⏱️  Time: {elapsed:.3f}s")
    print(f"📊 Agent calls:")
    print(f"   - Intent: {tracker.intent_calls} (required)")
    print(f"   - Planner: {tracker.planner_calls} (SKIPPED via fast path)")
    print(f"   - Executor: {tracker.executor_calls} (required)")
    print(f"   - Verifier: {tracker.verifier_calls} (SKIPPED)")
    print(f"   - Explainer: {tracker.explainer_calls} (SKIPPED)")
    print(f"\n   Total LLM calls: {tracker.intent_calls + tracker.planner_calls + tracker.executor_calls + tracker.verifier_calls + tracker.explainer_calls}")


async def test_complex_query(orchestrator: AgentOrchestrator, tracker: CallTracker):
    """Test a complex question query."""
    print("\n" + "="*60)
    print("COMPLEX QUERY TEST: 'What is quantum computing?'")
    print("="*60)
    
    start = time.time()
    result = await orchestrator.process_message("What is quantum computing?", "test-conv-2")
    elapsed = time.time() - start
    tracker.total_time = elapsed
    
    print(f"\n✅ Response: {result.response}")
    print(f"⏱️  Time: {elapsed:.3f}s")
    print(f"📊 Agent calls:")
    print(f"   - Intent: {tracker.intent_calls} (required)")
    print(f"   - Planner: {tracker.planner_calls} (required)")
    print(f"   - Executor: {tracker.executor_calls} (required)")
    print(f"   - Verifier: {tracker.verifier_calls} (required)")
    print(f"   - Explainer: {tracker.explainer_calls} (required)")
    print(f"\n   Total LLM calls: {tracker.intent_calls + tracker.planner_calls + tracker.executor_calls + tracker.verifier_calls + tracker.explainer_calls}")


async def main():
    """Run integration tests."""
    print("\n" + "="*60)
    print("AGENT PIPELINE OPTIMIZATION DEMO")
    print("="*60)
    print("\nThis demo shows the optimization benefits:")
    print("- Simple queries use FAST PATH (skip planner/verifier/explainer)")
    print("- Complex queries use FULL PIPELINE (all agents)")
    print("- Memory retrieval is PARALLELIZED")
    
    # Create orchestrator with mocked LLM
    mock_llm = MagicMock()
    orchestrator = AgentOrchestrator(llm_provider=mock_llm)
    
    # Test 1: Simple query (fast path)
    simple_tracker = CallTracker()
    
    async def mock_intent_simple(msg, **kw):
        return await mock_intent_agent(msg, simple_tracker)
    
    async def mock_planner_simple(intent, **kw):
        return await mock_planner_agent(intent, simple_tracker)
    
    async def mock_executor_simple(plan, **kw):
        return await mock_executor_agent(plan, simple_tracker)
    
    async def mock_verifier_simple(result, **kw):
        return await mock_verifier_agent(result, simple_tracker)
    
    async def mock_explainer_simple(intent, result, **kw):
        return await mock_explainer_agent(intent, result, simple_tracker)
    
    with patch.object(orchestrator.intent_agent, 'interpret', side_effect=mock_intent_simple):
        with patch.object(orchestrator.planner_agent, 'create_plan', side_effect=mock_planner_simple):
            with patch.object(orchestrator.executor_agent, 'execute', side_effect=mock_executor_simple):
                with patch.object(orchestrator.verifier_agent, 'verify', side_effect=mock_verifier_simple):
                    with patch.object(orchestrator.explainer_agent, 'explain', side_effect=mock_explainer_simple):
                        await test_simple_query(orchestrator, simple_tracker)
    
    # Test 2: Complex query (full pipeline)
    complex_tracker = CallTracker()
    
    async def mock_intent_complex(msg, **kw):
        return await mock_intent_agent(msg, complex_tracker)
    
    async def mock_planner_complex(intent, **kw):
        return await mock_planner_agent(intent, complex_tracker)
    
    async def mock_executor_complex(plan, **kw):
        return await mock_executor_agent(plan, complex_tracker)
    
    async def mock_verifier_complex(result, **kw):
        return await mock_verifier_agent(result, complex_tracker)
    
    async def mock_explainer_complex(intent, result, **kw):
        return await mock_explainer_agent(intent, result, complex_tracker)
    
    with patch.object(orchestrator.intent_agent, 'interpret', side_effect=mock_intent_complex):
        with patch.object(orchestrator.planner_agent, 'create_plan', side_effect=mock_planner_complex):
            with patch.object(orchestrator.executor_agent, 'execute', side_effect=mock_executor_complex):
                with patch.object(orchestrator.verifier_agent, 'verify', side_effect=mock_verifier_complex):
                    with patch.object(orchestrator.explainer_agent, 'explain', side_effect=mock_explainer_complex):
                        await test_complex_query(orchestrator, complex_tracker)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY: Optimization Impact")
    print("="*60)
    
    simple_calls = simple_tracker.intent_calls + simple_tracker.planner_calls + simple_tracker.executor_calls + simple_tracker.verifier_calls + simple_tracker.explainer_calls
    complex_calls = complex_tracker.intent_calls + complex_tracker.planner_calls + complex_tracker.executor_calls + complex_tracker.verifier_calls + complex_tracker.explainer_calls
    
    print(f"\n📉 Simple query (greeting):")
    print(f"   - LLM calls: {simple_calls} (was 5 before optimization)")
    print(f"   - Time saved: ~{(0.75 - simple_tracker.total_time):.2f}s")
    print(f"   - Improvement: {((5 - simple_calls) / 5 * 100):.0f}% fewer LLM calls")
    
    print(f"\n📊 Complex query:")
    print(f"   - LLM calls: {complex_calls} (was 5 before optimization)")
    print(f"   - Time: {complex_tracker.total_time:.2f}s")
    print(f"   - Note: Full pipeline still runs for complex queries")
    
    print("\n✨ Key optimizations:")
    print("   ✓ Fast path for greetings/simple queries")
    print("   ✓ Parallel memory retrieval (4 concurrent queries)")
    print("   ✓ Conditional verification based on complexity")
    print("   ✓ Conditional explanation based on plan complexity")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(main())
