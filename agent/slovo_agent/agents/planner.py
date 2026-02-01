"""
Planner Agent

Determines if existing tools can satisfy intent, plans multi-step execution,
and decides when tool discovery is required.
Uses LLM for sophisticated planning with structured outputs.
"""

import structlog

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ClarificationRequest,
    ExecutionPlan,
    ExecutionPlanAnalysis,
    Intent,
    PlanStep,
    StepType,
    ToolManifest,
)

logger = structlog.get_logger(__name__)


# System prompt for execution planning
PLANNER_SYSTEM_PROMPT = """You are an execution planning system for a voice assistant called Slovo.
Your job is to create optimal execution plans for user requests.

Available step types:
- llm_response: Generate a response using language model reasoning
- tool_execution: Execute a specific tool (requires tool_name)
- tool_discovery: Search for and integrate a new tool capability
- memory_retrieval: Retrieve relevant context from long-term memory
- clarification: Request clarification from the user

Planning guidelines:
1. Always start with memory_retrieval to gather context
2. Minimize the number of steps while ensuring completeness
3. Use tool_execution only when necessary (for real-time data, calculations, etc.)
4. If a required capability is missing, include tool_discovery
5. Always end with llm_response to synthesize results
6. Assess risks honestly - any tool execution or external action has some risk
7. Request clarification if the intent is unclear or missing critical information
8. Consider step dependencies carefully

Available tools will be provided in the context. Only use tools that are available.
Be thorough in your reasoning and honest about uncertainty."""


class PlannerAgent:
    """
    Agent responsible for planning execution.

    Responsibilities:
    - Analyze intent and determine required capabilities
    - Check available tools against requirements
    - Create multi-step execution plans using LLM
    - Request tool discovery when needed
    - Signal uncertainty and request clarification
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider
        self.available_tools: dict[str, ToolManifest] = {}
        logger.info(
            "Planner agent initialized",
            has_llm=llm_provider is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for planner")

    async def create_plan(
        self,
        intent: Intent,
        conversation_context: str | None = None,
    ) -> ExecutionPlan:
        """
        Create an execution plan for the given intent.

        Args:
            intent: The interpreted user intent
            conversation_context: Optional context from conversation

        Returns:
            ExecutionPlan with steps to execute
        """
        logger.debug("Creating execution plan", intent_type=intent.type.value)

        # Use LLM for sophisticated planning if available
        if self.llm:
            analysis = await self._llm_plan(intent, conversation_context)
            return self._analysis_to_plan(intent, analysis)

        # Fallback to simple heuristic planning
        return self._heuristic_plan(intent)

    async def _llm_plan(
        self,
        intent: Intent,
        conversation_context: str | None = None,
    ) -> ExecutionPlanAnalysis:
        """Use LLM for sophisticated execution planning."""
        assert self.llm is not None

        # Build context about available tools
        tools_context = self._build_tools_context()

        # Build the user message
        user_content = f"""Create an execution plan for this request:

Intent: {intent.text}
Type: {intent.type.value}
Requires Tool: {intent.requires_tool}
Tool Hint: {intent.tool_hint or 'None'}
Confidence: {intent.confidence}
Entities: {intent.entities}

