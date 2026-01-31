"""
Explainer Agent

Produces user-facing explanations, summarizes reasoning and actions.
"""

from dataclasses import dataclass
from typing import Optional

import structlog

from slovo_agent.agents.intent import Intent
from slovo_agent.agents.executor import ExecutionResult
from slovo_agent.agents.verifier import Verification

logger = structlog.get_logger()


@dataclass
class Explanation:
    """User-facing explanation of agent actions."""
    
    response: str
    reasoning: Optional[str] = None
    actions_taken: list[str] = None
    confidence_note: Optional[str] = None
    
    def __post_init__(self):
        if self.actions_taken is None:
            self.actions_taken = []


class ExplainerAgent:
    """
    Agent responsible for generating explanations.
    
    Responsibilities:
    - Produce clear user-facing responses
    - Summarize reasoning and decision process
    - Explain actions taken
    - Communicate uncertainty when appropriate
    """
    
    def __init__(self) -> None:
        logger.info("Explainer agent initialized")
    
    async def explain(
        self,
        intent: Intent,
        result: ExecutionResult,
        verification: Verification,
    ) -> Explanation:
        """
        Generate an explanation for the execution result.
        """
        logger.debug("Generating explanation", success=result.success)
        
        # Get the main response from execution result
        if result.success and result.final_output:
            response = str(result.final_output)
        else:
            response = "I apologize, but I wasn't able to complete your request."
            if result.error:
                response += f" The issue was: {result.error}"
        
        # Build reasoning summary
        reasoning_parts = []
        reasoning_parts.append(f"Understood intent: {intent.type.value}")
        reasoning_parts.append(f"Executed {len(result.step_results)} steps")
        
        if verification.issues:
            reasoning_parts.append(f"Issues found: {', '.join(verification.issues)}")
        
        reasoning = " | ".join(reasoning_parts)
        
        # List actions taken
        actions = [
            step.description 
            for step in result.plan.steps
        ]
        
        # Add confidence note if low
        confidence_note = None
        if verification.confidence < 0.7:
            confidence_note = "I'm not entirely confident in this response. Please verify the information."
        
        return Explanation(
            response=response,
            reasoning=reasoning,
            actions_taken=actions,
            confidence_note=confidence_note,
        )
