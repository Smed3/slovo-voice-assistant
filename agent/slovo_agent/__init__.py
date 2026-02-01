"""
Slovo Agent Runtime

Python agent runtime for the Slovo Voice Assistant.
"""

__version__ = "0.1.0"

from slovo_agent.agents import (
    AgentOrchestrator,
    ExecutorAgent,
    ExplainerAgent,
    IntentInterpreterAgent,
    PlannerAgent,
    VerifierAgent,
)
from slovo_agent.config import settings

__all__ = [
    # Configuration
    "settings",
    # Agents
    "AgentOrchestrator",
    "ExecutorAgent",
    "ExplainerAgent",
    "IntentInterpreterAgent",
    "PlannerAgent",
    "VerifierAgent",
]
