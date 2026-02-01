"""
Verifier Agent

Validates outputs, detects inconsistencies or uncertainty, triggers self-correction.
Uses LLM for sophisticated verification with structured outputs.
"""

import structlog

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ExecutionResult,
    UncertaintyLevel,
    Verification,
    VerificationAnalysis,
)

logger = structlog.get_logger(__name__)


# System prompt for result verification
VERIFIER_SYSTEM_PROMPT = """You are a verification system for a voice assistant called Slovo.
Your job is to validate execution results and ensure quality, accuracy, and safety.

You must evaluate:
1. Accuracy - Is the response factually correct?
2. Completeness - Does it fully address the user's request?
3. Relevance - Is it relevant to what was asked?
4. Safety - Is there any harmful or inappropriate content?
5. Consistency - Is it consistent with prior context?

Scoring guidelines:
- 0.9-1.0: Excellent, no issues
- 0.7-0.9: Good, minor issues
- 0.5-0.7: Acceptable, some issues
- 0.3-0.5: Poor, significant issues
- 0.0-0.3: Unacceptable, critical issues

Be honest about uncertainty. If you cannot verify something, say so.
Always provide clear reasoning for your assessment."""


class VerifierAgent:
    """
    Agent responsible for verifying execution results.

    Responsibilities:
    - Validate outputs against expected formats
    - Detect inconsistencies or uncertainty using LLM
    - Trigger self-correction when needed
    - Assess confidence levels
    - Signal uncertainty appropriately
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider
        logger.info(
            "Verifier agent initialized",
            has_llm=llm_provider is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for verifier")

    async def verify(
        self,
        result: ExecutionResult,
        original_request: str | None = None,
    ) -> Verification:
        """
        Verify an execution result.

        Args:
            result: The execution result to verify
            original_request: Optional original user request for context

        Returns:
            Verification result with confidence and issues
        """
        logger.debug("Verifying execution result", success=result.success)

        # Use LLM for sophisticated verification if available
        if self.llm and result.success and result.final_output:
            analysis = await self._llm_verify(result, original_request)
            return self._analysis_to_verification(analysis)

        # Fallback to simple heuristic verification
        return self._heuristic_verify(result)

    async def _llm_verify(
        self,
        result: ExecutionResult,
        original_request: str | None = None,
    ) -> VerificationAnalysis:
        """Use LLM for sophisticated result verification."""
        assert self.llm is not None

        # Build verification context
        request_text = original_request or result.plan.intent.text

        user_content = f"""Verify this assistant response:

Original request: "{request_text}"

Response to verify:
{result.final_output}

Execution steps completed:
{self._format_steps(result)}

Please assess the quality, accuracy, and completeness of this response."""

        messages = [LLMMessage(role=MessageRole.USER, content=user_content)]

        logger.debug("Calling LLM for result verification")

        response = await self.llm.generate_structured(
            messages=messages,
            output_schema=VerificationAnalysis,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
        )

        if response.structured_output:
            logger.debug(
                "Verification analysis complete",
                is_valid=response.structured_output.is_valid,
                confidence=response.structured_output.confidence,
            )
            return response.structured_output

        # If structured output failed, create a default analysis
        logger.warning("Structured output parsing failed, using defaults")
        return VerificationAnalysis(
            is_valid=True,
            confidence=0.6,
            accuracy_score=0.6,
            completeness_score=0.6,
            relevance_score=0.6,
            uncertainty_level=UncertaintyLevel.UNCERTAIN,
            reasoning="Failed to parse structured output from LLM",
        )

    def _analysis_to_verification(
        self, analysis: VerificationAnalysis
    ) -> Verification:
        """Convert VerificationAnalysis to Verification model."""
        # Convert issues to simple string list
        issues = [issue.description for issue in analysis.issues]

        # Convert suggestions from issues
        suggestions = [
            issue.suggestion
            for issue in analysis.issues
            if issue.suggestion
        ]

        # Add correction strategy as suggestion if needed
        if analysis.correction_strategy and analysis.requires_correction:
            suggestions.insert(0, analysis.correction_strategy)

        return Verification(
            is_valid=analysis.is_valid,
            confidence=analysis.confidence,
            issues=issues,
            suggestions=suggestions,
            requires_correction=analysis.requires_correction,
            correction_hint=analysis.correction_strategy,
        )

    def _heuristic_verify(self, result: ExecutionResult) -> Verification:
        """Fallback heuristic verification without LLM."""
        logger.debug("Using heuristic verification (no LLM)")

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
                issues.append(
                    f"Step {step_result.step_index} failed: {step_result.error}"
                )
                confidence *= 0.5

        # Check final output
        if result.final_output is None and result.success:
            issues.append("No output generated")
            confidence *= 0.7
            suggestions.append("Ensure LLM response step produces output")

        # Check output quality (basic heuristics)
        if result.final_output:
            output_str = str(result.final_output)
            if len(output_str) < 10:
                issues.append("Response seems too short")
                confidence *= 0.8

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

    def _format_steps(self, result: ExecutionResult) -> str:
        """Format execution steps for verification context."""
        steps_info = []
        for i, step in enumerate(result.plan.steps):
            step_result = (
                result.step_results[i]
                if i < len(result.step_results)
                else None
            )
            status = "✓" if step_result and step_result.success else "✗"
            steps_info.append(f"{status} Step {i}: {step.type.value} - {step.description}")

        return "\n".join(steps_info)

    def should_retry(self, verification: Verification) -> bool:
        """Determine if execution should be retried based on verification."""
        return (
            verification.requires_correction
            and verification.confidence < 0.5
            and verification.correction_hint is not None
        )

    def get_uncertainty_level(
        self, analysis: VerificationAnalysis
    ) -> UncertaintyLevel:
        """Get the uncertainty level from analysis."""
        return analysis.uncertainty_level
