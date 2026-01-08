#!/bin/bash

# ExamsGPT Service Wrapper
# This script is called by launchd to run ExamsGPT in the background

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment and run main.py
source "$PROJECT_DIR/venv/bin/activate"

# Run ExamsGPT
exec "$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/main.py"
