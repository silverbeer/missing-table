"""
Type-safe API client for Missing Table backend.

This package provides a comprehensive, type-safe client for interacting
with the Missing Table API, complete with authentication handling,
retry logic, and full Pydantic model validation.
"""

from .client import MissingTableClient
from .exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "MissingTableClient",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]
