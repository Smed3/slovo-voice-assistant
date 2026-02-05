# Phase 4: Autonomous Tooling Implementation

This document describes the Phase 4 implementation for autonomous tool management in Slovo Voice Assistant.

## Overview

Phase 4 introduces the autonomous tooling system that allows Slovo to:
- Discover and integrate new tools via OpenAPI specifications
- Execute tools in isolated Docker containers
- Enforce strict permission models
- Maintain tool state across executions
- Log all tool executions for verification

## Architecture

### Components

1. **Tool Repository** (`slovo_agent/tools/repository.py`)
   - PostgreSQL-based persistence for tool manifests, permissions, and execution logs
   - Manages tool lifecycle from discovery to revocation
   - Tracks tool state and Docker volumes

2. **Tool Discovery Agent** (`slovo_agent/agents/tool_discovery.py`)
   - Imports tool manifests from local YAML/JSON files
   - Fetches and parses OpenAPI specifications from URLs
   - Uses LLM to analyze APIs and extract capabilities
   - Queues discovery requests for manual approval

3. **Docker Sandbox Manager** (`slovo_agent/tools/sandbox.py`)
   - Executes tools in isolated Docker containers
   - Enforces network isolation (default: no internet)
   - Applies resource limits (CPU, memory)
   - Manages tool-scoped volumes for state persistence
   - Monitors resource usage and logs execution metrics

4. **Executor Agent Integration**
   - Updated to use Docker sandbox for tool execution
   - Integrates with Tool Discovery Agent for missing capabilities
   - Handles execution failures and retry logic

## Database Schema

Phase 4 adds the following tables to PostgreSQL:

- `tool_manifest` - Tool definitions and metadata
- `tool_permission` - Explicit permissions per tool
- `tool_execution_log` - Complete execution history
- `tool_state` - Persistent state storage
- `tool_volume` - Docker volume tracking
- `tool_discovery_queue` - Discovery request queue

Migration file: `agent/scripts/phase4_tools.sql`

## Tool Lifecycle

```
1. Discovery
   ↓
2. Proposal (awaiting approval)
   ↓
3. Approval
   ↓
4. Installation (Docker volume created)
   ↓
5. Execution (in sandbox)
   ↓
6. Verification (by Verifier Agent)
   ↓
7. Active Use
   ↓
8. Revocation (user-initiated)
```

## Permission Model

### Permission Types

- **Internet Access** (`internet_access`)
  - `false` (default): No network access
  - `true`: Bridge network access

- **Storage Quota** (`storage`)
  - Default: 100 MB
  - Tool-scoped Docker volume

- **CPU Limit** (`cpu_limit`)
  - Default: 50% of one CPU core
  - Enforced via Docker CPU quota

- **Memory Limit** (`memory_limit`)
  - Default: 512 MB
  - Hard limit, no swap

### Permission Enforcement

Permissions are:
1. Defined in tool manifest or granted by user
2. Stored in `tool_permission` table
3. Enforced at Docker container creation
4. Validated before each execution

## Tool Manifest Format

Tools can be defined in YAML or JSON:

```yaml
name: tool-name
version: "1.0.0"
description: Tool description

capabilities:
  - name: capability_name
    description: What it does
    parameters:
      type: object
      properties:
        param1:
          type: string

parameters_schema:
  type: object
  properties:
    # JSON schema

permissions:
  internet_access: false
  storage_quota_mb: 100
  cpu_limit_percent: 50
  memory_limit_mb: 512
```

See `tools/manifests/examples/` for complete examples.

## Usage

### Import a Local Manifest

```python
from slovo_agent.agents import ToolDiscoveryAgent
from slovo_agent.tools import ToolRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("postgresql+asyncpg://...")
session_factory = async_sessionmaker(engine)
tool_repo = ToolRepository(session_factory)
discovery_agent = ToolDiscoveryAgent(tool_repo)

# Import manifest
tool_id = await discovery_agent.import_local_manifest(
    "tools/manifests/examples/example-calculator.yaml"
)
```

### Ingest OpenAPI Specification

```python
tool_id = await discovery_agent.ingest_openapi_url(
    "https://api.example.com/openapi.json"
)
```

### Execute a Tool

