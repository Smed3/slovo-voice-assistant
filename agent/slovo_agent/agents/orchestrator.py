"""
Agent orchestrator that coordinates all agent interactions.

Integrates with LLM providers for intelligent reasoning and
supports clarification requests for uncertain situations.
"""

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator

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
    ExecutionPlan,
    IntentType,
    MemoryContext,
    MemorySource,
    MemoryType,
    MemoryWriteRequest,
    PlanStep,
    StepType,
    VerifierMemoryApproval,
)

if TYPE_CHECKING:
    from slovo_agent.memory import MemoryManager

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

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        memory_manager: "MemoryManager | None" = None,
    ) -> None:
        # Initialize LLM provider
        self.llm: LLMProvider | None = llm_provider
        self._init_llm_provider()

        # Memory manager (optional, enables long-term memory)
        self._memory: "MemoryManager | None" = memory_manager

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
            has_memory=self._memory is not None,
        )

    def set_memory_manager(self, manager: "MemoryManager") -> None:
        """Set memory manager for long-term memory support."""
        self._memory = manager
        logger.info("Memory manager set for orchestrator")

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
            # Store the user message in short-term memory
            if self._memory is not None:
                try:
                    await self._memory.store_turn(
                        conversation_id=conversation_id,
                        role="user",
                        content=message,
                    )
                    logger.info("User turn stored in memory", conversation_id=conversation_id)
                except Exception as e:
                    logger.warning("Failed to store user turn", error=str(e))
            else:
                logger.warning("Memory manager not available - turns will not be persisted")

            # Check if this is a response to a pending clarification
            if conversation_id in self.pending_clarifications:
                return await self._handle_clarification_response(
                    message, conversation_id, context
                )

            # OPTIMIZATION: Parallelize memory retrieval and intent interpretation
            # These are independent operations
            memory_context: MemoryContext | None = None
            memory_task = None
            if self._memory is not None:
                memory_task = asyncio.create_task(
                    self._memory.retrieve_context(
                        user_message=message,
                        conversation_id=conversation_id,
                    )
                )

            # Build context string for intent (without full memory yet)
            context_string = self._build_context_string(context)

            # Step 1: Interpret intent
            intent = await self.intent_agent.interpret(
                message,
                conversation_context=context_string,
            )
            logger.debug("Intent interpreted", intent_type=intent.type.value)

            # Wait for memory retrieval to complete
            if memory_task is not None:
                try:
                    memory_context = await memory_task
                    logger.debug(
                        "Memory context retrieved",
                        has_profile=bool(memory_context.user_profile_summary),
                        has_semantic=bool(memory_context.relevant_memories_summary),
                        has_conversation=bool(memory_context.recent_conversation_summary),
                        total_tokens=memory_context.total_token_estimate,
                    )
                except Exception as e:
                    logger.warning("Failed to retrieve memory context", error=str(e))

            # Build full context string with memory
            context_string = self._build_context_string_with_memory(context, memory_context)

            # OPTIMIZATION: Fast path for simple intents
            # Skip planner, verifier, and explainer for conversational intents
            if self._is_simple_intent(intent):
                logger.info("Fast path: simple intent detected", intent_type=intent.type.value)
                
                # Create a minimal plan with just LLM response
                plan = ExecutionPlan(
                    intent=intent,
                    steps=[
                        PlanStep(
                            type=StepType.LLM_RESPONSE,
                            description="Generate conversational response",
                        )
                    ],
                    estimated_complexity="simple",
                    requires_verification=False,
                    requires_explanation=False,
                )

                # Execute directly
                execution_result = await self.executor_agent.execute(
                    plan,
                    conversation_history=self._get_conversation_history(context),
                    memory_context=memory_context,
                )
                logger.debug("Fast path execution complete", success=execution_result.success)

                # Extract response directly from execution result
                response = execution_result.final_output or "I'm here to help!"
                
                # Update conversation context
                self._update_conversation_context(context, message, response)

                # Store assistant response
                if self._memory is not None:
                    try:
                        await self._memory.store_turn(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=response,
                        )
                    except Exception as e:
                        logger.warning("Failed to store assistant turn", error=str(e))

                return AgentResult(
                    response=response,
                    reasoning="Simple conversational response",
                    confidence=1.0,
                )

            # Step 2: Create plan (for complex intents)
            plan = await self.planner_agent.create_plan(
                intent,
                conversation_context=context_string,
            )
            logger.debug(
                "Plan created",
                steps=len(plan.steps) if plan.steps else 0,
                requires_verification=plan.requires_verification,
                requires_explanation=plan.requires_explanation,
            )

            # Check if plan requires clarification
            if self._plan_needs_clarification(plan):
                return await self._request_clarification_from_plan(
                    conversation_id, plan
                )

            # Step 3: Execute plan (with memory context for personalized responses)
            execution_result = await self.executor_agent.execute(
                plan,
                conversation_history=self._get_conversation_history(context),
                memory_context=memory_context,
            )
            logger.debug("Plan executed", success=execution_result.success)

            # OPTIMIZATION: Skip verification for low-risk plans
            verification = None
            if plan.requires_verification:
                # Step 4: Verify results (with memory context for consistency checking)
                verification = await self.verifier_agent.verify(
                    execution_result,
                    original_request=message,
                    memory_context=memory_context,
                )
                logger.debug("Results verified", valid=verification.is_valid)

                # Self-correction if needed
                if verification.requires_correction and self.max_retries > 0:
                    execution_result, verification = await self._attempt_correction(
                        plan, execution_result, verification, message
                    )
            else:
                logger.debug("Verification skipped for low-risk plan")
                # Create a simple verification result
                from slovo_agent.models import Verification
                verification = Verification(
                    is_valid=True,
                    confidence=0.9,
                    issues=[],
                    correction_hint=None,
                )

            # OPTIMIZATION: Skip explainer if execution produced direct response
            # and explanation is not required
            explanation = None
            if not plan.requires_explanation and execution_result.final_output:
                logger.debug("Explainer skipped - using direct execution output")
                response = execution_result.final_output
                reasoning = "Direct execution response"
            else:
                # Step 5: Generate explanation (with memory context for personalization)
                explanation = await self.explainer_agent.explain(
                    intent=intent,
                    result=execution_result,
                    verification=verification,
                    memory_context=memory_context,
                )
                response = explanation.response
                reasoning = explanation.reasoning

            # Update conversation context
            self._update_conversation_context(context, message, response)

            # Store assistant response in short-term memory
            if self._memory is not None:
                try:
                    await self._memory.store_turn(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=response,
                    )
                    # Try to extract and store any memorable facts
                    await self._extract_and_store_memories(
                        message, response, verification
                    )
                except Exception as e:
                    logger.warning("Failed to store memories", error=str(e))

            return AgentResult(
                response=response,
                reasoning=reasoning,
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

    def _is_simple_intent(self, intent) -> bool:
        """
        Check if an intent is simple and can use the fast path.
        
        Simple intents include greetings, farewells, and basic conversation
        that don't require tool execution or complex reasoning.
        """
        # Conversational intents are typically simple
        if intent.type == IntentType.CONVERSATION:
            return True
        
        # Questions that don't require tools are simple
        if intent.type == IntentType.QUESTION and not intent.requires_tool:
            # Check for greeting patterns
            message_lower = intent.text.lower()
            greeting_patterns = [
                "hello", "hi", "hey", "greetings", "good morning", 
                "good afternoon", "good evening", "howdy",
                "goodbye", "bye", "see you", "farewell",
                "thanks", "thank you", "thx",
            ]
            if any(pattern in message_lower for pattern in greeting_patterns):
                return True
        
        return False

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

    def _build_context_string_with_memory(
        self,
        context: ConversationContext,
        memory_context: MemoryContext | None,
    ) -> str:
        """Build context string including memory."""
        parts = []

        # Add memory context first (summaries from retrieval pipeline)
        if memory_context:
            # User profile summary
            if memory_context.user_profile_summary:
                parts.append(f"User profile: {memory_context.user_profile_summary}")

            # Recent conversation summary
            if memory_context.recent_conversation_summary:
                parts.append(f"Recent context: {memory_context.recent_conversation_summary}")

            # Relevant memories summary
            if memory_context.relevant_memories_summary:
                parts.append(f"Relevant memories: {memory_context.relevant_memories_summary}")

            # Episodic context summary
            if memory_context.episodic_context_summary:
                parts.append(f"Past actions: {memory_context.episodic_context_summary}")

        # Add regular conversation context
        base_context = self._build_context_string(context)
        if base_context:
            parts.append(base_context)

        return "\n\n".join(parts) if parts else ""

    async def _extract_and_store_memories(
        self,
        user_message: str,
        assistant_response: str,
        verification: "VerificationResult",  # type: ignore
    ) -> None:
        """Extract memorable facts from conversation and store them."""
        if self._memory is None:
            return

        # Look for patterns that indicate memorable information
        # This is a simple heuristic - could be enhanced with LLM extraction
        memorable_patterns = [
            "my name is",
            "i am called",
            "call me",
            "i prefer",
            "i like",
            "i don't like",
            "i live in",
            "i work at",
            "i work as",
            "my favorite",
            "remember that",
            "please remember",
            "don't forget",
        ]

        message_lower = user_message.lower()
        for pattern in memorable_patterns:
            if pattern in message_lower:
                # Extract the fact and store it
                try:
                    # Create a simple write request
                    request = MemoryWriteRequest(
                        content=user_message,
                        memory_type=MemoryType.SEMANTIC,
                        source=MemorySource.CONVERSATION,
                        confidence=0.8,
                        metadata={"original_message": user_message},
                    )
                    # Auto-approve for simple facts
                    approval = VerifierMemoryApproval(
                        approved=True,
                        reason="User explicitly shared personal information",
                        confidence=0.8,
                    )
                    result = await self._memory.write_memory(request, approval)
                    if result.success:
                        logger.info("Stored memorable fact", pattern=pattern, memory_id=str(result.memory_id))
                    else:
                        logger.warning("Memory write failed", error=result.error)
                except Exception as e:
                    logger.warning("Failed to store memory", error=str(e))
                break  # Only store once per message

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
