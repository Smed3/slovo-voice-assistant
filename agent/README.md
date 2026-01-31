# Slovo Agent Runtime

Python agent runtime for Slovo Voice Assistant, built with FastAPI and LangGraph.

## Features

- **FastAPI Server**: HTTP API for IPC with the desktop application
- **LangGraph Agents**: Orchestrated AI agents for intent interpretation, planning, execution
- **Memory System**: Short-term (Redis), semantic (Qdrant), and structured (PostgreSQL) memory

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Redis, Qdrant, and PostgreSQL (for full functionality)

### Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file:

```bash
cp ../.env.example .env
```

Edit `.env` with your API keys and service URLs.

## Development

```bash
# Start the development server
uv run uvicorn slovo_agent.main:app --reload --port 8741

# Run tests
uv run pytest

# Type checking
uv run mypy slovo_agent

# Linting
uv run ruff check slovo_agent
```

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/chat` - Send a chat message
- `POST /api/v1/chat/stream` - Stream a chat response
- `GET /api/v1/conversation/{id}` - Get conversation history

## Architecture

```
slovo_agent/
├── main.py           # FastAPI application entry point
├── config.py         # Configuration management
├── api/              # API routes
├── agents/           # LangGraph agent definitions
├── memory/           # Memory system components
└── services/         # External service integrations
```
