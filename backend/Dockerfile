# Production Dockerfile for Sports League Backend
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
# `git` is required because uv syncs telegram-notify and discord-notify
# from git+https sources defined in pyproject.toml's [tool.uv.sources].
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application directory
WORKDIR /app

# Create non-root user, and give it /app up front.
#
# SB-860: this used to end with `RUN chown -R appuser:appuser /app` after the
# venv existed. A recursive chown rewrites every file, so Docker stored a
# SECOND full copy of the 970MB virtualenv in that layer — 974MB of pure
# duplication. Owning the files as they are written costs nothing instead.
RUN useradd --create-home --shell /bin/bash appuser && \
    chown appuser:appuser /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Everything below runs as appuser, so the venv and application code are
# written with the right ownership and never need chowning afterwards.
USER appuser

# Copy project configuration and install dependencies
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv sync --frozen && \
    uv pip install slowapi redis

# Copy application code
COPY --chown=appuser:appuser . .

# Record which commit this image was built from (SB-860).
#
# Declared after the dependency layers so supplying it does not invalidate
# them. Without this, confirming a merged fix was actually running meant
# grepping for function names inside the container filesystem — the worker
# is built locally and has no /api/version to ask.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

# Permissions and runtime directories. Cheap layer: touches two paths, not
# the whole tree.
RUN chmod +x /app/docker-entrypoint.sh && \
    mkdir -p /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use entrypoint script to support both API and worker modes
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default to API mode
CMD []