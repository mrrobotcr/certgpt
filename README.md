# ExamsGPT 🎓🤖

AI-powered exam assistant for Microsoft Azure certification practice exams. Capture screenshots of exam questions and get instant AI-powered answers using GPT-4o/GPT-5.2 vision capabilities.

> ⚠️ **Important**: This tool is designed for **practice exams only**, not real certification exams. Use responsibly for learning purposes.

## Features

- 📸 **Instant Screenshot Capture**: Press a configurable hotkey to capture exam questions
- 🤖 **AI-Powered Analysis**: Uses OpenAI's vision models to analyze and answer questions
- ⚡ **Background Operation**: Runs silently in the background, ready when you need it
- 🔧 **Configurable**: Easy configuration via YAML and environment variables
- 📊 **History Tracking**: Saves all questions and answers for review
- 🔌 **Extensible**: Ready for Socket.IO or webhook integration for multi-device access

## Quick Start

### 1. Prerequisites

- Python 3.10+ (tested with Python 3.13.6)
- OpenAI API key with access to vision models (GPT-4o or GPT-5.2)
- macOS (primary), Windows, or Linux

### 2. Installation

```bash
# Clone or download the repository
cd examsGPT

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env  # or use your preferred editor
```

### 3. Configuration

Edit your `.env` file:

```env
OPENAI_API_KEY=sk-your-api-key-here
APP_MODE=dev
```

