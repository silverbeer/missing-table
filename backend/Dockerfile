# Production Dockerfile for Sports League Backend
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application directory
WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project configuration and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen && \
    uv pip install slowapi redis

# Copy application code
COPY . .

# Set ownership and permissions
RUN chown -R appuser:appuser /app && \
    chmod +x /app && \
    chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Create logs directory
RUN mkdir -p /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use entrypoint script to support both API and worker modes
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default to API mode
CMD []