{tools_context}"""

        if conversation_context:
            user_content = (
                f"Conversation context:\n{conversation_context}\n\n{user_content}"
            )

        messages = [LLMMessage(role=MessageRole.USER, content=user_content)]

        logger.debug("Calling LLM for execution planning")

        response = await self.llm.generate_structured(
            messages=messages,
            output_schema=ExecutionPlanAnalysis,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )

        if response.structured_output:
            logger.debug(
                "Execution plan analysis complete",
                can_fulfill=response.structured_output.can_fulfill,
                steps=len(response.structured_output.steps),
                confidence=response.structured_output.confidence,
            )
            return response.structured_output

        # If structured output failed, create a default analysis
        logger.warning("Structured output parsing failed, using defaults")
        return ExecutionPlanAnalysis(
            can_fulfill=True,
            confidence=0.5,
            steps=[
                {
                    "step_number": 0,
                    "action_type": "memory_retrieval",
                    "description": "Retrieve context from memory",
                },
                {
                    "step_number": 1,
                    "action_type": "llm_response",
                    "description": "Generate response",
                    "depends_on": [0],
                },
            ],
            complexity="simple",
            risk={"level": "low"},
            reasoning="Failed to parse structured output from LLM, using default plan",
        )

    def _analysis_to_plan(
        self, intent: Intent, analysis: ExecutionPlanAnalysis
    ) -> ExecutionPlan:
        """Convert ExecutionPlanAnalysis to ExecutionPlan model."""
        # Map action types to step types
        type_mapping = {
            "llm_response": StepType.LLM_RESPONSE,
            "tool_execution": StepType.TOOL_EXECUTION,
            "tool_discovery": StepType.TOOL_DISCOVERY,
            "memory_retrieval": StepType.MEMORY_RETRIEVAL,
            "clarification": StepType.CLARIFICATION,
        }

        steps: list[PlanStep] = []
        for action in analysis.steps:
            step_type = type_mapping.get(
                action.action_type.lower(), StepType.LLM_RESPONSE
            )
            steps.append(
                PlanStep(
                    type=step_type,
                    description=action.description,
                    tool_name=action.tool_name,
                    tool_params=action.tool_parameters,
                    depends_on=action.depends_on,
                )
            )

        return ExecutionPlan(
            intent=intent,
            steps=steps,
            requires_approval=analysis.risk.requires_approval,
            estimated_complexity=analysis.complexity,
        )

    def _heuristic_plan(self, intent: Intent) -> ExecutionPlan:
        """Fallback heuristic planning without LLM."""
        logger.debug("Using heuristic planning (no LLM)")

        steps: list[PlanStep] = []

        # Always start with memory retrieval for context
        steps.append(
            PlanStep(
                type=StepType.MEMORY_RETRIEVAL,
                description="Retrieve relevant context from memory",
            )
        )

        if intent.requires_tool:
            # Check if we have the required tool
            if intent.tool_hint and intent.tool_hint in self.available_tools:
                steps.append(
                    PlanStep(
                        type=StepType.TOOL_EXECUTION,
                        description=f"Execute {intent.tool_hint} tool",
                        tool_name=intent.tool_hint,
                        depends_on=[0],
                    )
                )
            else:
                # Need to discover a tool
                steps.append(
                    PlanStep(
                        type=StepType.TOOL_DISCOVERY,
                        description="Discover appropriate tool for the request",
                        depends_on=[0],
                    )
                )

        # Final step: Generate response
        steps.append(
            PlanStep(
                type=StepType.LLM_RESPONSE,
                description="Generate response based on context and results",
                depends_on=list(range(len(steps))),
            )
        )

        return ExecutionPlan(
            intent=intent,
            steps=steps,
            requires_approval=intent.requires_tool,
            estimated_complexity="simple" if len(steps) <= 3 else "complex",
        )

    def _build_tools_context(self) -> str:
        """Build context string about available tools."""
        if not self.available_tools:
            return "Available tools: None"

        tools_info = ["Available tools:"]
        for name, manifest in self.available_tools.items():
            tools_info.append(f"- {name}: {manifest.description}")
            if manifest.permissions:
                tools_info.append(f"  Permissions: {', '.join(manifest.permissions)}")

        return "\n".join(tools_info)

    def register_tool(self, name: str, manifest: ToolManifest) -> None:
        """Register an available tool."""
        self.available_tools[name] = manifest
        logger.info("Tool registered", tool_name=name)

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool."""
        if name in self.available_tools:
            del self.available_tools[name]
            logger.info("Tool unregistered", tool_name=name)

    def get_clarification_request(
        self, analysis: ExecutionPlanAnalysis
    ) -> ClarificationRequest | None:
        """Extract clarification request from analysis if needed."""
        if analysis.clarification.needed:
            return analysis.clarification
        return None
