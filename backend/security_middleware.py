# -*- coding: utf-8 -*-
"""
Security Middleware for FastAPI with Logfire Integration

This middleware provides comprehensive security monitoring for all FastAPI requests,
including threat detection, performance monitoring, and security analytics.
"""

import time
import json
import asyncio
import logging
from typing import Callable, Dict, Any, Optional
from datetime import datetime

import logfire
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from security_monitoring import (
    SecurityMonitor, 
    SecurityEvent, 
    SecurityEventType, 
    SecuritySeverity,
    get_security_monitor
)

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware with Logfire integration."""
    
    def __init__(self, app: ASGIApp, security_monitor: Optional[SecurityMonitor] = None):
        super().__init__(app)
        self.security_monitor = security_monitor or get_security_monitor()
        self.tracer = trace.get_tracer(__name__)
        
        # Performance thresholds
        self.SLOW_REQUEST_THRESHOLD = 5.0  # seconds
        self.VERY_SLOW_REQUEST_THRESHOLD = 10.0  # seconds
        
        # Request size limits
        self.MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
        self.LARGE_REQUEST_THRESHOLD = 1024 * 1024  # 1MB
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method."""
        start_time = time.time()
        client_ip = self.security_monitor.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        request_id = f"{start_time}_{hash(f'{client_ip}{request.url.path}')}"
        
        with self.tracer.start_as_current_span("security_middleware") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.user_agent", user_agent)
            span.set_attribute("http.client_ip", client_ip)
            span.set_attribute("http.request_id", request_id)
            
            try:
                # Pre-request security checks
                await self._pre_request_security_checks(request, span)
                
                # Process the request
                response = await call_next(request)
                
                # Post-request security analysis
                await self._post_request_security_analysis(
                    request, response, start_time, span
                )
                
                return response
                
            except HTTPException as e:
                # Log HTTP exceptions as potential security events
                await self._handle_http_exception(request, e, start_time, span)
                raise
            except Exception as e:
                # Log unexpected exceptions
                await self._handle_unexpected_exception(request, e, start_time, span)
                raise
    
    async def _pre_request_security_checks(self, request: Request, span):
        """Perform security checks before processing the request."""
        client_ip = self.security_monitor.get_client_ip(request)
        
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                span.set_attribute("http.request_size", size)
                
                if size > self.MAX_REQUEST_SIZE:
                    self.security_monitor.log_security_event(SecurityEvent(
                        event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                        severity=SecuritySeverity.HIGH,
                        source_ip=client_ip,
                        user_agent=request.headers.get("user-agent", ""),
                        timestamp=datetime.utcnow(),
                        endpoint=str(request.url.path),
                        method=request.method,
                        additional_context={
                            "reason": "request_too_large",
                            "size": size,
                            "max_allowed": self.MAX_REQUEST_SIZE
                        }
                    ))
                    raise HTTPException(status_code=413, detail="Request entity too large")
                
                if size > self.LARGE_REQUEST_THRESHOLD:
                    logfire.info(
                        "Large request detected",
                        size=size,
                        client_ip=client_ip,
                        endpoint=str(request.url.path),
                        method=request.method
                    )
            except ValueError:
                pass  # Invalid content-length header
        
        # Analyze request for threats (without reading body yet)
        threat_events = self.security_monitor.analyze_request_for_threats(request)
        
        # Log all detected threats
        for event in threat_events:
            self.security_monitor.log_security_event(event)
            
            # Block critical threats
            if event.severity == SecuritySeverity.CRITICAL:
                span.set_status(Status(StatusCode.ERROR, "Critical security threat detected"))
                raise HTTPException(
                    status_code=403, 
                    detail="Request blocked due to security policy violation"
                )
        
        # Rate limiting check (basic implementation)
        await self._check_rate_limiting(request, span)
    
    async def _check_rate_limiting(self, request: Request, span):
        """Check rate limiting for the request."""
        # This is a basic implementation - in production you'd use Redis
        # or a more sophisticated rate limiting solution
        client_ip = self.security_monitor.get_client_ip(request)
        current_time = time.time()
        
        # Track requests in security monitor
        if hasattr(self.security_monitor, 'request_counts'):
            self.security_monitor.request_counts[client_ip].append(current_time)
            
            # Count requests in the last minute
            recent_requests = [
                t for t in self.security_monitor.request_counts[client_ip]
                if current_time - t < 60
            ]
            
            span.set_attribute("rate_limit.recent_requests", len(recent_requests))
            
            if len(recent_requests) > self.security_monitor.REQUEST_RATE_THRESHOLD:
                self.security_monitor.log_rate_limit_exceeded(request, "general")
                raise HTTPException(
                    status_code=429, 
                    detail="Rate limit exceeded"
                )
    
    async def _post_request_security_analysis(
        self, 
        request: Request, 
        response: Response, 
        start_time: float, 
        span
    ):
        """Perform security analysis after request processing."""
        duration = time.time() - start_time
        client_ip = self.security_monitor.get_client_ip(request)
        
        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.response_time", duration)
        
        # Log slow requests as potential DoS attempts
        if duration > self.VERY_SLOW_REQUEST_THRESHOLD:
            self.security_monitor.log_security_event(SecurityEvent(
                event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                severity=SecuritySeverity.MEDIUM,
                source_ip=client_ip,
                user_agent=request.headers.get("user-agent", ""),
                timestamp=datetime.utcnow(),
                endpoint=str(request.url.path),
                method=request.method,
                additional_context={
                    "reason": "very_slow_request",
                    "duration": duration,
                    "threshold": self.VERY_SLOW_REQUEST_THRESHOLD
                }
            ))
        elif duration > self.SLOW_REQUEST_THRESHOLD:
            logfire.info(
                "Slow request detected",
                duration=duration,
                client_ip=client_ip,
                endpoint=str(request.url.path),
                method=request.method,
                status_code=response.status_code
            )
        
        # Log security-relevant status codes
        if response.status_code == 401:
            # Already handled in auth endpoints
            pass
        elif response.status_code == 403:
            self.security_monitor.log_unauthorized_access(request)
        elif response.status_code == 404:
            # Track 404s for potential reconnaissance
            await self._track_404_patterns(request, span)
        elif response.status_code >= 500:
            # Server errors might indicate attacks
            await self._track_server_errors(request, response, span)
        
        # Log successful request for analytics
        logfire.info(
            "Request processed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration=duration,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", "")[:100]  # Truncate long user agents
        )
    
    async def _track_404_patterns(self, request: Request, span):
        """Track 404 patterns for potential reconnaissance."""
        client_ip = self.security_monitor.get_client_ip(request)
        
        # Common reconnaissance patterns
        recon_patterns = [
            "/admin",
            "/wp-admin",
            "/administrator",
            "/phpmyadmin",
            "/xmlrpc.php",
            "/robots.txt",
            "/.env",
            "/.git",
            "/config",
            "/backup",
            "/test",
            "/debug"
        ]
        
        path = str(request.url.path).lower()
        for pattern in recon_patterns:
            if pattern in path:
                self.security_monitor.log_security_event(SecurityEvent(
                    event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                    severity=SecuritySeverity.MEDIUM,
                    source_ip=client_ip,
                    user_agent=request.headers.get("user-agent", ""),
                    timestamp=datetime.utcnow(),
                    endpoint=str(request.url.path),
                    method=request.method,
                    additional_context={
                        "reason": "reconnaissance_attempt",
                        "pattern": pattern
                    }
                ))
                break
    
    async def _track_server_errors(self, request: Request, response: Response, span):
        """Track server errors for potential attack patterns."""
        client_ip = self.security_monitor.get_client_ip(request)
        
        # Log server errors as they might indicate successful attacks
        self.security_monitor.log_security_event(SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_REQUEST,
            severity=SecuritySeverity.HIGH if response.status_code >= 500 else SecuritySeverity.MEDIUM,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "reason": "server_error",
                "status_code": response.status_code
            }
        ))
        
        span.set_status(Status(StatusCode.ERROR, f"Server error: {response.status_code}"))
    
    async def _handle_http_exception(
        self, 
        request: Request, 
        exception: HTTPException, 
        start_time: float, 
        span
    ):
        """Handle HTTP exceptions with security logging."""
        duration = time.time() - start_time
        client_ip = self.security_monitor.get_client_ip(request)
        
        span.set_attribute("http.status_code", exception.status_code)
        span.set_attribute("http.response_time", duration)
        span.set_attribute("exception.type", "HTTPException")
        span.set_attribute("exception.message", str(exception.detail))
        
        # Log based on status code
        if exception.status_code == 403:
            severity = SecuritySeverity.HIGH
            event_type = SecurityEventType.UNAUTHORIZED_ACCESS
        elif exception.status_code == 429:
            severity = SecuritySeverity.MEDIUM
            event_type = SecurityEventType.RATE_LIMIT_EXCEEDED
        else:
            severity = SecuritySeverity.LOW
            event_type = SecurityEventType.SUSPICIOUS_REQUEST
        
        self.security_monitor.log_security_event(SecurityEvent(
            event_type=event_type,
            severity=severity,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "status_code": exception.status_code,
                "detail": str(exception.detail),
                "duration": duration
            }
        ))
        
        logfire.warn(
            "HTTP Exception occurred",
            status_code=exception.status_code,
            detail=str(exception.detail),
            client_ip=client_ip,
            endpoint=str(request.url.path),
            method=request.method,
            duration=duration
        )
    
    async def _handle_unexpected_exception(
        self, 
        request: Request, 
        exception: Exception, 
        start_time: float, 
        span
    ):
        """Handle unexpected exceptions with security logging."""
        duration = time.time() - start_time
        client_ip = self.security_monitor.get_client_ip(request)
        
        span.set_attribute("http.response_time", duration)
        span.set_attribute("exception.type", type(exception).__name__)
        span.set_attribute("exception.message", str(exception))
        span.set_status(Status(StatusCode.ERROR, str(exception)))
        
        # Log unexpected exceptions as potential attack indicators
        self.security_monitor.log_security_event(SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_REQUEST,
            severity=SecuritySeverity.HIGH,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "duration": duration
            }
        ))
        
        logfire.error(
            "Unexpected exception occurred",
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            client_ip=client_ip,
            endpoint=str(request.url.path),
            method=request.method,
            duration=duration
        )

