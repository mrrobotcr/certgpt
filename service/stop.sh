#!/bin/bash

# Stop ExamsGPT service

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

if [ ! -f "$INSTALLED_PLIST" ]; then
    echo "❌ Service not installed."
    exit 1
fi

echo "⏸️  Stopping ExamsGPT service..."
launchctl stop com.blueorbit.examsgpt 2>/dev/null || true
launchctl unload "$INSTALLED_PLIST" 2>/dev/null || true

sleep 1

# Check if stopped
if ! launchctl list | grep -q com.blueorbit.examsgpt; then
    echo "✅ Service stopped successfully"
else
    echo "⚠️  Service may still be running"
fi
