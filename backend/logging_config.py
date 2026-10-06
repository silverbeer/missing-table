"""
Structured Logging Configuration

Provides consistent structured JSON logging for backend and Celery workers,
optimized for Grafana Loki integration.

Usage:
    from logging_config import setup_logging

    setup_logging(service_name="backend")
    logger = structlog.get_logger()
    logger.info("event_occurred", user_id=123, action="login")
"""

import logging
import os
from typing import Any

import structlog


class DropAlreadyLoggedASGIException(logging.Filter):
    """Drop uvicorn's "Exception in ASGI application" record when
    TraceMiddleware already logged that exception on the request's line."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.error" or not record.exc_info:
            return True
        return not getattr(record.exc_info[1], "_mt_logged", False)


def setup_logging(service_name: str = "missing-table") -> None:
    """
    Configure structured logging with JSON output for Loki/Grafana.

    Args:
        service_name: Name of the service (backend, celery-worker, etc.)
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Processors shared by structlog loggers and foreign (stdlib) records,
    # so uvicorn, supabase etc. come out as the same JSON with the same
    # request context instead of raw text (SB-1283).
    shared_processors: list[Any] = [
        # Merge context variables (session_id, request_id from middleware)
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        # Add callsite info (filename, line number)
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                # Traceback becomes a string field: one line per event
                structlog.processors.format_exc_info,
                # Render as JSON for Loki
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    handler.addFilter(DropAlreadyLoggedASGIException())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # uvicorn installs its own plain-text handlers before importing the app.
    # Route its loggers through the root handler instead; its access log is
    # replaced by TraceMiddleware's levelled, request-scoped one.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    # Suppress verbose httpcore/httpx debug logs (they're too noisy)
    # Only show warnings and errors from httpcore/httpx
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Use logging module as backend
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind service name globally
    structlog.contextvars.bind_contextvars(service=service_name)

    # Log initialization
    logger = structlog.get_logger()
    logger.info("logging_initialized", service=service_name, log_level=log_level, format="json")


def get_logger(name: str | None = None) -> Any:
    """
    Get a structlog logger instance.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured structlog logger

    Example:
        logger = get_logger(__name__)
        logger.info("user_login", user_id=123, method="oauth")
    """
    return structlog.get_logger(name)