Optionally customize `config.yaml` to change:
- Trigger key (default: `\`)
- OpenAI model (default: `gpt-4o`)
- Screenshot settings
- Logging preferences

### 4. Run

```bash
# Make sure virtualenv is activated
source venv/bin/activate

# Run the application
python main.py
```

You'll see:
```
Testing OpenAI connection...
✓ OpenAI connection successful

======================================================================
ExamsGPT is running!
======================================================================
Press '\' to capture and analyze exam question
Press Ctrl+C to stop
======================================================================
```

### 5. Usage

1. Open your practice exam in a browser or application
2. When you see a question you want help with, press the configured key (default: `\`)
3. The app captures your screen and sends it to OpenAI
4. The answer appears in your terminal within seconds

Example output:
```
======================================================================
[2026-01-04T19:45:23] EXAM ANSWER
======================================================================

Answer: B. Azure Virtual Network with Network Security Groups

Model: gpt-4o
Time: 2.34s
Tokens: 245
Screenshot: screenshots/exam_20260104_194523.png
======================================================================
```

## Project Structure

```
examsGPT/
├── src/
│   ├── config.py           # Configuration management
│   ├── capture.py          # Screenshot & keyboard handling
│   ├── ai_service.py       # OpenAI API integration
│   └── output_handler.py   # Output strategies (console/socket.io/webhook)
├── main.py                 # Application entry point
├── config.yaml             # Runtime configuration
├── .env                    # Environment variables (API keys)
├── requirements.txt        # Python dependencies
├── screenshots/            # Saved screenshots
└── logs/                   # Application logs & history
```

## Configuration Guide

### Trigger Key Configuration

Edit `config.yaml`:

```yaml
keyboard:
  trigger_key: '\\'  # Change to any key: '/', 'f12', etc.
```

Supported keys:
- Single characters: `\`, `/`, `=`, etc.
- Function keys: `f1`, `f2`, ..., `f12`
- Special keys: Can be extended to support combinations

### OpenAI Model Selection

Edit `config.yaml`:

```yaml
openai:
  model: 'gpt-4o'        # or 'gpt-5.2' if available
  max_tokens: 500
  temperature: 0.3       # Lower = more focused/consistent
```

### History and Logging

All screenshots (if enabled) are saved to `screenshots/`
All responses are logged to `logs/history.jsonl` in JSON Lines format:

```json
{"success": true, "answer": "B. Virtual Network", "model": "gpt-4o", "timestamp": "2026-01-04T19:45:23", "screenshot_path": "screenshots/exam_20260104_194523.png"}
```

## Web Interface (Real-Time Display)

ExamsGPT includes a beautiful web interface to view answers in real-time on any device!

### Setup Web Interface

1. **Navigate to web directory**:
```bash
cd web
npm install
npm run dev
```

2. **Configure ExamsGPT** to use webhook mode. Edit `.env`:
```env
APP_MODE=webhook
WEBHOOK_URL=http://localhost:3000/api/webhook
```

3. **Start ExamsGPT**:
```bash
# In main directory
python main.py
```

4. **Open browser**: Navigate to http://localhost:3000

Now when you press `\` to capture an exam question, the answer appears instantly on the web interface!

### Features

- ⚡ **Real-time updates** using Server-Sent Events
- 📱 **Responsive design** - works on phone, tablet, desktop
- 🎨 **Beautiful UI** - clean, distraction-free interface
- 🔄 **Auto-reconnect** - handles connection drops gracefully

See `web/README.md` for detailed documentation.

---

## Advanced Usage

### Production Mode (Future: Socket.IO)

The architecture supports sending answers to remote devices via Socket.IO or webhooks.

To enable (when implemented):

1. Edit `.env`:
```env
APP_MODE=socketio
SOCKETIO_URL=http://your-server:3000
SOCKETIO_NAMESPACE=/exams
```

2. The app will emit `exam_answer` events to your Socket.IO server
3. View answers on any device connected to your Socket.IO server

### Webhook Mode (Future)

```env
APP_MODE=webhook
WEBHOOK_URL=http://your-server:3000/webhook
```

## Troubleshooting

### "Failed to connect to OpenAI API"

- Check your API key in `.env`
- Verify you have credits in your OpenAI account
- Check internet connection

### Keyboard listener not working on macOS

macOS requires accessibility permissions for keyboard monitoring:

1. System Preferences → Security & Privacy → Privacy → Accessibility
2. Add Terminal (or your Python app) to the allowed list

### Screenshots not capturing correctly

- Ensure the app has Screen Recording permissions (macOS)
- Check `config.yaml` screenshot settings
- Review logs in `logs/` directory

## Development

### Project Architecture

The project follows a **pragmatic modular architecture**:

1. **config.py**: Centralized configuration from `.env` and `config.yaml`
2. **capture.py**: Hardware interaction (screen, keyboard)
3. **ai_service.py**: OpenAI API client with vision support
4. **output_handler.py**: Strategy pattern for extensible output
5. **main.py**: Application orchestration and lifecycle

### Adding New Output Strategies

To add Socket.IO or webhook support:

1. Edit `src/output_handler.py`
2. Implement the strategy methods in `SocketIOOutput` or `WebhookOutput`
3. Install required dependencies
4. Update `.env` with appropriate configuration

### Running as macOS Background Service

ExamsGPT can run as an invisible background service that starts automatically:

```bash
# Install service (auto-starts on login)
./service/install.sh

# Check status
./service/status.sh

# View logs
./service/logs.sh

# Stop service
./service/stop.sh

# Uninstall service
./service/uninstall.sh
```

**Features:**
- ✅ Runs silently in background (no terminal window)
- ✅ Auto-starts when you log in
- ✅ Auto-restarts if it crashes
- ✅ No Dock icon or visible windows

See `service/README.md` for complete documentation.

### Running in Background (Other Methods)

```bash
# Using nohup (simple but visible)
nohup python main.py > output.log 2>&1 &

# Using screen (requires manual start)
screen -S examsgpt
python main.py
# Press Ctrl+A then D to detach
```

## Security Notes

- **Never commit `.env` file** (already in `.gitignore`)
- Store API keys securely
- Be mindful of screenshot content (may contain sensitive information)
- Respect exam provider terms of service

## License

This project is for educational purposes only. Use responsibly.

## Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Review this README
3. Check OpenAI API status

## Roadmap

- [x] Screenshot capture with configurable hotkey
- [x] OpenAI vision API integration
- [x] Console output for development
- [x] History tracking
- [ ] Socket.IO output for multi-device access
- [ ] Webhook output support
- [ ] Hotkey combinations (Ctrl+\, Cmd+\, etc.)
- [ ] GUI mode
- [ ] Answer caching for identical questions
- [ ] Multiple monitor support
