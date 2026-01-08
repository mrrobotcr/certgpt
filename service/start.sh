#!/bin/bash

# Start ExamsGPT service

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

if [ ! -f "$INSTALLED_PLIST" ]; then
    echo "❌ Service not installed. Run './service/install.sh' first."
    exit 1
fi

echo "🚀 Starting ExamsGPT service..."
launchctl load "$INSTALLED_PLIST" 2>/dev/null || launchctl start com.blueorbit.examsgpt

sleep 1

# Check if running
if launchctl list | grep -q com.blueorbit.examsgpt; then
    echo "✅ Service started successfully"
else
    echo "⚠️  Service may not have started. Check logs with './service/logs.sh'"
fi
