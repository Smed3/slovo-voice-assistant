"""
Executor Agent

Executes approved tools in sandboxed environments, handles retries and partial failures.
Uses LLM for response generation with structured outputs.
"""

from typing import Any

import structlog

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ExecutionPlan,
    ExecutionResult,
    MemoryContext,
    PlanStep,
    StepResult,
    StepType,
)

logger = structlog.get_logger(__name__)


# System prompt for LLM response generation
LLM_RESPONSE_SYSTEM_PROMPT = """You are Slovo, a helpful, intelligent voice assistant.
You are friendly, knowledgeable, and aim to provide accurate, helpful responses.

Guidelines:
1. Be conversational but informative
2. If you're uncertain about something, say so honestly
3. Keep responses concise but complete
4. Use the provided context to give relevant, personalized responses
5. If the user's request requires capabilities you don't have, explain what you can help with instead

Current context will be provided including any retrieved memories and tool outputs."""


class ExecutorAgent:
    """
    Agent responsible for executing plans.

    Responsibilities:
    - Execute each step in the plan
    - Manage tool sandbox execution
    - Handle retries and partial failures
    - Generate LLM responses using the provider
    - Aggregate results
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider
        self.max_retries = 2
        logger.info(
            "Executor agent initialized",
            has_llm=llm_provider is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for executor")

    async def execute(
        self,
        plan: ExecutionPlan,
        conversation_history: list[dict[str, str]] | None = None,
        memory_context: MemoryContext | None = None,
    ) -> ExecutionResult:
        """
        Execute an execution plan.

        Args:
            plan: The execution plan to execute
            conversation_history: Optional conversation history for context
            memory_context: Memory context with user info and relevant memories

        Returns:
            ExecutionResult with all step results
        """
        logger.debug("Executing plan", steps=len(plan.steps), has_memory=memory_context is not None)

        step_results: list[StepResult] = []
        context: dict[str, Any] = {
            "intent": plan.intent.text,
            "conversation_history": conversation_history or [],
            "memory_context": memory_context,
        }

        for i, step in enumerate(plan.steps):
            try:
                result = await self._execute_step(step, i, context)
                step_results.append(result)

                if result.success:
                    context[f"step_{i}"] = result.output
                else:
                    # Stop execution on failure (unless configured otherwise)
                    logger.warning("Step failed", step_index=i, error=result.error)
                    return ExecutionResult(
                        plan=plan,
                        success=False,
                        step_results=step_results,
                        error=result.error,
                    )

            except Exception as e:
                logger.error("Step execution error", step_index=i, error=str(e))
                step_results.append(
                    StepResult(
                        step_index=i,
                        success=False,
                        error=str(e),
                    )
                )
                return ExecutionResult(
                    plan=plan,
                    success=False,
                    step_results=step_results,
                    error=str(e),
                )

        # Get final output from the last step
        final_output = step_results[-1].output if step_results else None

        return ExecutionResult(
            plan=plan,
            success=True,
            step_results=step_results,
            final_output=final_output,
        )

    async def _execute_step(
        self,
        step: PlanStep,
        index: int,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute a single step."""
        logger.debug("Executing step", index=index, type=step.type.value)

        if step.type == StepType.MEMORY_RETRIEVAL:
            return await self._execute_memory_retrieval(index, context)

        elif step.type == StepType.TOOL_EXECUTION:
            return await self._execute_tool(step, index, context)

        elif step.type == StepType.TOOL_DISCOVERY:
            return await self._execute_tool_discovery(index, context)

        elif step.type == StepType.LLM_RESPONSE:
            return await self._execute_llm_response(index, context)

        elif step.type == StepType.CLARIFICATION:
            return StepResult(
                step_index=index,
                success=True,
                output={"needs_clarification": True},
            )

        else:
            return StepResult(
                step_index=index,
                success=False,
                error=f"Unknown step type: {step.type}",
            )

    async def _execute_memory_retrieval(
        self,
        index: int,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute memory retrieval step."""
        # TODO: Implement actual memory retrieval from Qdrant/Redis
        logger.debug("Retrieving memories for context")

        # For now, return empty memories
        # In Phase 3, this will query the memory subsystem
        return StepResult(
            step_index=index,
            success=True,
            output={
                "memories": [],
                "relevant_context": "",
            },
        )

    async def _execute_tool(
        self,
        step: PlanStep,
        index: int,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute a tool in the sandbox."""
        # TODO: Implement sandboxed tool execution via Docker
        logger.debug("Executing tool", tool_name=step.tool_name)

        # For now, return placeholder
        # In Phase 4, this will execute in Docker sandbox
        return StepResult(
            step_index=index,
            success=True,
            output={
                "tool_name": step.tool_name,
                "result": "Tool execution not yet implemented",
                "params": step.tool_params,
            },
        )

    async def _execute_tool_discovery(
        self,
        index: int,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute tool discovery step."""
        # TODO: Implement tool discovery via API search
        logger.debug("Discovering tools for request")

        # For now, return empty discovery
        # In Phase 4, this will search for and propose tools
        return StepResult(
            step_index=index,
            success=True,
            output={
                "discovered_tools": [],
                "recommendation": "No tools discovered yet",
            },
        )

    async def _execute_llm_response(
        self,
        index: int,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute LLM response generation step."""
        if not self.llm:
            # Fallback without LLM
            return StepResult(
                step_index=index,
                success=True,
                output=self._generate_fallback_response(context),
            )

        logger.debug("Generating LLM response")

        try:
            # Build messages from context
            messages = self._build_response_messages(context)

            response = await self.llm.generate(
                messages=messages,
                system_prompt=LLM_RESPONSE_SYSTEM_PROMPT,
            )

            logger.debug(
                "LLM response generated",
                tokens=response.usage.get("total_tokens", 0),
            )

            return StepResult(
                step_index=index,
                success=True,
                output=response.content,
            )

        except Exception as e:
            logger.error("LLM response generation failed", error=str(e))
            return StepResult(
                step_index=index,
                success=False,
                error=f"Failed to generate response: {str(e)}",
            )

    def _build_response_messages(
        self, context: dict[str, Any]
    ) -> list[LLMMessage]:
        """Build messages for LLM response generation."""
        messages: list[LLMMessage] = []

        # Add conversation history if available
        history = context.get("conversation_history", [])
        for msg in history[-10:]:  # Keep last 10 messages for context
            role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
            messages.append(LLMMessage(role=role, content=msg.get("content", "")))

        # Build context summary
        context_parts = []

        # Add memory context from pre-retrieval pipeline (prioritize this)
        memory_ctx: MemoryContext | None = context.get("memory_context")
        if memory_ctx:
            if memory_ctx.user_profile_summary:
                context_parts.append(f"User Profile: {memory_ctx.user_profile_summary}")
            if memory_ctx.relevant_memories_summary:
                context_parts.append(f"Relevant Memories (IMPORTANT - use to personalize response): {memory_ctx.relevant_memories_summary}")
            if memory_ctx.recent_conversation_summary:
                context_parts.append(f"Recent Conversation: {memory_ctx.recent_conversation_summary}")
            if memory_ctx.episodic_context_summary:
                context_parts.append(f"Past Actions: {memory_ctx.episodic_context_summary}")
        
        # Fallback to step-based memories if no pre-retrieved context
        if not context_parts:
            memories = context.get("step_0", {}).get("memories", [])
            if memories:
                context_parts.append(f"Relevant memories: {memories}")

        # Add tool outputs
        for key, value in context.items():
            if key.startswith("step_") and key != "step_0":
                if isinstance(value, dict) and "tool_name" in value:
                    context_parts.append(
                        f"Tool '{value['tool_name']}' result: {value.get('result', 'N/A')}"
                    )

        # Add current request with context
        intent = context.get("intent", "")
        if context_parts:
            user_message = f"""Context:
{chr(10).join(context_parts)}

User request: {intent}

Please provide a helpful response based on the above context."""
        else:
            user_message = intent

        messages.append(LLMMessage(role=MessageRole.USER, content=user_message))

        return messages

    def _generate_fallback_response(self, context: dict[str, Any]) -> str:
        """Generate a fallback response when LLM is not available."""
        intent = context.get("intent", "")

        return (
            f"Hello! I'm Slovo, your voice assistant. "
            f"I received your message: \"{intent[:100]}{'...' if len(intent) > 100 else ''}\". "
            f"I'm currently running in limited mode without full language model capabilities. "
            f"Please ensure your API keys are configured to enable intelligent responses."
        )
