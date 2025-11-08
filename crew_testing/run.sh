#!/bin/bash
# Wrapper script to run CrewAI testing from any directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
PYTHONPATH=. backend/.venv/bin/python3 crew_testing/main.py "$@"
