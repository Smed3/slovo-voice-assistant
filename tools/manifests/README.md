# Tool Manifests

This directory contains example tool manifests that can be imported into Slovo.

Tool manifests define the capabilities, permissions, and execution requirements for autonomous tools.

## Manifest Format

Manifests can be in JSON or YAML format and should include:

```yaml
name: tool-name              # Unique identifier (lowercase, hyphenated)
version: "1.0.0"             # Semantic version
description: >               # Clear description of what the tool does
  A brief description of the tool's purpose and capabilities.

capabilities:                # List of operations the tool provides
  - name: capability_name
    description: What this capability does
    endpoint: /api/endpoint  # Optional: API endpoint
    method: GET              # Optional: HTTP method
    parameters:              # JSON schema for parameters
      type: object
      properties:
        param1:
          type: string
          description: Parameter description

parameters_schema:           # Overall tool parameters schema
  type: object
  properties:
    # ... parameter definitions

# Optional: OpenAPI specification can be included
openapi_spec:
  openapi: "3.0.0"
  info:
    title: API Title
    version: "1.0.0"
  # ... full OpenAPI spec
```

## Example Manifests

- `example-calculator.yaml` - Simple calculator tool
- `example-weather.yaml` - Weather API integration (requires internet)

## Usage

Import a manifest using the Tool Discovery Agent:

```python
from slovo_agent.agents import ToolDiscoveryAgent

agent = ToolDiscoveryAgent(tool_repository)
tool_id = await agent.import_local_manifest("path/to/manifest.yaml")
```

Or via the API (future):

```bash
curl -X POST http://localhost:8741/api/tools/import \
  -H "Content-Type: application/json" \
  -d '{"manifest_path": "/path/to/manifest.yaml"}'
```
