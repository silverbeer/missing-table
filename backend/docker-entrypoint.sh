#!/bin/bash
# Docker entrypoint script for backend container
#
# Supports two modes:
# 1. API mode (default): Runs FastAPI with uvicorn
# 2. Worker mode: Runs Celery worker
#
# Usage:
#   docker run <image>                    # Runs API mode
#   docker run <image> worker             # Runs Celery worker
#   docker run <image> worker --loglevel=debug  # Celery worker with debug logging

set -e

MODE="${1:-api}"

if [ "$MODE" = "worker" ]; then
    echo "🔄 Starting Celery worker..."
    shift  # Remove 'worker' from arguments
    exec uv run celery -A celery_app worker "$@"
else
    echo "🚀 Starting FastAPI application..."
    exec uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2
fi
