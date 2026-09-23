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

# Say which commit this is before doing anything else (SB-860). The worker has
# no /api/version, so this line is the only way to answer "is the fix live?"
# without grepping the container filesystem.
echo "📌 build: ${GIT_SHA:-unknown}"
if [ "${GIT_SHA:-unknown}" = "unknown" ]; then
    echo "⚠️  built without --build-arg GIT_SHA; the running commit is unrecorded"
fi

if [ "$MODE" = "worker" ]; then
    echo "🔄 Starting Celery worker..."
    shift  # Remove 'worker' from arguments
    exec uv run celery -A celery_app worker "$@"
else
    echo "🚀 Starting FastAPI application..."
    exec uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2
fi