```python
from slovo_agent.tools import DockerSandboxManager

sandbox = DockerSandboxManager(tool_repo)

# Get tool manifest and permissions
tool_manifest = await tool_repo.get_tool_manifest(tool_id)
permissions = await tool_repo.list_tool_permissions(tool_id)

# Execute
result = await sandbox.execute_tool(
    tool_manifest=tool_manifest,
    permissions=permissions,
    input_params={"operation": "add", "a": 5, "b": 3}
)

print(result["output"])  # {"stdout": "8", ...}
```

## Security Considerations

### Sandbox Isolation

Each tool execution runs in a fresh Docker container with:
- No network access by default
- Read-only root filesystem
- All capabilities dropped
- Resource limits enforced
- Isolated process namespace

### Permission Approval

- All tools start in `pending_approval` status
- User must explicitly approve tools before execution
- Permissions are granted per tool, not per execution
- Internet access requires explicit user consent

### Execution Logging

Every tool execution is logged with:
- Input parameters
- Execution status (success/failure)
- Output and errors
- Resource usage (CPU, memory)
- Container ID for debugging

### State Management

- Tool state is isolated per tool (no cross-tool access)
- State is stored in dedicated Docker volumes
- Volume quotas enforced
- State can be cleared on tool revocation

## Integration with Agents

### Planner Agent

The Planner determines when tool discovery is needed:

```python
# In planning phase
if intent.requires_tool and not tool_available:
    steps.append(
        PlanStep(
            type=StepType.TOOL_DISCOVERY,
            description="Discover tool for capability"
        )
    )
```

### Executor Agent

The Executor handles tool execution:

```python
# Executor configured with sandbox
executor = ExecutorAgent(
    llm_provider=llm,
    sandbox_manager=sandbox,
    tool_discovery_agent=discovery_agent
)
```

### Verifier Agent

The Verifier reviews tool outputs:
- Validates execution logs
- Checks for anomalies
- Triggers alerts for failures
- Provides feedback for self-correction

## Testing

### Unit Tests

```bash
cd agent
pytest tests/test_tools.py -v
```

### Integration Tests

```bash
# Start infrastructure
docker-compose up -d

# Run database migration
psql -U slovo -d slovo -f agent/scripts/phase4_tools.sql

# Run tests
pytest tests/test_tool_integration.py -v
```

### Manual Testing

```bash
# Import example calculator tool
python -m slovo_agent.tools.cli import \
  tools/manifests/examples/example-calculator.yaml

# Execute tool
python -m slovo_agent.tools.cli execute \
  example-calculator \
  --params '{"operation": "add", "a": 5, "b": 3}'
```

## Future Enhancements

Phase 4 MVP focuses on Docker-only execution with local manifests and OpenAPI URLs. Future enhancements:

1. **API Discovery**
   - Integration with RapidAPI, APIs.guru
   - Automatic API ranking and selection
   - Semantic search for capabilities

2. **WASM Support**
   - Lightweight tool execution
   - Faster startup times
   - Better resource efficiency

3. **Tool Marketplace**
   - Community-contributed tools
   - Ratings and reviews
   - Automatic updates

4. **Advanced Permissions**
   - Fine-grained filesystem access
   - Scoped network access (allow-list)
   - Time-based permissions

5. **Tool Composition**
   - Chain multiple tools
   - Workflows and pipelines
   - Conditional execution

## Troubleshooting

### Docker not available

```
Error: Docker daemon not available
```

**Solution**: Ensure Docker is installed and running:
```bash
sudo systemctl start docker
docker ps
```

### Permission denied

```
Error: Permission denied: /var/run/docker.sock
```

**Solution**: Add user to docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Container execution timeout

**Solution**: Increase timeout in sandbox configuration or check tool implementation for infinite loops.

### Volume quota exceeded

**Solution**: 
1. Check volume usage: `docker volume inspect slovo-tool-{id}`
2. Increase quota in permissions
3. Clear old state if needed

## References

- Specification: `.github/copilot-instructions.md`
- Database Schema: `agent/scripts/phase4_tools.sql`
- Models: `agent/slovo_agent/models/tools.py`
- Repository: `agent/slovo_agent/tools/repository.py`
- Sandbox: `agent/slovo_agent/tools/sandbox.py`
- Discovery Agent: `agent/slovo_agent/agents/tool_discovery.py`
