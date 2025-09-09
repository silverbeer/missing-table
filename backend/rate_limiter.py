"""
Rate limiting middleware for the sports league backend.
"""

import logging
import os

import redis
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Redis configuration for distributed rate limiting
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
USE_REDIS = os.getenv("USE_REDIS_RATE_LIMIT", "false").lower() == "true"

# Create Redis client if enabled
redis_client = None
if USE_REDIS:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected for rate limiting")
    except Exception as e:
        logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
        redis_client = None


# Custom key function that includes user ID for authenticated requests
def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on IP and user ID if authenticated."""
    # Get IP address
    ip = get_remote_address(request)

    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        return f"{ip}:{user_id}"
    return ip


# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["200 per hour", "50 per minute"],  # Global limits
    storage_uri=REDIS_URL if redis_client else None,
    headers_enabled=True,  # Include rate limit headers in responses
)

# Rate limit configurations for different endpoint categories
RATE_LIMITS = {
    # Authentication endpoints - stricter limits
    "auth": {"login": "5 per minute", "signup": "3 per hour", "password_reset": "3 per hour"},
    # Public read endpoints - generous limits
    "public": {"default": "100 per minute", "standings": "30 per minute", "games": "30 per minute"},
    # Authenticated write endpoints - moderate limits
    "authenticated": {
        "default": "30 per minute",
        "create_game": "10 per minute",
        "update_game": "20 per minute",
    },
    # Admin endpoints - relaxed limits
    "admin": {"default": "100 per minute"},
}


def get_endpoint_limit(path: str, method: str, user_role: str = None) -> str:
    """Determine rate limit based on endpoint and user role."""

    # Auth endpoints
    if path.startswith("/api/auth/"):
        if "login" in path:
            return RATE_LIMITS["auth"]["login"]
        elif "signup" in path:
            return RATE_LIMITS["auth"]["signup"]
        elif "password" in path:
            return RATE_LIMITS["auth"]["password_reset"]

    # Admin users get higher limits
    if user_role == "admin":
        return RATE_LIMITS["admin"]["default"]

    # Write operations (POST, PUT, DELETE)
    if method in ["POST", "PUT", "DELETE"]:
        if "games" in path:
            if method == "POST":
                return RATE_LIMITS["authenticated"]["create_game"]
            else:
                return RATE_LIMITS["authenticated"]["update_game"]
        return RATE_LIMITS["authenticated"]["default"]

    # Public read operations
    if "standings" in path:
        return RATE_LIMITS["public"]["standings"]
    elif "games" in path:
        return RATE_LIMITS["public"]["games"]

    return RATE_LIMITS["public"]["default"]


def create_rate_limit_middleware(app):
    """Create and configure rate limiting middleware."""

    # Add error handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add middleware
    app.add_middleware(SlowAPIMiddleware)

    return limiter


# Decorator for custom rate limits on specific endpoints
def rate_limit(limit: str):
    """Decorator to apply custom rate limit to an endpoint."""
    return limiter.limit(limit)
