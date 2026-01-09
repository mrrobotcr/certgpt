#!/bin/bash

# ExamsGPT Service Wrapper with Auto-Recovery
# This script provides intelligent retry logic for transient failures

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WRAPPER_LOG="$PROJECT_DIR/logs/wrapper.log"
MAX_RESTARTS=10
RESTART_WINDOW=300  # 5 minutes in seconds

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$WRAPPER_LOG"
}

# Function to track restart history
RESTART_HISTORY="$PROJECT_DIR/logs/.restart_history"
update_restart_history() {
    local current_time=$(date +%s)
    echo "$current_time" >> "$RESTART_HISTORY"

    # Remove entries older than RESTART_WINDOW
    local cutoff_time=$((current_time - RESTART_WINDOW))
    if [ -f "$RESTART_HISTORY" ]; then
        temp_file=$(mktemp)
        awk -v cutoff="$cutoff_time" '$1 > cutoff' "$RESTART_HISTORY" > "$temp_file"
        mv "$temp_file" "$RESTART_HISTORY"
    fi
}

# Function to count recent restarts
count_recent_restarts() {
    if [ ! -f "$RESTART_HISTORY" ]; then
        echo 0
        return
    fi
    wc -l < "$RESTART_HISTORY" | tr -d ' '
}

# Clear history on successful run (age it out)
age_out_history() {
    local current_time=$(date +%s)
    local cutoff_time=$((current_time - RESTART_WINDOW))
    if [ -f "$RESTART_HISTORY" ]; then
        awk -v cutoff="$cutoff_time" '$1 < cutoff {next} 1' "$RESTART_HISTORY" > "${RESTART_HISTORY}.tmp"
        mv "${RESTART_HISTORY}.tmp" "$RESTART_HISTORY"
    fi
}

# Calculate backoff delay
get_backoff_delay() {
    local restart_count=$(count_recent_restarts)
    local delay=$((restart_count * 5))  # 5 seconds per restart

    # Cap at 60 seconds
    if [ $delay -gt 60 ]; then
        delay=60
    fi

    echo $delay
}

# Main retry loop
restart_count=0
while true; do
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Starting ExamsGPT (attempt $((restart_count + 1)))"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Activate virtual environment and run main.py
    source "$PROJECT_DIR/venv/bin/activate" 2>/dev/null || {
        log "ERROR: Failed to activate virtual environment"
        exit 1
    }

    # Run Python and capture exit code
    "$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/main.py"
    exit_code=$?

    # Handle different exit codes
    case $exit_code in
        0)  # Clean exit (Ctrl+C or intentional stop)
            log "ExamsGPT exited cleanly (exit code 0)"
            age_out_history
            exit 0
            ;;
        130)  # SIGINT (Ctrl+C)
            log "ExamsGPT interrupted by user"
            age_out_history
            exit 0
            ;;
        143)  # SIGTERM (termination signal)
            log "ExamsGPT terminated by signal"
            age_out_history
            exit 0
            ;;
        *)  # Error exit
            update_restart_history
            restart_count=$(count_recent_restarts)

            log "ERROR: ExamsGPT crashed with exit code $exit_code"

            # Check if we're restarting too frequently
            if [ $restart_count -ge $MAX_RESTARTS ]; then
                log "CRITICAL: Too many restarts ($restart_count in ${RESTART_WINDOW}s). Giving up."
                log "Check logs for details: $PROJECT_DIR/logs/service.*.log"
                exit 1
            fi

            # Calculate and apply backoff delay
            delay=$(get_backoff_delay)
            log "Restarting in ${delay}s (restart #$restart_count of $MAX_RESTARTS in ${RESTART_WINDOW}s window)"

            # Wait before retrying
            sleep $delay
            ;;
    esac
done
