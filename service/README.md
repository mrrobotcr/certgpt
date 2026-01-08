# ExamsGPT Background Service

Run ExamsGPT as an invisible macOS background service using **launchd**.

## Features

✅ **Silent Operation**: Runs completely in the background, no terminal window
✅ **Auto-start**: Starts automatically when you log in
✅ **Auto-restart**: Automatically restarts if it crashes
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
examsgpt-wrapper.sh
     ↓
Activates venv
     ↓
Runs main.py
     ↓
Listens for '\' keypress
     ↓
Captures → OpenAI → Webhook
```

### Files

- **`com.blueorbit.examsgpt.plist`**: launchd configuration
- **`examsgpt-wrapper.sh`**: Wrapper script that sets up environment
- **`install.sh`**: Installation script
- **`uninstall.sh`**: Uninstallation script
- **`start.sh`**: Start the service
- **`stop.sh`**: Stop the service
- **`status.sh`**: Check service status
- **`logs.sh`**: View service logs

### Log Files

Service logs are stored in:
- **`logs/service.out.log`**: Standard output (application logs)
- **`logs/service.err.log`**: Standard error (errors and warnings)

These are separate from the regular ExamsGPT logs in `logs/examsGPT_*.log`.

## Troubleshooting

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

## Support

For issues:
1. Check logs: `./service/logs.sh`
2. Check status: `./service/status.sh`
3. Review main README.md for general ExamsGPT troubleshooting
4. Check GitHub issues

---

**Remember**: This tool is for practice exams only. Use responsibly.
