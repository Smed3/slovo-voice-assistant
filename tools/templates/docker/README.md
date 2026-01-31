# Docker Tool Template

This directory contains a template for creating Docker-based tools.

## Structure

```
docker-tool/
├── Dockerfile          # Container definition
├── requirements.txt    # Python dependencies
├── main.py             # Tool entry point
└── manifest.json       # Tool manifest
```

## Usage

1. Copy this directory to create a new tool
2. Modify `manifest.json` with tool details
3. Implement logic in `main.py`
4. Build: `docker build -t slovo/tool-<name>:latest .`
5. Test locally before deployment

## Security Notes

- Container runs as non-root user
- No network access unless specified in manifest
- Filesystem is read-only except for `/data` volume
- Resource limits enforced by sandbox
