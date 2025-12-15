"""
Trace Middleware - Request Tracing for Distributed Logging

Extracts session_id and request_id from HTTP headers and binds them
to structlog context for all subsequent logging in the request.

Headers:
- X-Session-ID: Frontend session identifier (mt-sess-{uuid})
- X-Request-ID: Per-request identifier (mt-req-{uuid})

If headers are not provided, generates new identifiers.
"""

import time
import uuid
from contextvars import ContextVar
from typing import Optional, Tuple

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variables for trace IDs - accessible throughout the request lifecycle
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

logger = structlog.get_logger(__name__)


def generate_request_id() -> str:
    """Generate a new request ID (8 hex chars for easy copy/paste)."""
    return f"mt-req-{uuid.uuid4().hex[:8]}"


def generate_session_id() -> str:
    """Generate a new session ID (8 hex chars, used when frontend doesn't provide one)."""
    return f"mt-sess-{uuid.uuid4().hex[:8]}"


def get_trace_context() -> Tuple[Optional[str], Optional[str]]:
    """
    Get current trace context (session_id, request_id).

    Returns:
        Tuple of (session_id, request_id) from current context
    """
    return _session_id.get(), _request_id.get()


def get_session_id() -> Optional[str]:
    """Get current session ID from context."""
    return _session_id.get()


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return _request_id.get()


class TraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts trace IDs from request headers and binds
    them to structlog context for distributed tracing.

    Also logs request start/end with timing information.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with trace context."""
        start_time = time.perf_counter()

        # Extract or generate trace IDs
        session_id = request.headers.get("X-Session-ID") or generate_session_id()
        request_id = request.headers.get("X-Request-ID") or generate_request_id()

        # Store in context variables
        session_token = _session_id.set(session_id)
        request_token = _request_id.set(request_id)

        # Bind to structlog context for all logging in this request
        structlog.contextvars.bind_contextvars(
            session_id=session_id,
            request_id=request_id,
        )

        # Log request start
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request completion - use warning level for server errors
            if response.status_code >= 500:
                logger.warning(
                    "request_server_error",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    hint="Check endpoint logs above for stack trace with same request_id",
                )
            else:
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )

            # Add trace IDs to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration even on error
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request failure
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise

        finally:
            # Reset context variables
            _session_id.reset(session_token)
            _request_id.reset(request_token)

            # Clear structlog context
            structlog.contextvars.unbind_contextvars("session_id", "request_id")
