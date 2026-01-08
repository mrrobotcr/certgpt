#!/bin/bash

# ExamsGPT Service Installer
# Installs ExamsGPT as a macOS background service using launchd

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="$SCRIPT_DIR/com.blueorbit.examsgpt.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ExamsGPT Service Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if already installed
if [ -f "$INSTALLED_PLIST" ]; then
    echo "⚠️  ExamsGPT service is already installed."
    echo "   Run './service/uninstall.sh' first to reinstall."
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy plist to LaunchAgents
echo "📦 Installing service configuration..."
cp "$PLIST_FILE" "$INSTALLED_PLIST"

# Load the service
echo "🚀 Loading service..."
launchctl load "$INSTALLED_PLIST"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ExamsGPT service installed successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The service is now running in the background."
echo "It will automatically start when you log in."
echo ""
echo "📝 Useful commands:"
echo "   ./service/status.sh   - Check service status"
echo "   ./service/stop.sh     - Stop the service"
echo "   ./service/start.sh    - Start the service"
echo "   ./service/logs.sh     - View service logs"
echo "   ./service/uninstall.sh - Uninstall the service"
echo ""
echo "📂 Logs location: ./logs/service.*.log"
echo ""
