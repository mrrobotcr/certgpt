# ExamsGPT Background Service

Run ExamsGPT as an invisible macOS background service using **launchd**.

## Features

✅ **Silent Operation**: Runs completely in the background, no terminal window
✅ **Auto-start**: Starts automatically when you log in
✅ **Auto-restart**: Automatically restarts if it crashes
✅ **Smart Recovery**: Detects transient errors and retries with exponential backoff
✅ **Network Resilience**: Automatically recovers from network failures
✅ **Crash Prevention**: Max 10 restarts per 5-minute window prevents infinite crash loops
✅ **No Dock Icon**: Invisible to other applications
✅ **Low Priority**: Runs with nice priority to not affect system performance
✅ **Persistent Logs**: All output saved to log files

## Quick Start

### 1. Install Service

```bash
./service/install.sh
```

This will:
- Copy the service configuration to `~/Library/LaunchAgents/`
- Start the service immediately
- Configure it to auto-start on login

### 2. Check Status

```bash
./service/status.sh
```

Shows whether the service is running and recent activity.

### 3. View Logs

```bash
./service/logs.sh
```

View recent logs. Use `./service/logs.sh -f` to follow logs in real-time.

## Management Commands

All commands should be run from the project root:

### Install
```bash
./service/install.sh
```
Installs and starts the background service.

### Uninstall
```bash
./service/uninstall.sh
```
Stops and completely removes the service.

### Start
```bash
./service/start.sh
```
Starts the service (if stopped).

### Stop
```bash
./service/stop.sh
```
Stops the service (but keeps it installed).

### Status
```bash
./service/status.sh
```
Shows service status and recent activity.

### Logs
```bash
./service/logs.sh       # View recent logs
./service/logs.sh -f    # Follow logs in real-time
```

## How It Works

### Architecture

```
macOS Login
     ↓
launchd starts service
     ↓
examsgpt-wrapper.sh (generated dynamically during install)
     ↓
Activates venv
     ↓
Runs main.py
     ↓
Listens for '\' keypress
     ↓
Captures → OpenAI → Webhook
```

### Dynamic Configuration

**Important**: The service uses **dynamic path generation** for portability:

- **`com.blueorbit.examsgpt.plist.template`**: Template with placeholders
- **`install.sh`**: Generates plist dynamically based on project location
- **Result**: Service works on any machine without manual path edits

The plist is generated with your actual project paths during installation, so you can:
- Move the project to any directory
- Clone to different machines
- Share without path conflicts

### Files

- **`com.blueorbit.examsgpt.plist.template`**: Template with `__PROJECT_DIR__` placeholders
- **`examsgpt-wrapper.sh`**: Wrapper script with intelligent retry logic
- **`install.sh`**: Installation script (generates plist dynamically)
- **`uninstall.sh`**: Uninstallation script
- **`start.sh`**: Start the service
- **`stop.sh`**: Stop the service
- **`status.sh`**: Check service status
- **`logs.sh`**: View service logs (includes wrapper recovery logs)

### Log Files

Service logs are stored in:
- **`logs/service.out.log`**: Standard output (application logs)
- **`logs/service.err.log`**: Standard error (errors and warnings)
- **`logs/wrapper.log`**: Wrapper script logs (restart attempts, recovery)

These are separate from the regular ExamsGPT logs in `logs/examsGPT_*.log`.

## Auto-Recovery System

The service implements a **3-layer defense** for maximum reliability:

### Layer 1: Application-Level Retries (main.py)

**What**: Python code automatically retries transient failures
**When**: Network timeouts, API rate limits, connection errors
**How**: Exponential backoff (2s → 4s → 8s) for up to 3 attempts

**Example**:
```
Connection timeout to OpenAI API
  ↓
Retry 1 in 2s...
  ↓
Retry 2 in 4s...
  ↓
Retry 3 in 8s...
  ↓
If still failing: Exit (triggers Layer 2)
```

### Layer 2: Wrapper Script Recovery (examsgpt-wrapper.sh)

**What**: Bash wrapper monitors process and restarts on crashes
**When**: Application exits with error code, unhandled exceptions
**How**: Smart restart counting with backoff delay

