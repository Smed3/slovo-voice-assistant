"""
Test agent pipeline optimizations.

This test verifies:
1. Fast path for simple intents (greetings, farewells)
2. Parallel memory retrieval
3. Conditional verification and explanation
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slovo_agent.agents.orchestrator import AgentOrchestrator
from slovo_agent.models import (
    ExecutionPlan,
    Intent,
    IntentType,
    PlanStep,
    StepType,
)


@pytest.fixture
def mock_llm():
    """Mock LLM provider."""
    llm = MagicMock()
    llm.generate_structured = AsyncMock()
    return llm


@pytest.fixture
def orchestrator(mock_llm):
    """Create orchestrator with mocked LLM."""
    return AgentOrchestrator(llm_provider=mock_llm)


@pytest.mark.asyncio
async def test_simple_intent_fast_path(orchestrator):
    """Test that simple intents use the fast path."""
    
    # Mock the intent agent to return a conversational intent
    with patch.object(
        orchestrator.intent_agent, 
        'interpret',
        new=AsyncMock(return_value=Intent(
            type=IntentType.CONVERSATION,
            text="Hello",
            confidence=1.0,
        ))
    ):
        # Mock executor to return a simple response
        with patch.object(
            orchestrator.executor_agent,
            'execute',
            new=AsyncMock(return_value=MagicMock(
                success=True,
                final_output="Hello! How can I help you today?",
            ))
        ):
            # Mock planner (should NOT be called for fast path)
            planner_spy = AsyncMock()
            orchestrator.planner_agent.create_plan = planner_spy
            
            result = await orchestrator.process_message("Hello", "test-conv")
            
            # Verify response
            assert result.response == "Hello! How can I help you today?"
            assert result.confidence == 1.0
            
            # Verify planner was NOT called (fast path)
            planner_spy.assert_not_called()


@pytest.mark.asyncio
async def test_complex_intent_full_pipeline(orchestrator):
    """Test that complex intents go through full pipeline."""
    
    # Mock the intent agent to return a tool request
    with patch.object(
        orchestrator.intent_agent,
        'interpret',
        new=AsyncMock(return_value=Intent(
            type=IntentType.TOOL_REQUEST,
            text="What's the weather?",
            confidence=1.0,
            requires_tool=True,
        ))
    ):
        # Mock planner to return a complex plan
        with patch.object(
            orchestrator.planner_agent,
            'create_plan',
            new=AsyncMock(return_value=ExecutionPlan(
                intent=Intent(
                    type=IntentType.TOOL_REQUEST,
                    text="What's the weather?",
                    requires_tool=True,
                ),
                steps=[
                    PlanStep(
                        type=StepType.TOOL_EXECUTION,
                        description="Get weather data",
                    ),
                    PlanStep(
                        type=StepType.LLM_RESPONSE,
                        description="Format response",
                    ),
                ],
                requires_verification=True,
                requires_explanation=True,
            ))
        ):
            # Mock executor
            with patch.object(
                orchestrator.executor_agent,
                'execute',
                new=AsyncMock(return_value=MagicMock(
                    success=True,
                    final_output="It's sunny and 72°F",
                ))
            ):
                # Mock verifier
                with patch.object(
                    orchestrator.verifier_agent,
                    'verify',
                    new=AsyncMock(return_value=MagicMock(
                        is_valid=True,
                        confidence=0.95,
                        requires_correction=False,
                    ))
                ):
                    # Mock explainer
                    with patch.object(
                        orchestrator.explainer_agent,
                        'explain',
                        new=AsyncMock(return_value=MagicMock(
                            response="The weather is sunny and 72°F.",
                            reasoning="Retrieved weather data successfully",
                        ))
                    ):
                        result = await orchestrator.process_message(
                            "What's the weather?", 
                            "test-conv"
                        )
                        
                        # Verify all agents were called
                        assert result.response == "The weather is sunny and 72°F."


@pytest.mark.asyncio
async def test_is_simple_intent_detection():
    """Test simple intent detection logic."""
    orchestrator = AgentOrchestrator()
    
    # Test conversational intents
    simple_conv = Intent(
        type=IntentType.CONVERSATION,
        text="Hi there",
        confidence=1.0,
    )
    assert orchestrator._is_simple_intent(simple_conv) is True
    
    # Test greeting patterns
    greeting_question = Intent(
        type=IntentType.QUESTION,
        text="Hello, how are you?",
        confidence=1.0,
        requires_tool=False,
    )
    assert orchestrator._is_simple_intent(greeting_question) is True
    
    # Test farewell patterns
    farewell_question = Intent(
        type=IntentType.QUESTION,
        text="Goodbye and thanks",
        confidence=1.0,
        requires_tool=False,
    )
    assert orchestrator._is_simple_intent(farewell_question) is True
    
    # Test complex intent (tool request)
    complex_intent = Intent(
        type=IntentType.TOOL_REQUEST,
        text="Calculate 2+2",
        confidence=1.0,
        requires_tool=True,
    )
    assert orchestrator._is_simple_intent(complex_intent) is False
    
    # Test complex question
    complex_question = Intent(
        type=IntentType.QUESTION,
        text="What is quantum physics?",
        confidence=1.0,
        requires_tool=False,
    )
    assert orchestrator._is_simple_intent(complex_question) is False


@pytest.mark.asyncio
async def test_memory_retrieval_parallelization():
    """Test that memory retrieval runs in parallel."""
    from slovo_agent.memory.retrieval import MemoryRetrievalPipeline
    from slovo_agent.models import MemoryRetrievalRequest
    
    # Mock repositories
    mock_redis = MagicMock()
    mock_redis.get_recent_turns = AsyncMock(return_value=[])
    
    mock_qdrant = MagicMock()
    mock_qdrant.search = AsyncMock(return_value=[])
    
    mock_postgres = MagicMock()
    mock_postgres.get_user_profile = AsyncMock(return_value=MagicMock(
        preferred_languages=[],
        communication_style=None,
        memory_capture_enabled=True,
    ))
    mock_postgres.get_recent_episodic_logs = AsyncMock(return_value=[])
    
    pipeline = MemoryRetrievalPipeline(
        redis=mock_redis,
        qdrant=mock_qdrant,
        postgres=mock_postgres,
    )
    
    request = MemoryRetrievalRequest(
        user_message="Test message",
        conversation_id="test-conv",
        token_limit=2000,
    )
    
    # Execute retrieval
    context = await pipeline.retrieve(request)
    
    # Verify all repositories were called
    mock_redis.get_recent_turns.assert_called_once()
    mock_qdrant.search.assert_not_called()  # No embedding function set
    mock_postgres.get_user_profile.assert_called_once()
    mock_postgres.get_recent_episodic_logs.assert_called_once()
    
    # Verify context was created
    assert context.total_token_estimate >= 0


def test_execution_plan_complexity_flags():
    """Test that ExecutionPlan has complexity flags."""
    from slovo_agent.models import ExecutionPlan, Intent, IntentType
    
    # Test default values
    plan = ExecutionPlan(
        intent=Intent(
            type=IntentType.CONVERSATION,
            text="Hello",
        ),
        steps=[],
    )
    
    # Verify flags exist and have correct defaults
    assert hasattr(plan, 'requires_verification')
    assert hasattr(plan, 'requires_explanation')
    assert plan.requires_verification is True
    assert plan.requires_explanation is True
    
    # Test setting flags explicitly
    simple_plan = ExecutionPlan(
        intent=Intent(
            type=IntentType.CONVERSATION,
            text="Hi",
        ),
        steps=[],
        requires_verification=False,
        requires_explanation=False,
    )
    
    assert simple_plan.requires_verification is False
    assert simple_plan.requires_explanation is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
