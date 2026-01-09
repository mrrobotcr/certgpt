#!/bin/bash

# ExamsGPT Service Installer
# Installs ExamsGPT as a macOS background service using launchd
# Generates plist dynamically based on project location

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_TEMPLATE="$SCRIPT_DIR/com.blueorbit.examsgpt.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.blueorbit.examsgpt.plist"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ExamsGPT Service Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if template exists
if [ ! -f "$PLIST_TEMPLATE" ]; then
    echo "❌ ERROR: Template file not found: $PLIST_TEMPLATE"
    exit 1
fi

# Check if already installed
if [ -f "$INSTALLED_PLIST" ]; then
    echo "⚠️  ExamsGPT service is already installed."
    echo "   Run './service/uninstall.sh' first to reinstall."
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Generate plist from template with dynamic paths
echo "📦 Generating service configuration..."
echo "   • Project path: $PROJECT_DIR"

# Escape special characters in path for sed
ESCAPED_PROJECT_DIR=$(echo "$PROJECT_DIR" | sed 's/[&/\]/\\&/g')

# Replace __PROJECT_DIR__ placeholder with actual path
sed "s|__PROJECT_DIR__|$ESCAPED_PROJECT_DIR|g" "$PLIST_TEMPLATE" > "$INSTALLED_PLIST"

echo "   ✓ Plist generated dynamically"

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
echo "📁 Configuration:"
echo "   • Project: $PROJECT_DIR"
echo "   • Plist:   $INSTALLED_PLIST"
echo ""
echo "🛡️  Auto-Recovery Features Enabled:"
echo "   • Automatic restart on crashes"
echo "   • Transient error retry with exponential backoff"
echo "   • Network failure detection and recovery"
echo "   • Max 10 restarts per 5-minute window (prevents crash loops)"
echo ""
echo "📝 Useful commands:"
echo "   ./service/status.sh   - Check service status"
echo "   ./service/stop.sh     - Stop the service"
echo "   ./service/start.sh    - Start the service"
echo "   ./service/logs.sh     - View service logs"
echo "   ./service/uninstall.sh - Uninstall the service"
echo ""
echo "📂 Logs location: ./logs/service.*.log"
echo "📂 Wrapper log:  ./logs/wrapper.log"
echo ""
