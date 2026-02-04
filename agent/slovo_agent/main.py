"""
FastAPI application entry point for Slovo Agent Runtime.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slovo_agent.api.routes import router as api_router
from slovo_agent.api.memory import set_memory_manager
from slovo_agent.api.chat import set_chat_memory_manager
from slovo_agent.config import settings
from slovo_agent.memory import create_memory_manager, MemoryManager
from slovo_agent.models import HealthResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if not settings.debug else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Track uptime and memory manager
_start_time: float = 0
_memory_manager: MemoryManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global _start_time, _memory_manager
    _start_time = asyncio.get_event_loop().time()
    
    logger.info("Starting Slovo Agent Runtime", version=settings.version)
    
    # Initialize memory services
    try:
        _memory_manager = await create_memory_manager(
            redis_url=settings.redis_url,
            qdrant_url=settings.qdrant_url,
            database_url=settings.database_url,
        )
        set_memory_manager(_memory_manager)
        set_chat_memory_manager(_memory_manager)
        
        # Check memory health
        health = await _memory_manager.health_check()
        logger.info(
            "Memory services initialized",
            redis=health.get("redis", False),
            qdrant=health.get("qdrant", False),
            postgres=health.get("postgres", False),
        )
    except Exception as e:
        logger.warning(
            "Memory services initialization failed - running in degraded mode",
            error=str(e),
        )
    
    yield
    
    # Cleanup
    logger.info("Shutting down Slovo Agent Runtime")


# Create FastAPI application
app = FastAPI(
    title="Slovo Agent Runtime",
    description="Python agent runtime for the Slovo Voice Assistant",
    version=settings.version,
    lifespan=lifespan,
)

# Configure CORS for local Tauri app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",  # Vite dev server
        "tauri://localhost",      # Tauri app
        "https://tauri.localhost", # Tauri app (HTTPS)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    global _start_time
    current_time = asyncio.get_event_loop().time()
    uptime = current_time - _start_time if _start_time > 0 else 0
    
    return HealthResponse(
        status="healthy",
        version=settings.version,
        uptime=uptime,
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


def run() -> None:
    """Run the server."""
    uvicorn.run(
        "slovo_agent.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run()
