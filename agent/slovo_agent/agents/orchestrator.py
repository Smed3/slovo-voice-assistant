"""
Agent orchestrator that coordinates all agent interactions.
"""

from typing import AsyncGenerator

import structlog

from slovo_agent.agents.executor import ExecutorAgent
from slovo_agent.agents.explainer import ExplainerAgent
from slovo_agent.agents.intent import IntentInterpreterAgent
from slovo_agent.agents.planner import PlannerAgent
from slovo_agent.agents.verifier import VerifierAgent
from slovo_agent.models import AgentResult

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """
    Orchestrates the multi-agent pipeline for processing user requests.
    
    Pipeline:
    1. Intent Interpreter - Parse and understand user intent
    2. Planner - Create execution plan
    3. Executor - Execute planned actions
    4. Verifier - Validate results
    5. Explainer - Generate user-facing response
    """
    
    def __init__(self) -> None:
        self.intent_agent = IntentInterpreterAgent()
        self.planner_agent = PlannerAgent()
        self.executor_agent = ExecutorAgent()
        self.verifier_agent = VerifierAgent()
        self.explainer_agent = ExplainerAgent()
        
        logger.info("Agent orchestrator initialized")
    
    async def process_message(
        self,
        message: str,
        conversation_id: str,
    ) -> AgentResult:
        """
        Process a user message through the agent pipeline.
        """
        logger.info(
            "Processing message",
            conversation_id=conversation_id,
            message_length=len(message),
        )
        
        try:
            # Step 1: Interpret intent
            intent = await self.intent_agent.interpret(message)
            logger.debug("Intent interpreted", intent=intent)
            
            # Step 2: Create plan
            plan = await self.planner_agent.create_plan(intent)
            logger.debug("Plan created", steps=len(plan.steps) if plan.steps else 0)
            
            # Step 3: Execute plan
            execution_result = await self.executor_agent.execute(plan)
            logger.debug("Plan executed", success=execution_result.success)
            
            # Step 4: Verify results
            verification = await self.verifier_agent.verify(execution_result)
            logger.debug("Results verified", valid=verification.is_valid)
            
            # Step 5: Generate explanation
            explanation = await self.explainer_agent.explain(
                intent=intent,
                result=execution_result,
                verification=verification,
            )
            
            return AgentResult(
                response=explanation.response,
                reasoning=explanation.reasoning,
                confidence=verification.confidence,
            )
            
        except Exception as e:
            logger.error("Error processing message", error=str(e))
            return AgentResult(
                response="I apologize, but I encountered an error processing your request. Please try again.",
                reasoning=f"Error: {str(e)}",
                confidence=0.0,
            )
    
    async def process_message_stream(
        self,
        message: str,
        conversation_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a message and stream the response.
        """
        # For now, just yield the complete response
        # TODO: Implement true streaming with LangGraph
        result = await self.process_message(message, conversation_id)
        
        # Simulate streaming by yielding chunks
        words = result.response.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word
