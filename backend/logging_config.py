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

import os
import logging
import structlog
from typing import Any


def setup_logging(service_name: str = "missing-table") -> None:
    """
    Configure structured logging with JSON output for Loki/Grafana.

    Args:
        service_name: Name of the service (backend, celery-worker, etc.)
    """
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level, logging.INFO),
        handlers=[logging.StreamHandler()],
    )
    
    # Suppress verbose httpcore/httpx debug logs (they're too noisy)
    # Only show warnings and errors from httpcore/httpx
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Configure structlog with JSON renderer for Loki
    structlog.configure(
        processors=[
            # Merge context variables (session_id, request_id from middleware)
            structlog.contextvars.merge_contextvars,
            # Add log level to event dict
            structlog.stdlib.add_log_level,
            # Add logger name to event dict
            structlog.stdlib.add_logger_name,
            # Add timestamp in ISO format
            structlog.processors.TimeStamper(fmt="iso"),
            # Add stack info for exceptions
            structlog.processors.StackInfoRenderer(),
            # Format exceptions nicely
            structlog.processors.format_exc_info,
            # Decode unicode
            structlog.processors.UnicodeDecoder(),
            # Add callsite info (filename, line number)
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # Render as JSON for Loki
            structlog.processors.JSONRenderer(),
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
    logger.info(
        "logging_initialized",
        service=service_name,
        log_level=log_level,
        format="json"
    )


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
