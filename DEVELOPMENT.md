# Development Scripts

This document provides instructions for setting up and running the Slovo Voice Assistant development environment.

## Prerequisites

### Windows

1. **Install Rust**
   ```powershell
   # Install Rustup
   winget install -e --id Rustlang.Rustup
   
   # Add Rust to PATH and restart terminal, then:
   rustup default stable
   ```

2. **Install Node.js and pnpm**
   ```powershell
   winget install OpenJS.NodeJS.LTS
   npm install -g pnpm
   ```

3. **Install Python and uv**
   ```powershell
   winget install Python.Python.3.11
   pip install uv
   ```

4. **Install Docker Desktop** (for tool sandbox)
   ```powershell
   winget install Docker.DockerDesktop
   ```

5. **Install WebView2** (usually pre-installed on Windows 10/11)
   - Download from: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

## First Time Setup

```powershell
# Clone and enter the project
cd slovo-voice-assistant

# Install JavaScript dependencies
pnpm install

# Install Python dependencies
cd agent
uv sync
cd ..

# Copy environment configuration
Copy-Item .env.example .env
# Edit .env with your API keys
```

## Running in Development

### Option 1: Run Both Services Together

```powershell
# Terminal 1: Start the agent
pnpm agent:dev

# Terminal 2: Start the desktop app
pnpm dev
```

### Option 2: Run Services Separately

```powershell
# Terminal 1: Python Agent
cd agent
uv run uvicorn slovo_agent.main:app --reload --port 8741

# Terminal 2: Tauri Desktop App
cd desktop
pnpm tauri dev
```

## Building for Production

```powershell
# Build the desktop application
cd desktop
pnpm tauri build

# The installer will be in:
# desktop/src-tauri/target/release/bundle/
```

## Troubleshooting

### Tauri Build Fails
- Ensure Rust is properly installed: `rustc --version`
- Ensure WebView2 is installed
- Try: `cd desktop/src-tauri && cargo clean && cd .. && pnpm tauri build`

### Agent Won't Start
- Check Python version: `python --version` (needs 3.11+)
- Check if port 8741 is available
- Try: `cd agent && uv sync --reinstall`

### Connection Refused to Agent
- Ensure the agent is running on port 8741
- Check firewall settings for localhost connections
