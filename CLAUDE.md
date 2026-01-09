# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ExamsGPT is an AI-powered exam assistant for Microsoft Azure certification practice exams. It captures screenshots using keyboard/mouse triggers and analyzes them with OpenAI (GPT-4o/GPT-5.2) or Google Gemini vision APIs.

**Important**: This tool is for **practice exams only**, not real certification exams.

## Architecture

The project consists of three main components:

### 1. Python Service (Root Directory)
- **Entry point**: `main.py` - Orchestrates the application lifecycle
- **src/config.py**: Configuration management from `.env` and `config.yaml`
- **src/capture.py**: Screenshot capture (mss) and input listeners (pynput for keyboard/mouse)
- **src/ai_service.py**: OpenAI/Gemini API integration with vision support
- **src/output_handler.py**: Strategy pattern for output (console/webhook/Socket.IO)

### 2. Node.js/TypeScript Server (`server/`)
- Express + Socket.IO server that receives webhooks from Python service
- Broadcasts results to frontend via WebSocket
- **server/src/index.ts**: Main server entry point
- **server/src/routes/webhook.ts**: Webhook endpoint
- **server/src/socket/broadcaster.ts**: Socket.IO broadcasting

### 3. macOS Background Service (`service/`)
- launchd configuration for running as background daemon
- Auto-starts on login, auto-restarts on crash

## Common Development Commands

### Python Service

```bash
# Setup (first time only)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Then add your API key

# Run the application
python main.py
```

### Node.js Server

```bash
cd server
npm install
npm run dev    # Development with tsx watch
npm run build  # Compile TypeScript
npm start      # Production
```

### Configuration

- **`.env`**: API keys and app mode (dev/webhook/socketio)
- **`config.yaml`**: Runtime settings (trigger key, model, screenshot, logging)

### macOS Service Management

```bash
./service/install.sh    # Install and start background service
./service/uninstall.sh  # Remove service completely
./service/status.sh     # Check if running
./service/logs.sh       # View logs (-f for follow)
./service/stop.sh       # Stop service
./service/start.sh      # Start service
```

## Key Implementation Details

### AI Provider Architecture

The codebase supports two AI providers via `ai.provider` in `config.yaml`:

1. **OpenAI** (`provider: 'openai'`):
   - GPT-5.x models use the new Responses API (`client.responses.create()`)
   - GPT-4o and earlier use the legacy Completions API (`client.chat.completions.create()`)
   - Supports reasoning, web_search tools, and store options in config.yaml

2. **Gemini** (`provider: 'gemini'`):
   - Uses Google GenAI SDK with lazy initialization
   - Enabled with thinking config and Google Search
   - Requires `GEMINI_API_KEY` in `.env`

API detection happens in `ai_service.py:_uses_responses_api()` based on model name prefix.

### Output Strategy Pattern

The `OutputHandler` uses a strategy pattern based on `APP_MODE`:

- **dev**: Console output (for development)
- **webhook**: POST to configured `WEBHOOK_URL` with retry logic
- **socketio**: Socket.IO emission (not yet implemented)

### Input Triggers

Two capture triggers are supported:
- **Keyboard**: Configurable via `keyboard.trigger_key` in config.yaml (default: `=`)
- **Mouse**: Middle button (scroll wheel click) via `mouse.enable_middle_button`

Both are handled by `CaptureManager` in `src/capture.py`.

### Prompt Engineering

The system prompt is in `config.py:get_prompt_template()`. It's designed for Azure certification exams and instructs the AI to:
- Return structured JSON for different question types (single, multiple, dragdrop, etc.)
- Use web_search when confidence < 90% or for specific Azure topics
- Include confidence scores and verification sources

## Environment Variables Required

```env
# Required for OpenAI provider
OPENAI_API_KEY=sk-...

# Required for Gemini provider
GEMINI_API_KEY=...

# Application mode (dev/webhook/socketio)
APP_MODE=dev

# For webhook mode
WEBHOOK_URL=http://localhost:3000/api/webhook

# For Socket.IO mode (future)
SOCKETIO_URL=http://localhost:3000
SOCKETIO_NAMESPACE=/exams
```

## Project-Specific Patterns

### Configuration Loading
Configuration is initialized once via `init_config()` in `main.py` and accessed globally via `get_config()`. All modules import the singleton instance.

### Error Handling
- AIService returns dict with `success: True/False` and `error` field on failure
- WebhookOutput has exponential backoff retry (3 attempts, starting at 0.5s)
- All errors are logged to both console and file (if enabled)

### Logging Structure
- Logs go to `logs/examsGPT_YYYYMMDD.log`
- History (JSONL format) goes to `logs/history.jsonl`
- Service logs: `logs/service.out.log` and `logs/service.err.log`

### macOS Permissions
The app requires these macOS permissions (System Preferences → Privacy & Security):
- **Input Monitoring**: For keyboard/mouse listeners
- **Screen Recording**: For screenshot capture

## File Locations Reference

- Virtual env Python: `venv/bin/python` (hardcoded in `service/com.blueorbit.examsgpt.plist`)
- Screenshots: `screenshots/`
- Logs: `logs/`
- History: `logs/history.jsonl` (JSONL format)

## Testing Connection

The app runs `ai_service.test_connection()` on startup to verify API credentials before starting listeners.
