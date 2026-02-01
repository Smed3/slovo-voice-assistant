"""
Explainer Agent

Produces user-facing explanations, summarizes reasoning and actions.
Uses LLM for sophisticated explanations with structured outputs.
"""

import structlog

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ExecutionResult,
    Explanation,
    Intent,
    ResponseGeneration,
    Verification,
)

logger = structlog.get_logger(__name__)


# System prompt for explanation generation
EXPLAINER_SYSTEM_PROMPT = """You are an explanation system for a voice assistant called Slovo.
Your job is to generate clear, helpful responses and explain the assistant's reasoning when needed.

Guidelines:
1. The response should be the primary content the user sees
2. Keep responses conversational and natural
3. If confidence is low, include appropriate caveats
4. When explaining reasoning, be clear but not overwhelming
5. Suggest follow-ups when they would be helpful
6. Match the tone to the context (formal for serious matters, friendly for casual)
7. If something failed or was uncertain, be honest about it

The user should feel informed and supported, not confused or overwhelmed."""


class ExplainerAgent:
    """
    Agent responsible for generating explanations.

    Responsibilities:
    - Produce clear user-facing responses
    - Summarize reasoning and decision process
    - Explain actions taken
    - Communicate uncertainty when appropriate
    - Generate follow-up suggestions
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider
        logger.info(
            "Explainer agent initialized",
            has_llm=llm_provider is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for explainer")

    async def explain(
        self,
        intent: Intent,
        result: ExecutionResult,
        verification: Verification,
    ) -> Explanation:
        """
        Generate an explanation for the execution result.

        Args:
            intent: The original interpreted intent
            result: The execution result
            verification: The verification result

        Returns:
            Explanation with response and reasoning
        """
        logger.debug("Generating explanation", success=result.success)

        # If execution failed, use LLM to explain the failure nicely
        if not result.success:
            return await self._explain_failure(intent, result, verification)

        # Use LLM for sophisticated explanation if available
        if self.llm and result.final_output:
            generation = await self._llm_explain(intent, result, verification)
            return self._generation_to_explanation(result, verification, generation)

        # Fallback to simple explanation
        return self._heuristic_explain(intent, result, verification)

    async def _explain_failure(
        self,
        intent: Intent,
        result: ExecutionResult,
        verification: Verification,
    ) -> Explanation:
        """Generate an explanation for a failed execution."""
        error_message = result.error or "An unknown error occurred"

        if self.llm:
            # Use LLM to generate a friendly failure explanation
            user_content = f"""The assistant failed to complete the user's request.

Original request: "{intent.text}"
Error: {error_message}
Issues: {verification.issues}

Generate a helpful, friendly explanation of what went wrong and what the user can do."""

            messages = [LLMMessage(role=MessageRole.USER, content=user_content)]

            try:
                response = await self.llm.generate_structured(
                    messages=messages,
                    output_schema=ResponseGeneration,
                    system_prompt=EXPLAINER_SYSTEM_PROMPT,
                )

                if response.structured_output:
                    return self._generation_to_explanation(
                        result, verification, response.structured_output
                    )
            except Exception as e:
                logger.warning("Failed to generate LLM explanation", error=str(e))

        # Fallback failure explanation
        return Explanation(
            response=(
                f"I apologize, but I wasn't able to complete your request. "
                f"The issue was: {error_message}"
            ),
            reasoning=f"Execution failed with error: {error_message}",
            actions_taken=[step.description for step in result.plan.steps],
            confidence_note="This request could not be completed successfully.",
        )

    async def _llm_explain(
        self,
        intent: Intent,
        result: ExecutionResult,
        verification: Verification,
    ) -> ResponseGeneration:
        """Use LLM for sophisticated explanation generation."""
        assert self.llm is not None

        # Build context for explanation
        user_content = f"""Generate an explanation for this completed request:

Original request: "{intent.text}"
Intent type: {intent.type.value}

Response generated:
{result.final_output}

Verification:
- Valid: {verification.is_valid}
- Confidence: {verification.confidence:.2f}
- Issues: {verification.issues if verification.issues else "None"}

Steps taken:
{self._format_steps(result)}

Generate a polished explanation with appropriate tone and any needed caveats."""

        messages = [LLMMessage(role=MessageRole.USER, content=user_content)]

        logger.debug("Calling LLM for explanation generation")

        response = await self.llm.generate_structured(
            messages=messages,
            output_schema=ResponseGeneration,
            system_prompt=EXPLAINER_SYSTEM_PROMPT,
        )

        if response.structured_output:
            logger.debug("Explanation generated successfully")
            return response.structured_output

        # If structured output failed, create a default generation
        logger.warning("Structured output parsing failed, using defaults")
        return ResponseGeneration(
            response=str(result.final_output),
            summary="Request processed",
            use_markdown=True,
        )

    def _generation_to_explanation(
        self,
        result: ExecutionResult,
        verification: Verification,
        generation: ResponseGeneration,
    ) -> Explanation:
        """Convert ResponseGeneration to Explanation model."""
        # Build reasoning from details
        reasoning_parts = [generation.summary]
        for detail in generation.details:
            if detail.importance == "high":
                reasoning_parts.append(f"[{detail.category}] {detail.content}")

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else None

        # Build confidence note
        confidence_note = generation.confidence_statement
        if generation.caveats:
            caveat_text = "; ".join(generation.caveats)
            if confidence_note:
                confidence_note = f"{confidence_note} Note: {caveat_text}"
            else:
                confidence_note = f"Note: {caveat_text}"

        return Explanation(
            response=generation.response,
            reasoning=reasoning,
            actions_taken=[step.description for step in result.plan.steps],
            confidence_note=confidence_note,
        )

    def _heuristic_explain(
        self,
        intent: Intent,
        result: ExecutionResult,
        verification: Verification,
    ) -> Explanation:
        """Fallback heuristic explanation without LLM."""
        logger.debug("Using heuristic explanation (no LLM)")

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
        actions = [step.description for step in result.plan.steps]

        # Add confidence note if low
        confidence_note = None
        if verification.confidence < 0.7:
            confidence_note = (
                "I'm not entirely confident in this response. "
                "Please verify the information."
            )

        return Explanation(
            response=response,
            reasoning=reasoning,
            actions_taken=actions,
            confidence_note=confidence_note,
        )

    def _format_steps(self, result: ExecutionResult) -> str:
        """Format execution steps for context."""
        steps_info = []
        for i, step in enumerate(result.plan.steps):
            step_result = (
                result.step_results[i]
                if i < len(result.step_results)
                else None
            )
            status = "✓" if step_result and step_result.success else "✗"
            steps_info.append(f"{status} {step.type.value}: {step.description}")

        return "\n".join(steps_info)
