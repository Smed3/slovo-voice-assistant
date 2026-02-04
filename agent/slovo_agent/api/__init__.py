"""
API routes module.
"""

from slovo_agent.api.chat import router
from slovo_agent.api.memory import router as memory_router
from slovo_agent.api.memory import set_memory_manager

__all__ = ["router", "memory_router", "set_memory_manager"]
