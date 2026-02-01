"""
Agent orchestrator that coordinates all agent interactions.

Integrates with LLM providers for intelligent reasoning and
supports clarification requests for uncertain situations.
"""

from typing import AsyncGenerator

import structlog

from slovo_agent.agents.executor import ExecutorAgent
from slovo_agent.agents.explainer import ExplainerAgent
from slovo_agent.agents.intent import IntentInterpreterAgent
from slovo_agent.agents.planner import PlannerAgent
from slovo_agent.agents.verifier import VerifierAgent
from slovo_agent.llm.base import LLMProvider
from slovo_agent.llm.factory import LLMProviderError, get_default_provider
from slovo_agent.models import (
    AgentResult,
    ClarificationRequest,
    ConversationContext,
    IntentType,
)

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

    Supports:
    - Clarification requests when intent is unclear
    - Self-correction on verification failures
    - Conversation context tracking
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        # Initialize LLM provider
        self.llm: LLMProvider | None = llm_provider
        self._init_llm_provider()

        # Initialize agents with LLM provider
        self.intent_agent = IntentInterpreterAgent(self.llm)
        self.planner_agent = PlannerAgent(self.llm)
        self.executor_agent = ExecutorAgent(self.llm)
        self.verifier_agent = VerifierAgent(self.llm)
        self.explainer_agent = ExplainerAgent(self.llm)

        # Conversation tracking
        self.conversations: dict[str, ConversationContext] = {}
        self.pending_clarifications: dict[str, ClarificationRequest] = {}

        # Configuration
        self.max_retries = 2

        logger.info(
            "Agent orchestrator initialized",
            has_llm=self.llm is not None,
        )

    def _init_llm_provider(self) -> None:
        """Initialize LLM provider if not provided."""
        if self.llm is not None:
            return

        try:
            self.llm = get_default_provider()
            logger.info("Default LLM provider initialized")
        except LLMProviderError as e:
            logger.warning(
                "No LLM provider available, running in limited mode",
                error=str(e),
            )
            self.llm = None

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider for all agents."""
        self.llm = provider

        # Update all agents
        self.intent_agent.set_llm_provider(provider)
        self.planner_agent.set_llm_provider(provider)
        self.executor_agent.set_llm_provider(provider)
        self.verifier_agent.set_llm_provider(provider)
        self.explainer_agent.set_llm_provider(provider)

        logger.info("LLM provider updated for all agents")

    async def process_message(
        self,
        message: str,
        conversation_id: str,
    ) -> AgentResult:
        """
        Process a user message through the agent pipeline.

        Args:
            message: The user's message
            conversation_id: Unique conversation identifier

        Returns:
            AgentResult with response and metadata
        """
        logger.info(
            "Processing message",
            conversation_id=conversation_id,
            message_length=len(message),
        )

        # Get or create conversation context
        context = self._get_conversation_context(conversation_id)

        try:
            # Check if this is a response to a pending clarification
            if conversation_id in self.pending_clarifications:
                return await self._handle_clarification_response(
                    message, conversation_id, context
                )

            # Step 1: Interpret intent
            intent = await self.intent_agent.interpret(
                message,
                conversation_context=self._build_context_string(context),
            )
            logger.debug("Intent interpreted", intent_type=intent.type.value)

            # Check if clarification is needed from intent interpretation
            # Note: We check via the interpret method's internal analysis

            # Step 2: Create plan
            plan = await self.planner_agent.create_plan(
                intent,
                conversation_context=self._build_context_string(context),
            )
            logger.debug("Plan created", steps=len(plan.steps) if plan.steps else 0)

            # Check if plan requires clarification
            if self._plan_needs_clarification(plan):
                return await self._request_clarification_from_plan(
                    conversation_id, plan
                )

            # Step 3: Execute plan
            execution_result = await self.executor_agent.execute(
                plan,
                conversation_history=self._get_conversation_history(context),
            )
            logger.debug("Plan executed", success=execution_result.success)

            # Step 4: Verify results
            verification = await self.verifier_agent.verify(
                execution_result,
                original_request=message,
            )
            logger.debug("Results verified", valid=verification.is_valid)

            # Self-correction if needed
            if verification.requires_correction and self.max_retries > 0:
                execution_result, verification = await self._attempt_correction(
                    plan, execution_result, verification, message
                )

            # Step 5: Generate explanation
            explanation = await self.explainer_agent.explain(
                intent=intent,
                result=execution_result,
                verification=verification,
            )

            # Update conversation context
            self._update_conversation_context(
                context, message, explanation.response
            )

            return AgentResult(
                response=explanation.response,
                reasoning=explanation.reasoning,
                confidence=verification.confidence,
            )

        except Exception as e:
            logger.error("Error processing message", error=str(e))
            return AgentResult(
                response=(
                    "I apologize, but I encountered an error processing your request. "
                    "Please try again."
                ),
                reasoning=f"Error: {str(e)}",
                confidence=0.0,
            )

    async def _attempt_correction(
        self,
        plan,
        execution_result,
        verification,
        original_message: str,
    ):
        """Attempt to correct a failed or low-confidence result."""
        logger.info("Attempting self-correction", hint=verification.correction_hint)

        # Re-execute with the correction hint as additional context
        # For now, just retry the execution
        # In a more sophisticated implementation, this could modify the plan

        for attempt in range(self.max_retries):
            logger.debug("Correction attempt", attempt=attempt + 1)

            # Re-execute
            execution_result = await self.executor_agent.execute(
                plan,
                conversation_history=[
                    {"role": "user", "content": original_message},
                    {"role": "system", "content": f"Previous attempt had issues: {verification.issues}. Correction hint: {verification.correction_hint}"},
                ],
            )

            # Re-verify
            verification = await self.verifier_agent.verify(
                execution_result,
                original_request=original_message,
            )

            if not verification.requires_correction:
                logger.info("Self-correction successful", attempt=attempt + 1)
                break

        return execution_result, verification

    def _plan_needs_clarification(self, plan) -> bool:
        """Check if the plan requires clarification before execution."""
        from slovo_agent.models import StepType

        # Check if any step is a clarification step
        for step in plan.steps:
            if step.type == StepType.CLARIFICATION:
                return True

        return False

    async def _request_clarification_from_plan(
        self,
        conversation_id: str,
        plan,
    ) -> AgentResult:
        """Generate a clarification request based on the plan."""
        # Create a generic clarification request
        clarification = ClarificationRequest(
            needed=True,
            reason="ambiguous_intent",
            question="Could you please provide more details about what you'd like me to do?",
            options=[],
            context="Your request seems ambiguous or incomplete.",
        )

        # Store the pending clarification
        self.pending_clarifications[conversation_id] = clarification

        return AgentResult(
            response=clarification.question or "Could you please clarify your request?",
            reasoning="Requesting clarification before proceeding",
            confidence=0.5,
        )

    async def _handle_clarification_response(
        self,
        message: str,
        conversation_id: str,
        context: ConversationContext,
    ) -> AgentResult:
        """Handle a user's response to a clarification request."""
        # Remove the pending clarification
        clarification = self.pending_clarifications.pop(conversation_id, None)

        logger.debug(
            "Handling clarification response",
            original_question=clarification.question if clarification else None,
        )

        # Process the clarified message normally
        # The context from the clarification should help interpretation
        return await self.process_message(
            message=f"[Clarification] {message}",
            conversation_id=conversation_id,
        )

    def _get_conversation_context(self, conversation_id: str) -> ConversationContext:
        """Get or create conversation context."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext()

        return self.conversations[conversation_id]

    def _build_context_string(self, context: ConversationContext) -> str:
        """Build a context string from conversation context."""
        parts = []

        if context.recent_topics:
            parts.append(f"Recent topics: {', '.join(context.recent_topics)}")

        if context.user_preferences:
            prefs = [f"{k}: {v}" for k, v in context.user_preferences.items()]
            parts.append(f"User preferences: {', '.join(prefs)}")

        if context.conversation_language != "en":
            parts.append(f"Conversation language: {context.conversation_language}")

        parts.append(f"Turn count: {context.turn_count}")

        return "\n".join(parts) if parts else ""

    def _get_conversation_history(
        self, context: ConversationContext
    ) -> list[dict[str, str]]:
        """Get conversation history for the executor."""
        # This would typically fetch from the memory system
        # For now, return empty history
        return []

    def _update_conversation_context(
        self,
        context: ConversationContext,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Update conversation context after a turn."""
        context.turn_count += 1

        # Extract topics from the message (simple heuristic)
        # In a full implementation, this would use the intent analysis
        words = user_message.lower().split()
        for word in words:
            if len(word) > 5 and word not in context.recent_topics:
                context.recent_topics.append(word)

        # Keep only recent topics
        context.recent_topics = context.recent_topics[-5:]

    async def process_message_stream(
        self,
        message: str,
        conversation_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a message and stream the response.

        Args:
            message: The user's message
            conversation_id: Unique conversation identifier

        Yields:
            Chunks of the response as they become available
        """
        # For now, process completely and then stream
        # TODO: Implement true streaming with LLM streaming
        result = await self.process_message(message, conversation_id)

        # Simulate streaming by yielding chunks
        words = result.response.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word

    def request_clarification(
        self,
        conversation_id: str,
        clarification: ClarificationRequest,
    ) -> AgentResult:
        """
        Explicitly request clarification from the user.

        Args:
            conversation_id: The conversation to request clarification in
            clarification: The clarification request details

        Returns:
            AgentResult with the clarification question
        """
        self.pending_clarifications[conversation_id] = clarification

        response = clarification.question or "Could you please provide more details?"

        if clarification.options:
            options_text = "\n".join(f"- {opt}" for opt in clarification.options)
            response = f"{response}\n\nOptions:\n{options_text}"

        return AgentResult(
            response=response,
            reasoning=f"Requesting clarification: {clarification.reason}",
            confidence=0.5,
        )

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation context and pending clarifications."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

        if conversation_id in self.pending_clarifications:
            del self.pending_clarifications[conversation_id]

        logger.info("Conversation cleared", conversation_id=conversation_id)