class DatabaseQueryMonitor:
    """Monitor database queries for security threats."""
    
    def __init__(self, security_monitor: SecurityMonitor):
        self.security_monitor = security_monitor
        self.tracer = trace.get_tracer(__name__)
    
    def monitor_query(self, query: str, params: Any = None, client_ip: str = "unknown"):
        """Monitor a database query for security threats."""
        with self.tracer.start_as_current_span("database_query_monitor") as span:
            span.set_attribute("db.statement", query)
            span.set_attribute("db.client_ip", client_ip)
            
            # Check for SQL injection patterns
            if self.security_monitor.detect_sql_injection(query):
                event = SecurityEvent(
                    event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                    severity=SecuritySeverity.CRITICAL,
                    source_ip=client_ip,
                    user_agent="database_query",
                    timestamp=datetime.utcnow(),
                    additional_context={
                        "query": query,
                        "params": str(params) if params else None,
                        "location": "database_query"
                    }
                )
                event.risk_score = self.security_monitor.calculate_risk_score(event)
                self.security_monitor.log_security_event(event)
                
                span.set_status(Status(StatusCode.ERROR, "SQL injection attempt detected"))
                
                # In production, you might want to block the query
                logfire.error(
                    "SQL injection attempt detected in database query",
                    query=query,
                    client_ip=client_ip,
                    risk_score=event.risk_score
                )
            
            # Monitor for suspicious query patterns
            suspicious_patterns = [
                r"SELECT.*FROM.*WHERE.*=.*OR.*=",
                r"UNION.*SELECT",
                r"DROP\s+TABLE",
                r"DELETE\s+FROM.*WHERE.*1=1",
                r"UPDATE.*SET.*WHERE.*1=1"
            ]
            
            import re
            for pattern in suspicious_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    logfire.warn(
                        "Suspicious database query pattern detected",
                        pattern=pattern,
                        query=query,
                        client_ip=client_ip
                    )
                    break
            
            # Log query for performance monitoring
            logfire.debug(
                "Database query executed",
                query_type=query.split()[0].upper() if query.split() else "UNKNOWN",
                client_ip=client_ip
            )

# Global database query monitor
db_query_monitor = None

def get_db_query_monitor() -> DatabaseQueryMonitor:
    """Get the global database query monitor instance."""
    global db_query_monitor
    if db_query_monitor is None:
        db_query_monitor = DatabaseQueryMonitor(get_security_monitor())
    return db_query_monitor