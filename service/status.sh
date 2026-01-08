#!/bin/bash

# Check ExamsGPT service status

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ExamsGPT Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if installed
if [ ! -f "$INSTALLED_PLIST" ]; then
    echo "Status: ❌ Not installed"
    echo ""
    echo "Install with: ./service/install.sh"
    exit 1
fi

echo "Installation: ✅ Installed"
echo ""

# Check if running
if launchctl list | grep -q com.blueorbit.examsgpt; then
    echo "Status: 🟢 Running"
    echo ""

    # Get PID if available
    PID=$(launchctl list | grep com.blueorbit.examsgpt | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "Process ID: $PID"
    fi

    # Show recent activity
    echo ""
    echo "Recent activity (last 5 lines):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -n 5 logs/service.out.log 2>/dev/null || echo "(No logs yet)"
else
    echo "Status: 🔴 Not running"
    echo ""
    echo "Start with: ./service/start.sh"
fi

echo ""
echo "Commands:"
echo "  ./service/start.sh  - Start service"
echo "  ./service/stop.sh   - Stop service"
echo "  ./service/logs.sh   - View logs"
echo ""
