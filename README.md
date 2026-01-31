# Slovo Voice Assistant

A desktop-native, cloud-first agentic voice assistant that can autonomously expand its capabilities, learn from failures, maintain persistent contextual memory, and explain its reasoning.

## Architecture

```
slovo-voice-assistant/
├── desktop/          # Tauri (Rust) + React UI
├── agent/            # Python agent runtime (FastAPI + LangGraph)
└── tools/            # Tool templates and sandbox definitions
```

## Components

### Desktop (`/desktop`)
- **Tauri Core (Rust)**: System tray, autostart, permissions, policy enforcement
- **UI Layer (React + TypeScript)**: Voice controls, explanations, approvals, system feedback

### Agent Runtime (`/agent`)
- **FastAPI Server**: HTTP API for IPC with desktop
- **LangGraph Agents**: Intent interpretation, planning, execution, verification, explanation
- **Memory System**: Redis (short-term), Qdrant (semantic), PostgreSQL (structured)

### Tools (`/tools`)
- Docker container templates for sandboxed tool execution
- WASM module templates for lightweight tools
- Tool manifest schemas and examples

## Prerequisites

- **Node.js** 18+ and **pnpm** 8+
- **Rust** 1.70+ with `cargo`
- **Python** 3.11+ with `uv` or `pip`
- **Docker** for sandboxed tool execution

## Quick Start

### 1. Install Dependencies

```bash
# Install JavaScript/TypeScript dependencies
pnpm install

# Install Python dependencies
cd agent
uv sync  # or: pip install -e ".[dev]"
cd ..
```

### 2. Development

```bash
# Start the agent runtime
cd agent
uv run uvicorn slovo_agent.main:app --reload --port 8741

# In another terminal, start the desktop app
cd desktop
pnpm tauri dev
```

### 3. Build for Production

```bash
# Build the desktop application
cd desktop
pnpm tauri build
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# LLM Provider
OPENAI_API_KEY=your-api-key

# Agent Runtime
AGENT_HOST=127.0.0.1
AGENT_PORT=8741

# Memory Services (local)
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://localhost:5432/slovo
```

## Security

- All tool execution happens in isolated Docker containers
- No outbound network access for tools unless explicitly approved
- Local-only long-term memory (never synced to cloud)
- AES encryption at rest for sensitive data

## License

MIT
