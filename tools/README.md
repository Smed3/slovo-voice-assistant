# Tools Directory

This directory contains tool templates and sandbox definitions for the Slovo Voice Assistant.

## Structure

```
tools/
├── templates/          # Tool templates for different types
│   ├── docker/         # Docker-based tool templates
│   └── wasm/           # WASM module templates
├── manifests/          # Tool manifest schemas
├── sandbox/            # Sandbox configuration and policies
└── examples/           # Example tool implementations
```

## Tool Lifecycle

1. **Discovery** - Tool Discovery Agent finds relevant APIs
2. **Proposal** - Generate manifest with capabilities and permissions
3. **Approval** - User approves tool installation
4. **Installation** - Package into Docker/WASM container
5. **Execution** - Run in isolated sandbox
6. **Verification** - Validate outputs

## Security Model

All tools run in isolated environments with:

- No filesystem access (except tool-scoped volume)
- No outbound network access (unless explicitly approved)
- CPU and memory limits
- Time-limited execution

## Creating a New Tool

1. Copy a template from `templates/`
2. Implement the tool logic
3. Create a manifest in `manifests/`
4. Test locally with the sandbox runner
5. Submit for review

See the [examples](examples/) directory for reference implementations.
