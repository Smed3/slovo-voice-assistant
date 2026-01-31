"""
Explainer Agent

Produces user-facing explanations, summarizes reasoning and actions.
"""

import structlog

from slovo_agent.models import (
    ExecutionResult,
    Explanation,
    Intent,
    Verification,
)

logger = structlog.get_logger(__name__)


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
        reasoning_parts: list[str] = []
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
