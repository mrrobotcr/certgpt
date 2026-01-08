#!/bin/bash

# ExamsGPT Service Uninstaller
# Removes ExamsGPT background service

set -e

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ExamsGPT Service Uninstaller"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if installed
if [ ! -f "$INSTALLED_PLIST" ]; then
    echo "❌ ExamsGPT service is not installed."
    exit 1
fi

# Unload the service
echo "⏸️  Stopping service..."
launchctl unload "$INSTALLED_PLIST" 2>/dev/null || true

# Remove plist
echo "🗑️  Removing service configuration..."
rm -f "$INSTALLED_PLIST"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ExamsGPT service uninstalled successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The service has been stopped and removed."
echo "Log files are preserved in ./logs/ directory."
echo ""
