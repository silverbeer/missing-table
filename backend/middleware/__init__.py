"""
Backend Middleware

Provides request processing middleware for the FastAPI application.
"""

from .trace_middleware import TraceMiddleware, get_trace_context

__all__ = ["TraceMiddleware", "get_trace_context"]
