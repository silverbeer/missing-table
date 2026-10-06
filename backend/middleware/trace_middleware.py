"""
Trace Middleware - Request Tracing for Distributed Logging

Extracts session_id and request_id from HTTP headers and binds them
to structlog context for all subsequent logging in the request.

Headers:
- X-Session-ID: Frontend session identifier (mt-sess-{uuid})
- X-Request-ID: Per-request identifier (mt-req-{uuid})

If headers are not provided, generates new identifiers.

It also writes the access log: one JSON line per request, levelled by
status (5xx ERROR, 4xx WARNING), with an unhandled exception folded into
that same line. It is pure ASGI rather than BaseHTTPMiddleware so the trace
IDs stay bound while the response is sent and while the exception
propagates - BaseHTTPMiddleware unbinds them before either (SB-1283).
"""

import logging
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

access_logger = structlog.get_logger("access")

# Probe and scrape traffic: logged at DEBUG when it succeeds, so the
# kubelet's every-5s health checks do not bury real requests.
QUIET_PATHS = frozenset({"/health", "/metrics"})

# Context variables for trace IDs - accessible throughout the request lifecycle
_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    """Generate a new request ID (8 hex chars for easy copy/paste)."""
    return f"mt-req-{uuid.uuid4().hex[:8]}"


def generate_session_id() -> str:
    """Generate a new session ID (8 hex chars, used when frontend doesn't provide one)."""
    return f"mt-sess-{uuid.uuid4().hex[:8]}"


def get_trace_context() -> tuple[str | None, str | None]:
    """
    Get current trace context (session_id, request_id).

    Returns:
        Tuple of (session_id, request_id) from current context
    """
    return _session_id.get(), _request_id.get()


def get_session_id() -> str | None:
    """Get current session ID from context."""
    return _session_id.get()


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return _request_id.get()


def access_log_level(status: int, path: str = "") -> int:
    """Log level for a finished request: 5xx ERROR, 4xx WARNING, else INFO.

    Successful probe/scrape requests (QUIET_PATHS) drop to DEBUG.
    """
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    if path in QUIET_PATHS:
        return logging.DEBUG
    return logging.INFO


class TraceMiddleware:
    """
    Binds session_id/request_id to the structlog context for the whole
    request - including response send and exception propagation - and
    writes the access log line.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        session_id = headers.get("x-session-id") or generate_session_id()
        request_id = headers.get("x-request-id") or generate_request_id()

        session_token = _session_id.set(session_id)
        request_token = _request_id.set(request_id)
        structlog.contextvars.bind_contextvars(session_id=session_id, request_id=request_id)

        status: int | None = None
        started = time.perf_counter()

        async def send_with_trace(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        exc: BaseException | None = None
        try:
            await self.app(scope, receive, send_with_trace)
        except Exception as e:
            exc = e
            # ServerErrorMiddleware (outside us) turns this into the 500.
            # Mark it so uvicorn's own "Exception in ASGI application"
            # record is dropped instead of repeating the traceback.
            e._mt_logged = True  # type: ignore[attr-defined]
            raise
        finally:
            final_status = 500 if exc is not None and status is None else status or 0
            client = scope.get("client")
            access_logger.log(
                access_log_level(final_status, scope["path"]),
                "http_request",
                method=scope["method"],
                path=scope["path"],
                status=final_status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                client_ip=client[0] if client else None,
                exc_info=exc,
            )
            _session_id.reset(session_token)
            _request_id.reset(request_token)
            structlog.contextvars.unbind_contextvars("session_id", "request_id")
