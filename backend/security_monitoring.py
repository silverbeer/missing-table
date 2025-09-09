# -*- coding: utf-8 -*-
"""
Security Monitoring Module with Pydantic Logfire Integration

This module provides comprehensive security monitoring for the Missing Table application,
including authentication failures, suspicious requests, SQL injection attempts, and more.
"""

import os
import time
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import re
import ipaddress
from urllib.parse import unquote

from fastapi import Request, Response

# Conditional imports for security monitoring
DISABLE_SECURITY = os.getenv('DISABLE_SECURITY', 'false').lower() == 'true'

if not DISABLE_SECURITY:
    import logfire
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
else:
    # Create mock objects when security is disabled
    class MockLogfire:
        def configure(self, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
    
    class MockTrace:
        def get_tracer(self, *args, **kwargs):
            return MockTracer()
    
    class MockTracer:
        def start_as_current_span(self, *args, **kwargs):
            return MockSpan()
    
    class MockSpan:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_status(self, *args): pass
        def set_attribute(self, *args, **kwargs): pass
    
    class MockStatus:
        ERROR = "ERROR"
        OK = "OK"
    
    class MockStatusCode:
        ERROR = "ERROR"
        OK = "OK"
    
    logfire = MockLogfire()
    trace = MockTrace()
    Status = MockStatus()
    StatusCode = MockStatusCode()
import redis
from redis import Redis
from pydantic import BaseModel

# Configure Logfire
logger = logging.getLogger(__name__)

class SecurityEventType(str, Enum):
    """Security event types for classification."""
    AUTH_FAILURE = "auth_failure"
    SUSPICIOUS_REQUEST = "suspicious_request"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    DATA_EXFILTRATION = "data_exfiltration"
    SESSION_HIJACKING = "session_hijacking"
    CSRF_ATTACK = "csrf_attack"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"

class SecuritySeverity(str, Enum):
    """Security event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_type: SecurityEventType
    severity: SecuritySeverity
    source_ip: str
    user_agent: str
    timestamp: datetime
    user_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)
    risk_score: int = 0

class SecurityPattern:
    """Security pattern detection for various attack types."""
    
    # SQL Injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bOR\b.*[=<>].*[0-9])",
        r"(\bAND\b.*[=<>].*[0-9])",
        r"('.*--)",
        r"(;.*DROP\b)",
        r"(;.*DELETE\b)",
        r"(;.*INSERT\b)",
        r"(;.*UPDATE\b)",
        r"(\bEXEC\b.*\()",
        r"(\bsp_executesql\b)",
        r"(\bxp_cmdshell\b)",
        r"(\bSYSTEM\b.*\()",
        r"(\bLOAD_FILE\b)",
        r"(\bINTO\b.*\bOUTFILE\b)",
        r"(\bSLEEP\b.*\()",
        r"(\bBENCHMARK\b.*\()",
        r"(\bhex\b.*\()",
        r"(\bchar\b.*\()",
        r"(\bconcat\b.*\(.*\bselect\b)",
        r"(\bsubstring\b.*\(.*\bselect\b)",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"(<script[^>]*>.*?</script>)",
        r"(<iframe[^>]*>.*?</iframe>)",
        r"(<object[^>]*>.*?</object>)",
        r"(<embed[^>]*>.*?</embed>)",
        r"(<applet[^>]*>.*?</applet>)",
        r"(javascript:)",
        r"(vbscript:)",
        r"(data:text/html)",
        r"(onclick\s*=)",
        r"(onload\s*=)",
        r"(onerror\s*=)",
        r"(onmouseover\s*=)",
        r"(onfocus\s*=)",
        r"(onblur\s*=)",
        r"(<img[^>]*onerror)",
        r"(<svg[^>]*onload)",
        r"(document\.cookie)",
        r"(document\.domain)",
        r"(window\.location)",
        r"(eval\s*\()",
        r"(setTimeout\s*\()",
        r"(setInterval\s*\()",
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"(\.\./){2,}",
        r"(\.\.\\){2,}",
        r"(%2e%2e%2f){2,}",
        r"(%2e%2e\\){2,}",
        r"(\.\.%2f){2,}",
        r"(\.\.%5c){2,}",
        r"(%252e%252e%252f){2,}",
        r"(\.\./.*etc/passwd)",
        r"(\.\./.*etc/shadow)",
        r"(\.\./.*windows/system32)",
        r"(\.\./.*boot\.ini)",
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"(;\s*\w+)",
        r"(\|\s*\w+)",
        r"(&\s*\w+)",
        r"(`[^`]+`)",
        r"(\$\([^)]+\))",
        r"(\${[^}]+})",
        r"(wget\s+)",
        r"(curl\s+)",
        r"(nc\s+)",
        r"(netcat\s+)",
        r"(ping\s+)",
        r"(nslookup\s+)",
        r"(dig\s+)",
        r"(cat\s+)",
        r"(ls\s+)",
        r"(ps\s+)",
        r"(id\s+)",
        r"(whoami\s+)",
        r"(uname\s+)",
    ]
    
    # Suspicious user agents
    SUSPICIOUS_USER_AGENTS = [
        "sqlmap",
        "nikto", 
        "nmap",
        "masscan",
        "zap",
        "burp",
        "dirb",
        "gobuster",
        "wfuzz",
        "x-scan",
        "acunetix",
        "nessus",
        "openvas",
        "metasploit",
        "beef",
    ]

class ThreatIntelligence:
    """Threat intelligence for IP reputation and known attack patterns."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis_client = redis_client
        self.known_malicious_ips = set()
        self.tor_exit_nodes = set()
        self.vpn_providers = set()
        self._load_threat_feeds()
    
    def _load_threat_feeds(self):
        """Load threat intelligence feeds."""
        # In production, this would load from external threat feeds
        # For now, we'll use a basic set of known malicious patterns
        self.known_malicious_patterns = {
            "scanner_ips": [
                "185.220.",  # Known Tor range
                "192.42.116.",  # Scanning networks
                "45.142.214.",  # Malicious hosting
            ],
            "cloud_providers": [
                "amazonaws.com",
                "digitalocean.com", 
                "vultr.com",
                "linode.com",
            ]
        }
    
    def is_malicious_ip(self, ip: str) -> bool:
        """Check if IP is known to be malicious."""
        try:
            # Check against known malicious IP patterns
            for pattern in self.known_malicious_patterns["scanner_ips"]:
                if ip.startswith(pattern):
                    return True
            
            # Check if it's a Tor exit node
            if ip in self.tor_exit_nodes:
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error checking IP reputation: {e}")
            return False
    
    def is_cloud_provider(self, ip: str) -> bool:
        """Check if IP belongs to a cloud provider."""
        # This would typically use reverse DNS lookup
        # For demo purposes, we'll use basic patterns
        try:
            # Basic check for cloud provider IP ranges
            ip_obj = ipaddress.ip_address(ip)
            
            # AWS ranges (simplified)
            if ip_obj in ipaddress.ip_network("52.0.0.0/8"):
                return True
            if ip_obj in ipaddress.ip_network("54.0.0.0/8"):
                return True
                
            # Google Cloud ranges (simplified)
            if ip_obj in ipaddress.ip_network("35.0.0.0/8"):
                return True
                
            # Azure ranges (simplified)  
            if ip_obj in ipaddress.ip_network("40.0.0.0/8"):
                return True
                
            return False
        except Exception:
            return False

class SecurityMonitor:
    """Main security monitoring class with Logfire integration."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = Redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
        
        self.threat_intel = ThreatIntelligence(self.redis_client)
        self.tracer = trace.get_tracer(__name__)
        
        # Attack tracking
        self.failed_logins = defaultdict(lambda: deque(maxlen=50))
        self.request_counts = defaultdict(lambda: deque(maxlen=100))
        self.suspicious_activities = defaultdict(list)
        
        # Thresholds
        self.FAILED_LOGIN_THRESHOLD = 5
        self.FAILED_LOGIN_WINDOW = 300  # 5 minutes
        self.REQUEST_RATE_THRESHOLD = 100
        self.REQUEST_RATE_WINDOW = 60  # 1 minute
        
        # Initialize Logfire with security-specific configuration (only if security is enabled)
        if not DISABLE_SECURITY and not os.getenv('DISABLE_LOGFIRE', 'false').lower() == 'true':
            logfire.configure(
                token=os.getenv('LOGFIRE_TOKEN'),
                project_name=os.getenv('LOGFIRE_PROJECT', 'missing-table-security'),
                environment=os.getenv('ENVIRONMENT', 'development'),
            )
    
    def calculate_risk_score(self, event: SecurityEvent) -> int:
        """Calculate risk score for a security event."""
        base_scores = {
            SecurityEventType.AUTH_FAILURE: 20,
            SecurityEventType.SUSPICIOUS_REQUEST: 30,
            SecurityEventType.SQL_INJECTION_ATTEMPT: 80,
            SecurityEventType.XSS_ATTEMPT: 70,
            SecurityEventType.BRUTE_FORCE_ATTACK: 90,
            SecurityEventType.RATE_LIMIT_EXCEEDED: 40,
            SecurityEventType.UNAUTHORIZED_ACCESS: 60,
            SecurityEventType.ANOMALOUS_BEHAVIOR: 50,
            SecurityEventType.DATA_EXFILTRATION: 95,
            SecurityEventType.SESSION_HIJACKING: 85,
            SecurityEventType.CSRF_ATTACK: 65,
            SecurityEventType.PATH_TRAVERSAL: 75,
            SecurityEventType.COMMAND_INJECTION: 90,
        }
        
        score = base_scores.get(event.event_type, 30)
        
        # Increase score based on factors
        if self.threat_intel.is_malicious_ip(event.source_ip):
            score += 30
        
        if self.threat_intel.is_cloud_provider(event.source_ip):
            score += 10
        
        # Check for automation/bot behavior
        ua_lower = event.user_agent.lower()
        for suspicious_ua in SecurityPattern.SUSPICIOUS_USER_AGENTS:
            if suspicious_ua in ua_lower:
                score += 40
                break
        
        # Check for repeated failures from same IP
        if event.event_type == SecurityEventType.AUTH_FAILURE:
            recent_failures = len([
                t for t in self.failed_logins[event.source_ip]
                if time.time() - t < self.FAILED_LOGIN_WINDOW
            ])
            score += min(recent_failures * 10, 50)
        
        return min(score, 100)
    
    def detect_sql_injection(self, text: str) -> bool:
        """Detect SQL injection attempts."""
        if not text:
            return False
        
        # URL decode the text
        decoded_text = unquote(text).lower()
        
        for pattern in SecurityPattern.SQL_INJECTION_PATTERNS:
            if re.search(pattern, decoded_text, re.IGNORECASE):
                return True
        return False
    
    def detect_xss(self, text: str) -> bool:
        """Detect XSS attempts."""
        if not text:
            return False
        
        # URL decode the text
        decoded_text = unquote(text).lower()
        
        for pattern in SecurityPattern.XSS_PATTERNS:
            if re.search(pattern, decoded_text, re.IGNORECASE):
                return True
        return False
    
    def detect_path_traversal(self, text: str) -> bool:
        """Detect path traversal attempts."""
        if not text:
            return False
        
        # URL decode the text
        decoded_text = unquote(text)
        
        for pattern in SecurityPattern.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, decoded_text, re.IGNORECASE):
                return True
        return False
    
    def detect_command_injection(self, text: str) -> bool:
        """Detect command injection attempts."""
        if not text:
            return False
        
        # URL decode the text
        decoded_text = unquote(text)
        
        for pattern in SecurityPattern.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, decoded_text, re.IGNORECASE):
                return True
        return False
    
    def analyze_request_for_threats(self, request: Request, payload: Optional[Dict] = None) -> List[SecurityEvent]:
        """Analyze request for security threats."""
        events = []
        current_time = datetime.utcnow()
        
        # Get client IP
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Analyze URL path
        path = str(request.url.path)
        if self.detect_path_traversal(path):
            events.append(SecurityEvent(
                event_type=SecurityEventType.PATH_TRAVERSAL,
                severity=SecuritySeverity.HIGH,
                source_ip=client_ip,
                user_agent=user_agent,
                timestamp=current_time,
                endpoint=path,
                method=request.method,
                additional_context={"path": path}
            ))
        
        # Analyze query parameters
        for key, value in request.query_params.items():
            param_value = str(value)
            
            if self.detect_sql_injection(param_value):
                events.append(SecurityEvent(
                    event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                    severity=SecuritySeverity.CRITICAL,
                    source_ip=client_ip,
                    user_agent=user_agent,
                    timestamp=current_time,
                    endpoint=path,
                    method=request.method,
                    additional_context={"parameter": key, "value": param_value}
                ))
            
            if self.detect_xss(param_value):
                events.append(SecurityEvent(
                    event_type=SecurityEventType.XSS_ATTEMPT,
                    severity=SecuritySeverity.HIGH,
                    source_ip=client_ip,
                    user_agent=user_agent,
                    timestamp=current_time,
                    endpoint=path,
                    method=request.method,
                    additional_context={"parameter": key, "value": param_value}
                ))
            
            if self.detect_command_injection(param_value):
                events.append(SecurityEvent(
                    event_type=SecurityEventType.COMMAND_INJECTION,
                    severity=SecuritySeverity.CRITICAL,
                    source_ip=client_ip,
                    user_agent=user_agent,
                    timestamp=current_time,
                    endpoint=path,
                    method=request.method,
                    additional_context={"parameter": key, "value": param_value}
                ))
        
        # Analyze headers for suspicious patterns
        if user_agent:
            ua_lower = user_agent.lower()
            for suspicious_ua in SecurityPattern.SUSPICIOUS_USER_AGENTS:
                if suspicious_ua in ua_lower:
                    events.append(SecurityEvent(
                        event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                        severity=SecuritySeverity.MEDIUM,
                        source_ip=client_ip,
                        user_agent=user_agent,
                        timestamp=current_time,
                        endpoint=path,
                        method=request.method,
                        additional_context={"reason": "suspicious_user_agent"}
                    ))
                    break
        
        # Analyze payload if present
        if payload:
            payload_str = json.dumps(payload)
            
            if self.detect_sql_injection(payload_str):
                events.append(SecurityEvent(
                    event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                    severity=SecuritySeverity.CRITICAL,
                    source_ip=client_ip,
                    user_agent=user_agent,
                    timestamp=current_time,
                    endpoint=path,
                    method=request.method,
                    payload=payload,
                    additional_context={"location": "request_body"}
                ))
            
            if self.detect_xss(payload_str):
                events.append(SecurityEvent(
                    event_type=SecurityEventType.XSS_ATTEMPT,
                    severity=SecuritySeverity.HIGH,
                    source_ip=client_ip,
                    user_agent=user_agent,
                    timestamp=current_time,
                    endpoint=path,
                    method=request.method,
                    payload=payload,
                    additional_context={"location": "request_body"}
                ))
        
        # Calculate risk scores
        for event in events:
            event.risk_score = self.calculate_risk_score(event)
        
        return events
    
    def log_authentication_failure(self, request: Request, email: str, reason: str = "invalid_credentials"):
        """Log authentication failure with security monitoring."""
        client_ip = self.get_client_ip(request)
        current_time = time.time()
        
        # Track failed login attempts
        self.failed_logins[client_ip].append(current_time)
        
        # Check for brute force attack
        recent_failures = [
            t for t in self.failed_logins[client_ip]
            if current_time - t < self.FAILED_LOGIN_WINDOW
        ]
        
        severity = SecuritySeverity.LOW
        event_type = SecurityEventType.AUTH_FAILURE
        
        if len(recent_failures) >= self.FAILED_LOGIN_THRESHOLD:
            severity = SecuritySeverity.HIGH
            event_type = SecurityEventType.BRUTE_FORCE_ATTACK
        
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "email": email,
                "reason": reason,
                "recent_failures": len(recent_failures),
                "is_malicious_ip": self.threat_intel.is_malicious_ip(client_ip),
                "is_cloud_provider": self.threat_intel.is_cloud_provider(client_ip)
            }
        )
        event.risk_score = self.calculate_risk_score(event)
        
        self.log_security_event(event)
    
    def log_unauthorized_access(self, request: Request, user_id: Optional[str] = None, required_role: Optional[str] = None):
        """Log unauthorized access attempts."""
        client_ip = self.get_client_ip(request)
        
        event = SecurityEvent(
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            severity=SecuritySeverity.MEDIUM,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "required_role": required_role,
                "is_malicious_ip": self.threat_intel.is_malicious_ip(client_ip)
            }
        )
        event.risk_score = self.calculate_risk_score(event)
        
        self.log_security_event(event)
    
    def log_rate_limit_exceeded(self, request: Request, limit_type: str = "general"):
        """Log rate limit exceeded events."""
        client_ip = self.get_client_ip(request)
        
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecuritySeverity.MEDIUM,
            source_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=datetime.utcnow(),
            endpoint=str(request.url.path),
            method=request.method,
            additional_context={
                "limit_type": limit_type,
                "is_malicious_ip": self.threat_intel.is_malicious_ip(client_ip)
            }
        )
        event.risk_score = self.calculate_risk_score(event)
        
        self.log_security_event(event)
    
    def log_security_event(self, event: SecurityEvent):
        """Log security event to Logfire with proper formatting."""
        with self.tracer.start_as_current_span("security_event") as span:
            # Set span attributes
            span.set_attribute("security.event_type", event.event_type)
            span.set_attribute("security.severity", event.severity)
            span.set_attribute("security.source_ip", event.source_ip)
            span.set_attribute("security.risk_score", event.risk_score)
            
            if event.user_id:
                span.set_attribute("security.user_id", event.user_id)
            if event.endpoint:
                span.set_attribute("security.endpoint", event.endpoint)
            if event.method:
                span.set_attribute("security.method", event.method)
            
            # Set span status based on severity
            if event.severity in [SecuritySeverity.HIGH, SecuritySeverity.CRITICAL]:
                span.set_status(Status(StatusCode.ERROR))
            
            # Log to Logfire
            logfire.warn(
                "Security Event Detected",
                event_type=event.event_type,
                severity=event.severity,
                source_ip=event.source_ip,
                user_agent=event.user_agent,
                timestamp=event.timestamp.isoformat(),
                user_id=event.user_id,
                endpoint=event.endpoint,
                method=event.method,
                payload=event.payload,
                additional_context=event.additional_context,
                risk_score=event.risk_score,
            )
            
            # Store in Redis for real-time analysis
            if self.redis_client:
                try:
                    event_key = f"security_event:{event.timestamp.isoformat()}:{hashlib.md5(f'{event.source_ip}{event.event_type}'.encode()).hexdigest()}"
                    event_data = {
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "source_ip": event.source_ip,
                        "user_agent": event.user_agent,
                        "timestamp": event.timestamp.isoformat(),
                        "user_id": event.user_id,
                        "endpoint": event.endpoint,
                        "method": event.method,
                        "risk_score": event.risk_score,
                        "additional_context": json.dumps(event.additional_context)
                    }
                    
                    # Store event with TTL of 7 days
                    self.redis_client.hset(event_key, mapping=event_data)
                    self.redis_client.expire(event_key, 604800)  # 7 days
                    
                    # Add to IP-based tracking
                    ip_events_key = f"ip_events:{event.source_ip}"
                    self.redis_client.lpush(ip_events_key, event_key)
                    self.redis_client.ltrim(ip_events_key, 0, 99)  # Keep last 100 events
                    self.redis_client.expire(ip_events_key, 86400)  # 1 day
                    
                except Exception as e:
                    logger.error(f"Failed to store security event in Redis: {e}")
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, considering proxies."""
        # Check for forwarded headers (common with load balancers)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return getattr(request.client, 'host', 'unknown')
    
    def get_security_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get security analytics for the specified time period."""
        if not self.redis_client:
            return {"error": "Redis not available for analytics"}
        
        try:
            analytics = {
                "time_period_hours": hours,
                "total_events": 0,
                "events_by_type": defaultdict(int),
                "events_by_severity": defaultdict(int),
                "top_source_ips": defaultdict(int),
                "risk_score_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                "recent_events": []
            }
            
            # Scan for all security events in the time period
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Get all security event keys
            for key in self.redis_client.scan_iter(match="security_event:*"):
                event_data = self.redis_client.hgetall(key)
                if not event_data:
                    continue
                
                event_timestamp = datetime.fromisoformat(event_data.get("timestamp", ""))
                if event_timestamp < cutoff_time:
                    continue
                
                analytics["total_events"] += 1
                analytics["events_by_type"][event_data.get("event_type", "unknown")] += 1
                analytics["events_by_severity"][event_data.get("severity", "unknown")] += 1
                analytics["top_source_ips"][event_data.get("source_ip", "unknown")] += 1
                
                # Risk score distribution
                risk_score = int(event_data.get("risk_score", 0))
                if risk_score >= 80:
                    analytics["risk_score_distribution"]["critical"] += 1
                elif risk_score >= 60:
                    analytics["risk_score_distribution"]["high"] += 1
                elif risk_score >= 30:
                    analytics["risk_score_distribution"]["medium"] += 1
                else:
                    analytics["risk_score_distribution"]["low"] += 1
                
                # Add to recent events (limit to 50)
                if len(analytics["recent_events"]) < 50:
                    analytics["recent_events"].append({
                        "timestamp": event_data.get("timestamp"),
                        "event_type": event_data.get("event_type"),
                        "severity": event_data.get("severity"),
                        "source_ip": event_data.get("source_ip"),
                        "endpoint": event_data.get("endpoint"),
                        "risk_score": risk_score
                    })
            
            # Sort recent events by timestamp (newest first)
            analytics["recent_events"].sort(
                key=lambda x: x.get("timestamp", ""), 
                reverse=True
            )
            
            # Convert defaultdict to regular dict for JSON serialization
            analytics["events_by_type"] = dict(analytics["events_by_type"])
            analytics["events_by_severity"] = dict(analytics["events_by_severity"])
            analytics["top_source_ips"] = dict(sorted(
                analytics["top_source_ips"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])  # Top 10 IPs
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating security analytics: {e}")
            return {"error": str(e)}

# Global security monitor instance (lazy initialization)
_security_monitor = None

def get_security_monitor() -> SecurityMonitor:
    """Get the global security monitor instance."""
    global _security_monitor
    if _security_monitor is None and not DISABLE_SECURITY:
        _security_monitor = SecurityMonitor(redis_url=os.getenv('REDIS_URL'))
    return _security_monitor