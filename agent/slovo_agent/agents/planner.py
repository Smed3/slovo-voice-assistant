"""
Planner Agent

Determines if existing tools can satisfy intent, plans multi-step execution,
and decides when tool discovery is required.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

from slovo_agent.agents.intent import Intent

logger = structlog.get_logger()


class StepType(str, Enum):
    """Types of execution steps."""
    
    LLM_RESPONSE = "llm_response"
    TOOL_EXECUTION = "tool_execution"
    TOOL_DISCOVERY = "tool_discovery"
    MEMORY_RETRIEVAL = "memory_retrieval"
    CLARIFICATION = "clarification"


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    
    type: StepType
    description: str
    tool_name: Optional[str] = None
    tool_params: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """Complete execution plan for handling a user request."""
    
    intent: Intent
    steps: list[PlanStep] = field(default_factory=list)
    requires_approval: bool = False
    estimated_complexity: str = "simple"


class PlannerAgent:
    """
    Agent responsible for planning execution.
    
    Responsibilities:
    - Analyze intent and determine required capabilities
    - Check available tools against requirements
    - Create multi-step execution plans
    - Request tool discovery when needed
    """
    
    def __init__(self) -> None:
        # Track available tools
        self.available_tools: dict[str, dict] = {}
        logger.info("Planner agent initialized")
    
    async def create_plan(self, intent: Intent) -> ExecutionPlan:
        """
        Create an execution plan for the given intent.
        """
        logger.debug("Creating execution plan", intent_type=intent.type.value)
        
        steps: list[PlanStep] = []
        
        # Always start with memory retrieval for context
        steps.append(PlanStep(
            type=StepType.MEMORY_RETRIEVAL,
            description="Retrieve relevant context from memory",
        ))
        
        if intent.requires_tool:
            # Check if we have the required tool
            if intent.tool_hint and intent.tool_hint in self.available_tools:
                steps.append(PlanStep(
                    type=StepType.TOOL_EXECUTION,
                    description=f"Execute {intent.tool_hint} tool",
                    tool_name=intent.tool_hint,
                    depends_on=[0],
                ))
            else:
                # Need to discover a tool
                steps.append(PlanStep(
                    type=StepType.TOOL_DISCOVERY,
                    description="Discover appropriate tool for the request",
                    depends_on=[0],
                ))
        
        # Final step: Generate response
        steps.append(PlanStep(
            type=StepType.LLM_RESPONSE,
            description="Generate response based on context and results",
            depends_on=list(range(len(steps))),
        ))
        
        return ExecutionPlan(
            intent=intent,
            steps=steps,
            requires_approval=intent.requires_tool,
            estimated_complexity="simple" if len(steps) <= 3 else "complex",
        )
    
    def register_tool(self, name: str, manifest: dict) -> None:
        """Register an available tool."""
        self.available_tools[name] = manifest
        logger.info("Tool registered", tool_name=name)
    
    def unregister_tool(self, name: str) -> None:
        """Unregister a tool."""
        if name in self.available_tools:
            del self.available_tools[name]
            logger.info("Tool unregistered", tool_name=name)
