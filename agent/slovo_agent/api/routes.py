"""
API routes for Slovo Agent Runtime.
"""

from fastapi import APIRouter

from slovo_agent.api.chat import router as chat_router
from slovo_agent.api.memory import router as memory_router

router = APIRouter()

# Include sub-routers
router.include_router(chat_router, tags=["chat"])
router.include_router(memory_router, tags=["memory"])
