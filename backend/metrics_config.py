"""
Prometheus Metrics Configuration for FastAPI

Exposes a /metrics endpoint with standard HTTP metrics:
- http_requests_total: Counter of requests by method, path, status
- http_request_duration_seconds: Histogram of request latency
- http_requests_in_progress: Gauge of concurrent requests

These metrics are scraped by Grafana Alloy and sent to Grafana Cloud.

Usage:
    from metrics_config import setup_metrics
    setup_metrics(app)
"""

import re

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import latency, requests


def normalize_path(path: str) -> str:
    """
    Normalize dynamic path segments to prevent cardinality explosion.

    Examples:
        /api/users/123 -> /api/users/{id}
        /api/matches/abc-def-123 -> /api/matches/{id}
        /api/teams/5/players/10 -> /api/teams/{id}/players/{id}
    """
    # UUID pattern (with or without hyphens)
    path = re.sub(r"/[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", "/{id}", path)
    # Numeric IDs
    path = re.sub(r"/\d+", "/{id}", path)
    # Short hex IDs (8+ chars)
    path = re.sub(r"/[0-9a-f]{8,}", "/{id}", path)
    return path


def setup_metrics(app):
    """
    Configure Prometheus metrics instrumentation for FastAPI.

    Adds a /metrics endpoint that exposes:
    - Request counts by method, path, status code
    - Request duration histograms
    - In-progress request gauge

    Args:
        app: FastAPI application instance
    """
    instrumentator = Instrumentator(
        should_group_status_codes=False,  # Keep exact status codes (200, 201, 500, etc.)
        should_ignore_untemplated=True,  # Ignore requests without route templates
        should_respect_env_var=False,  # Always enable (don't check ENABLE_METRICS env)
        should_instrument_requests_inprogress=True,  # Track concurrent requests
        excluded_handlers=[
            "/health",
            "/healthz",
            "/ready",
            "/livez",
            "/metrics",  # Don't instrument the metrics endpoint itself
        ],
        inprogress_name="http_requests_in_progress",
        inprogress_labels=True,
    )

    # Add default metrics with path normalization
    instrumentator.add(
        requests(
            metric_name="http_requests",
            metric_doc="Total HTTP requests",
            metric_namespace="",
            metric_subsystem="",
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    ).add(
        latency(
            metric_name="http_request_duration_seconds",
            metric_doc="HTTP request duration in seconds",
            metric_namespace="",
            metric_subsystem="",
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0),
        )
    )

    # Instrument the app and expose /metrics endpoint
    instrumentator.instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,  # Hide from OpenAPI docs
        should_gzip=False,  # Prometheus prefers uncompressed
    )

    return instrumentator
