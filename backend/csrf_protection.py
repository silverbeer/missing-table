# -*- coding: utf-8 -*-
"""
CSRF protection middleware for the sports league backend.
"""
import secrets
import hashlib
import logging
from typing import Optional, Tuple
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse
import os

logger = logging.getLogger(__name__)

# Configuration
CSRF_SECRET_KEY = os.getenv('CSRF_SECRET_KEY', secrets.token_urlsafe(32))
CSRF_TOKEN_LIFETIME = 3600  # 1 hour
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"

# Methods that require CSRF protection
PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Paths that are exempt from CSRF protection
CSRF_EXEMPT_PATHS = {
    "/api/auth/login",  # Login needs to work without existing token
    "/api/auth/signup",  # Signup needs to work without existing token
    "/api/auth/refresh",  # Token refresh endpoint
    "/docs",  # API documentation
    "/openapi.json",  # OpenAPI spec
    "/redoc",  # ReDoc documentation
}


class CSRFProtection:
    """CSRF Protection middleware for FastAPI."""
    
    def __init__(self):
        self.secret_key = CSRF_SECRET_KEY
        
    def generate_csrf_token(self) -> str:
        """Generate a new CSRF token."""
        token = secrets.token_urlsafe(32)
        return token
    
    def verify_csrf_token(self, token: str, cookie_token: str) -> bool:
        """Verify that the provided token matches the cookie token."""
        if not token or not cookie_token:
            return False
        
        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(token, cookie_token)
    
    def get_csrf_token_from_request(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request headers."""
        return request.headers.get(CSRF_HEADER_NAME)
    
    def get_csrf_cookie_from_request(self, request: Request) -> Optional[str]:
        """Extract CSRF token from cookies."""
        return request.cookies.get(CSRF_COOKIE_NAME)
    
    def is_exempt(self, path: str) -> bool:
        """Check if the path is exempt from CSRF protection."""
        # Check exact matches
        if path in CSRF_EXEMPT_PATHS:
            return True
        
        # Check prefixes (for paths with parameters)
        for exempt_path in CSRF_EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return True
        
        return False
    
    def set_csrf_cookie(self, response: Response, token: str):
        """Set CSRF token cookie in response."""
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            max_age=CSRF_TOKEN_LIFETIME,
            httponly=True,
            secure=os.getenv('ENVIRONMENT', 'development') == 'production',
            samesite='strict'
        )


# Global CSRF protection instance
csrf_protection = CSRFProtection()


async def csrf_middleware(request: Request, call_next):
    """CSRF protection middleware."""
    # Skip CSRF check for safe methods
    if request.method not in PROTECTED_METHODS:
        response = await call_next(request)
        
        # For GET requests, ensure a CSRF token is set
        if request.method == "GET":
            cookie_token = csrf_protection.get_csrf_cookie_from_request(request)
            if not cookie_token:
                token = csrf_protection.generate_csrf_token()
                response = await call_next(request)
                csrf_protection.set_csrf_cookie(response, token)
                return response
        
        return response
    
    # Skip CSRF check for exempt paths
    if csrf_protection.is_exempt(request.url.path):
        return await call_next(request)
    
    # Get tokens
    header_token = csrf_protection.get_csrf_token_from_request(request)
    cookie_token = csrf_protection.get_csrf_cookie_from_request(request)
    
    # Verify CSRF token
    if not csrf_protection.verify_csrf_token(header_token, cookie_token):
        logger.warning(f"CSRF token validation failed for {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token validation failed"}
        )
    
    # Process request
    response = await call_next(request)
    
    # Refresh CSRF token cookie
    if cookie_token:
        csrf_protection.set_csrf_cookie(response, cookie_token)
    
    return response


def get_csrf_token(request: Request) -> str:
    """Get or generate CSRF token for the current request."""
    token = csrf_protection.get_csrf_cookie_from_request(request)
    if not token:
        token = csrf_protection.generate_csrf_token()
    return token


# Dependency for endpoints that need to provide CSRF token
async def provide_csrf_token(request: Request, response: Response) -> dict:
    """Provide CSRF token in response."""
    token = get_csrf_token(request)
    csrf_protection.set_csrf_cookie(response, token)
    return {"csrf_token": token}