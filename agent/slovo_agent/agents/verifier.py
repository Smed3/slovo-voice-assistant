"""
Verifier Agent

Validates outputs, detects inconsistencies or uncertainty, triggers self-correction.
"""

import structlog

from slovo_agent.models import ExecutionResult, Verification

logger = structlog.get_logger(__name__)


class VerifierAgent:
    """
    Agent responsible for verifying execution results.
    
    Responsibilities:
    - Validate outputs against expected formats
    - Detect inconsistencies or uncertainty
    - Trigger self-correction when needed
    - Assess confidence levels
    """
    
    def __init__(self) -> None:
        logger.info("Verifier agent initialized")
    
    async def verify(self, result: ExecutionResult) -> Verification:
        """
        Verify an execution result.
        """
        logger.debug("Verifying execution result", success=result.success)
        
        issues: list[str] = []
        suggestions: list[str] = []
        confidence = 1.0
        
        # Check overall success
        if not result.success:
            issues.append("Execution failed")
            confidence *= 0.3
            
            if result.error:
                suggestions.append(f"Address error: {result.error}")
        
        # Verify each step
        for step_result in result.step_results:
            if not step_result.success:
                issues.append(f"Step {step_result.step_index} failed: {step_result.error}")
                confidence *= 0.5
        
        # Check final output
        if result.final_output is None and result.success:
            issues.append("No output generated")
            confidence *= 0.7
            suggestions.append("Ensure LLM response step produces output")
        
        # Determine if correction is needed
        requires_correction = confidence < 0.5 or len(issues) > 0
        
        return Verification(
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
            requires_correction=requires_correction,
            correction_hint=suggestions[0] if suggestions else None,
        )