**Features**:
- Tracks restarts in 5-minute rolling window
- Exponential backoff: 5s × restart_count (max 60s)
- Gives up after 10 crashes in 5 minutes (prevents crash loops)
- Distinguishes clean exits (Ctrl+C) from crashes

**Example**:
```
main.py crashes with exit code 1
  ↓
Wrapper logs: "Restarting in 5s (restart #1 of 10)"
  ↓
If crashes again: "Restarting in 10s (restart #2 of 10)"
  ↓
If 10+ crashes in 5 min: "CRITICAL: Too many restarts. Giving up."
```

### Layer 3: launchd KeepAlive (com.blueorbit.examsgpt.plist)

**What**: macOS launchd daemon manager
**When**: Wrapper script itself crashes or exits
**How**: Restarts the wrapper immediately

**Features**:
- `KeepAlive` with `SuccessfulExit: false` - always restart on crashes
- `NetworkState: true` - restart when network comes back
- `ThrottleInterval: 5` - minimum 5 seconds between restarts
- `OnFailure: restart` - explicit restart on any failure

**Example**:
```
Wrapper crashes (e.g., venv activation failure)
  ↓
launchd: "Service died, restarting in 5s"
  ↓
Wrapper restarts and tries to run main.py again
```

### Recovery Flow Examples

**Scenario 1: Transient Network Failure**
```
1. main.py tries to connect to OpenAI → timeout
2. Layer 1: Retry with backoff (2s, 4s, 8s)
3. If successful: Continue running
4. If all retries fail: Exit with error code
5. Layer 2: Wrapper catches exit, restarts in 5s
6. Network is back: Success!
```

**Scenario 2: API Rate Limiting**
```
1. main.py gets HTTP 429 from OpenAI
2. Layer 1: Recognizes "rate limit" in error message
3. Retry with longer backoff
4. API limit resets: Success!
```

**Scenario 3: Code Bug (Crash on Startup)**
```
1. main.py crashes on startup
2. Layer 2: Wrapper catches exit, restarts in 5s
3. Crashes again: restart in 10s
4. ...continues for up to 10 restarts
5. Layer 2: "Too many restarts, giving up"
6. Wrapper exits with code 1
7. Layer 3: launchd restarts wrapper after 5s
8. Cycle continues until bug is fixed or manually stopped
```

### Monitoring Recovery

Check wrapper logs to see recovery in action:

```bash
# View wrapper recovery logs
cat logs/wrapper.log

# Follow in real-time
tail -f logs/wrapper.log
```

**Example output**:
```
[2025-01-09 10:23:45] Starting ExamsGPT (attempt 1)
[2025-01-09 10:24:12] ERROR: ExamsGPT crashed with exit code 1
[2025-01-09 10:24:12] Restarting in 5s (restart #1 of 10 in 300s window)
[2025-01-09 10:24:17] Starting ExamsGPT (attempt 2)
[2025-01-09 10:24:18] ✓ ExamsGPT running successfully
```

## Troubleshooting

### Service won't start after moving project

If you moved the project to a different directory:

```bash
# The plist still has old paths - reinstall to regenerate
./service/uninstall.sh
./service/install.sh
```

The installer automatically detects the new project location and regenerates the plist with correct paths.

### Service won't start

1. Check logs:
   ```bash
   ./service/logs.sh
   ```

2. Verify `.env` file exists and has valid `OPENAI_API_KEY`

3. Check permissions:
   ```bash
   ls -la service/examsgpt-wrapper.sh
   # Should show -rwxr-xr-x (executable)
   ```

### Service starts but doesn't respond to keypress

1. Check macOS permissions:
   - System Preferences → Privacy & Security → Input Monitoring
   - Add Python or the service to allowed apps

2. Check if service is actually running:
   ```bash
   ./service/status.sh
   ```

3. View real-time logs:
   ```bash
   ./service/logs.sh -f
   ```
   Then press `\` and watch for activity

### Can't unload service

If `./service/uninstall.sh` fails:

```bash
# Force unload
launchctl remove com.blueorbit.examsgpt

