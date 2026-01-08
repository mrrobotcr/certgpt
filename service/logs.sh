#!/bin/bash

# View ExamsGPT service logs

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STDOUT_LOG="$PROJECT_DIR/logs/service.out.log"
STDERR_LOG="$PROJECT_DIR/logs/service.err.log"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ExamsGPT Service Logs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check which logs exist
if [ ! -f "$STDOUT_LOG" ] && [ ! -f "$STDERR_LOG" ]; then
    echo "❌ No logs found yet. Service may not have started."
    exit 1
fi

# Check for -f flag to follow logs
if [ "$1" = "-f" ]; then
    echo "Following logs (Ctrl+C to stop)..."
    echo ""
    tail -f "$STDOUT_LOG" "$STDERR_LOG" 2>/dev/null
else
    # Show last 30 lines
    echo "Standard Output (last 30 lines):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -f "$STDOUT_LOG" ]; then
        tail -n 30 "$STDOUT_LOG"
    else
        echo "(No stdout logs)"
    fi

    echo ""
    echo "Standard Error (last 30 lines):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -f "$STDERR_LOG" ]; then
        tail -n 30 "$STDERR_LOG"
    else
        echo "(No stderr logs)"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Use './service/logs.sh -f' to follow logs in real-time"
    echo ""
fi
