"""Custom exceptions for API client."""


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Raised when authentication fails (401)."""

    pass


class AuthorizationError(APIError):
    """Raised when authorization fails (403)."""

    pass


class NotFoundError(APIError):
    """Raised when resource is not found (404)."""

    pass


class ValidationError(APIError):
    """Raised when validation fails (422)."""

    pass


class RateLimitError(APIError):
    """Raised when rate limit is exceeded (429)."""

    pass


class ServerError(APIError):
    """Raised when server returns 5xx error."""

    pass