# Manually delete plist
rm ~/Library/LaunchAgents/com.blueorbit.examsgpt.plist
```

### Service uses too much CPU

The service runs with `Nice` priority 5 (lower than normal processes). If you need to adjust:

Edit `com.blueorbit.examsgpt.plist` and change:
```xml
<key>Nice</key>
<integer>10</integer>  <!-- Higher = lower priority -->
```

Then reinstall:
```bash
./service/uninstall.sh
./service/install.sh
```

## Advanced Configuration

### Portable Installation

The service is designed to be **fully portable**:

1. **Clone to any location**: Works in `/Users/username/projects/`, `/opt/`, `~/Desktop/`, etc.
2. **Move anytime**: Just reinstall after moving (see troubleshooting above)
3. **Share with team**: No path conflicts, each install generates correct paths
4. **Multiple machines**: Same codebase works everywhere

The secret: `install.sh` uses `sed` to replace `__PROJECT_DIR__` in the template with the actual path during installation.

### Change Webhook URL

The service reads from `.env` automatically. To change webhook URL:

1. Edit `.env`:
   ```env
   APP_MODE=webhook
   WEBHOOK_URL=http://your-server:3000/api/webhook
   ```

2. Restart service:
   ```bash
   ./service/stop.sh
   ./service/start.sh
   ```

### Disable Auto-start

To prevent service from starting on login:

1. Edit `com.blueorbit.examsgpt.plist`
2. Change:
   ```xml
   <key>RunAtLoad</key>
   <false/>  <!-- Was true -->
   ```
3. Reinstall service

### Run on System Boot (not just login)

To run as a system daemon (requires sudo):

1. Copy plist to `/Library/LaunchDaemons/` instead of `~/Library/LaunchAgents/`
2. Change ownership:
   ```bash
   sudo chown root:wheel /Library/LaunchDaemons/com.blueorbit.examsgpt.plist
   ```
3. Load with sudo:
   ```bash
   sudo launchctl load /Library/LaunchDaemons/com.blueorbit.examsgpt.plist
   ```

**Note**: System daemons run as root. This is NOT recommended for ExamsGPT.

## Security Considerations

### Permissions

The service needs:
- **Input Monitoring**: To detect keyboard presses
- **Screen Recording**: To capture screenshots
- **Network**: To communicate with OpenAI API and webhook

Grant these in System Preferences → Privacy & Security.

### Visibility

While the service runs in the background:
- ✅ No terminal window
- ✅ No Dock icon
- ✅ Marked as `ProcessType: Background`
- ⚠️ Visible in Activity Monitor as "Python"
- ⚠️ Visible in `launchctl list | grep examsgpt`

It's designed for silent operation, not stealth. Appropriate for legitimate study purposes only.

### Network Traffic

All network requests go to:
- `api.openai.com` (OpenAI API)
- `localhost:3000` (or configured webhook URL)

## Uninstalling Completely

To remove all traces:

```bash
# 1. Uninstall service
./service/uninstall.sh

# 2. Remove logs (optional)
rm -rf logs/service.*.log

# 3. Remove entire project (if desired)
cd ..
rm -rf examsGPT/
```

## FAQ

**Q: Does it start automatically?**
A: Yes, when you log in to macOS.

**Q: Can I run it manually instead?**
A: Yes, just run `python main.py` normally. The service is optional.

**Q: How do I know it's working?**
A: Run `./service/status.sh` or check `./service/logs.sh`

**Q: Can I see the process running?**
A: Yes, in Activity Monitor search for "Python" or run `ps aux | grep examsgpt`

**Q: Does it survive reboots?**
A: Yes, it starts automatically when you log in after reboot.

**Q: How much resources does it use?**
A: Minimal when idle. Spikes briefly when processing screenshots (~2-5 seconds).

**Q: Can I move the project to another folder?**
A: Yes! Just reinstall: `./service/uninstall.sh && ./service/install.sh`. The installer regenerates paths automatically.

**Q: Will this work on another Mac?**
A: Absolutely. The plist is generated dynamically during install, so it works on any machine without modification.

**Q: Do I need to edit paths in the plist?**
A: No! The `install.sh` script handles all path generation automatically. Just run it.

## Support

For issues:
1. Check logs: `./service/logs.sh`
2. Check status: `./service/status.sh`
3. Review main README.md for general ExamsGPT troubleshooting
4. Check GitHub issues

---

**Remember**: This tool is for practice exams only. Use responsibly.
