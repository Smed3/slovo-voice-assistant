# Slovo Agent Runtime

Python agent runtime for Slovo Voice Assistant, built with FastAPI and LangGraph.

## Features

- **FastAPI Server**: HTTP API for IPC with the desktop application
- **LangGraph Agents**: Orchestrated AI agents for intent interpretation, planning, execution
- **LLM Provider Abstraction**: Unified interface for OpenAI and Anthropic
- **Structured Reasoning**: Pydantic schemas for consistent, verifiable outputs
- **Uncertainty Signaling**: Honest confidence reporting and clarification requests
- **Self-Correction**: Automatic retry with verification feedback
- **Memory System**: Short-term (Redis), semantic (Qdrant), and structured (PostgreSQL) memory

## Agent Pipeline

The runtime implements a multi-agent pipeline:

1. **Intent Interpreter** - Parses user input, detects language, extracts entities
2. **Planner** - Creates execution plans with risk assessment
3. **Executor** - Executes plans with tool sandboxing
4. **Verifier** - Validates outputs and triggers self-correction
5. **Explainer** - Generates user-facing responses with explanations

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- OpenAI or Anthropic API key
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
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Required: At least one LLM provider API key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Override defaults
LLM_PROVIDER=auto          # auto, openai, or anthropic
LLM_MODEL=                 # Optional model override
LLM_TEMPERATURE=0.7        # if supported
LLM_MAX_TOKENS=4096        # if supported
```

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
├── agents/           # Agent implementations
│   ├── orchestrator.py   # Multi-agent coordination
│   ├── intent.py         # Intent interpretation
│   ├── planner.py        # Execution planning
│   ├── executor.py       # Plan execution
│   ├── verifier.py       # Result verification
│   └── explainer.py      # Response generation
├── llm/              # LLM provider abstraction
│   ├── base.py           # Abstract interface
│   ├── factory.py        # Provider factory
│   └── providers/        # OpenAI, Anthropic implementations
├── models/           # Pydantic models
│   ├── base.py           # Core models
│   └── reasoning.py      # Structured reasoning schemas
├── memory/           # Memory system components (Phase 3)
└── services/         # External service integrations
```

## Structured Reasoning Models

The runtime uses Pydantic schemas for structured LLM outputs:

- **IntentAnalysis** - Detailed intent interpretation with entities and languages
- **ExecutionPlanAnalysis** - Plans with risk assessment and step dependencies
- **VerificationAnalysis** - Quality scores and correction strategies
- **ResponseGeneration** - Formatted responses with explanations

## Clarification Requests

When the agent is uncertain, it can request clarification:

```python
from slovo_agent.models import ClarificationRequest, ClarificationReason

clarification = ClarificationRequest(
    needed=True,
    reason=ClarificationReason.AMBIGUOUS_INTENT,
    question="Did you mean X or Y?",
    options=["Option X", "Option Y"],
)
```
