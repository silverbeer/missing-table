# -*- coding: utf-8 -*-
"""
Enhanced Authentication Security Module

This module provides enhanced security monitoring for authentication events,
including anomaly detection, session management, and behavioral analysis.
"""

import os
import time
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
import jwt
import ipaddress
from user_agents import parse

import logfire
from fastapi import Request, HTTPException
from opentelemetry import trace

from security_monitoring import (
    SecurityMonitor, 
    SecurityEvent, 
    SecurityEventType, 
    SecuritySeverity,
    get_security_monitor
)

logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    """User session information for security monitoring."""
    user_id: str
    session_id: str
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    is_suspicious: bool = False
    risk_factors: List[str] = None
    
    def __post_init__(self):
        if self.risk_factors is None:
            self.risk_factors = []

@dataclass
class AuthenticationAttempt:
    """Authentication attempt information."""
    email: str
    ip_address: str
    user_agent: str
    timestamp: datetime
    success: bool
    failure_reason: Optional[str] = None
    risk_score: int = 0

class AuthenticationSecurityMonitor:
    """Enhanced authentication security monitoring."""
    
    def __init__(self, security_monitor: Optional[SecurityMonitor] = None):
        self.security_monitor = security_monitor or get_security_monitor()
        self.tracer = trace.get_tracer(__name__)
        
        # Session tracking
        self.active_sessions: Dict[str, UserSession] = {}
        self.failed_attempts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.successful_logins: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        
        # Security thresholds
        self.MAX_FAILED_ATTEMPTS = 5
        self.FAILED_ATTEMPT_WINDOW = 300  # 5 minutes
        self.SUSPICIOUS_LOGIN_THRESHOLD = 3
        self.SESSION_TIMEOUT = 3600  # 1 hour
        self.MAX_CONCURRENT_SESSIONS = 5
        
        # Geographical and device tracking
        self.user_locations: Dict[str, List[str]] = defaultdict(list)
        self.user_devices: Dict[str, List[str]] = defaultdict(list)
    
    def analyze_authentication_attempt(
        self, 
        request: Request, 
        email: str, 
        success: bool,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> AuthenticationAttempt:
        """Analyze an authentication attempt for security threats."""
        
        with self.tracer.start_as_current_span("auth_security_analysis") as span:
            client_ip = self.security_monitor.get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            current_time = datetime.utcnow()
            
            span.set_attribute("auth.email", email)
            span.set_attribute("auth.success", success)
            span.set_attribute("auth.client_ip", client_ip)
            span.set_attribute("auth.user_id", user_id or "")
            
            attempt = AuthenticationAttempt(
                email=email,
                ip_address=client_ip,
                user_agent=user_agent,
                timestamp=current_time,
                success=success,
                failure_reason=failure_reason
            )
            
            if success:
                self._handle_successful_login(attempt, user_id, request, span)
            else:
                self._handle_failed_login(attempt, request, span)
            
            # Calculate overall risk score
            attempt.risk_score = self._calculate_auth_risk_score(attempt)
            span.set_attribute("auth.risk_score", attempt.risk_score)
            
            # Log to Logfire
            logfire.info(
                "Authentication attempt analyzed",
                email=email,
                success=success,
                client_ip=client_ip,
                user_agent=user_agent[:100],  # Truncate long user agents
                risk_score=attempt.risk_score,
                failure_reason=failure_reason,
                user_id=user_id
            )
            
            return attempt
    
    def _handle_successful_login(
        self, 
        attempt: AuthenticationAttempt, 
        user_id: str, 
        request: Request,
        span
    ):
        """Handle successful login with security analysis."""
        
        # Track successful login
        self.successful_logins[attempt.email].append(attempt.timestamp)
        
        # Analyze login patterns
        risk_factors = self._analyze_login_patterns(attempt, user_id)
        
        # Check for suspicious timing
        if self._is_suspicious_timing(attempt.email, attempt.timestamp):
            risk_factors.append("suspicious_timing")
        
        # Check for location anomalies
        if self._is_location_anomaly(user_id, attempt.ip_address):
            risk_factors.append("location_anomaly")
        
        # Check for device anomalies
        if self._is_device_anomaly(user_id, attempt.user_agent):
            risk_factors.append("device_anomaly")
        
        # Check for concurrent sessions
        if self._check_concurrent_sessions(user_id, attempt.ip_address):
            risk_factors.append("concurrent_sessions")
        
        # Create or update session
        session_id = self._generate_session_id(user_id, attempt.ip_address)
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            ip_address=attempt.ip_address,
            user_agent=attempt.user_agent,
            created_at=attempt.timestamp,
            last_activity=attempt.timestamp,
            is_suspicious=len(risk_factors) > 0,
            risk_factors=risk_factors
        )
        
        self.active_sessions[session_id] = session
        
        # Log suspicious successful logins
        if risk_factors:
            self.security_monitor.log_security_event(SecurityEvent(
                event_type=SecurityEventType.ANOMALOUS_BEHAVIOR,
                severity=SecuritySeverity.MEDIUM,
                source_ip=attempt.ip_address,
                user_agent=attempt.user_agent,
                timestamp=attempt.timestamp,
                user_id=user_id,
                endpoint="/api/auth/login",
                method="POST",
                additional_context={
                    "email": attempt.email,
                    "risk_factors": risk_factors,
                    "session_id": session_id
                }
            ))
            
            span.set_attribute("auth.suspicious", True)
            span.set_attribute("auth.risk_factors", ",".join(risk_factors))
        
        # Update user tracking data
        self._update_user_tracking(user_id, attempt.ip_address, attempt.user_agent)
        
        logfire.info(
            "Successful login processed",
            user_id=user_id,
            email=attempt.email,
            client_ip=attempt.ip_address,
            session_id=session_id,
            risk_factors=risk_factors,
            is_suspicious=len(risk_factors) > 0
        )
    
    def _handle_failed_login(self, attempt: AuthenticationAttempt, request: Request, span):
        """Handle failed login with security analysis."""
        
        # Track failed attempt
        self.failed_attempts[attempt.ip_address].append(attempt.timestamp)
        
        # Check for brute force patterns
        recent_failures = [
            ts for ts in self.failed_attempts[attempt.ip_address]
            if (attempt.timestamp - ts).total_seconds() < self.FAILED_ATTEMPT_WINDOW
        ]
        
        span.set_attribute("auth.recent_failures", len(recent_failures))
        
        # Determine severity based on failure count and patterns
        if len(recent_failures) >= self.MAX_FAILED_ATTEMPTS:
            # Brute force attack detected
            self.security_monitor.log_security_event(SecurityEvent(
                event_type=SecurityEventType.BRUTE_FORCE_ATTACK,
                severity=SecuritySeverity.HIGH,
                source_ip=attempt.ip_address,
                user_agent=attempt.user_agent,
                timestamp=attempt.timestamp,
                endpoint="/api/auth/login",
                method="POST",
                additional_context={
                    "email": attempt.email,
                    "failure_reason": attempt.failure_reason,
                    "recent_failures": len(recent_failures),
                    "time_window": self.FAILED_ATTEMPT_WINDOW
                }
            ))
            
            span.set_attribute("auth.brute_force_detected", True)
            
        else:
            # Regular failed login
            self.security_monitor.log_authentication_failure(
                request, attempt.email, attempt.failure_reason or "unknown"
            )
        
        # Check for credential stuffing patterns
        if self._detect_credential_stuffing(attempt):
            self.security_monitor.log_security_event(SecurityEvent(
                event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                severity=SecuritySeverity.HIGH,
                source_ip=attempt.ip_address,
                user_agent=attempt.user_agent,
                timestamp=attempt.timestamp,
                endpoint="/api/auth/login",
                method="POST",
                additional_context={
                    "email": attempt.email,
                    "attack_type": "credential_stuffing"
                }
            ))
    
    def _analyze_login_patterns(self, attempt: AuthenticationAttempt, user_id: str) -> List[str]:
        """Analyze login patterns for anomalies."""
        risk_factors = []
        
        # Check login frequency
        recent_logins = [
            ts for ts in self.successful_logins[attempt.email]
            if (attempt.timestamp - ts).total_seconds() < 3600  # Last hour
        ]
        
        if len(recent_logins) > self.SUSPICIOUS_LOGIN_THRESHOLD:
            risk_factors.append("high_frequency_logins")
        
        # Check for rapid successive logins
        if len(recent_logins) >= 2:
            time_diff = (attempt.timestamp - recent_logins[-1]).total_seconds()
            if time_diff < 60:  # Less than 1 minute
                risk_factors.append("rapid_successive_logins")
        
        return risk_factors
    
    def _is_suspicious_timing(self, email: str, timestamp: datetime) -> bool:
        """Check if login timing is suspicious (e.g., off-hours)."""
        hour = timestamp.hour
        
        # Define suspicious hours (e.g., 2 AM - 6 AM)
        if 2 <= hour <= 6:
            return True
        
        # Check if it's a weekend (simplified - in production you'd consider timezone)
        if timestamp.weekday() >= 5:  # Saturday or Sunday
            return True
        
        return False
    
    def _is_location_anomaly(self, user_id: str, ip_address: str) -> bool:
        """Check if login location is anomalous for the user."""
        try:
            # Get geographic location for IP (simplified)
            # In production, you'd use a GeoIP service
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Check if it's a private IP
            if ip_obj.is_private:
                return False
            
            # Simplified location check - in production use GeoIP database
            location = self._get_ip_location(ip_address)
            user_locations = self.user_locations[user_id]
            
            if location and location not in user_locations:
                # New location detected
                if len(user_locations) > 0:  # Not first login
                    return True
                
                # Add location to user's known locations
                user_locations.append(location)
                if len(user_locations) > 10:  # Limit stored locations
                    user_locations.pop(0)
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking location anomaly: {e}")
            return False
    
    def _is_device_anomaly(self, user_id: str, user_agent: str) -> bool:
        """Check if device/browser is anomalous for the user."""
        try:
            # Parse user agent
            parsed_ua = parse(user_agent)
            device_fingerprint = f"{parsed_ua.browser.family}_{parsed_ua.os.family}"
            
            user_devices = self.user_devices[user_id]
            
            if device_fingerprint not in user_devices:
                # New device detected
                if len(user_devices) > 0:  # Not first login
                    # Add device to user's known devices
                    user_devices.append(device_fingerprint)
                    if len(user_devices) > 5:  # Limit stored devices
                        user_devices.pop(0)
                    return True
                else:
                    # First login, add device
                    user_devices.append(device_fingerprint)
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking device anomaly: {e}")
            return False
    
    def _check_concurrent_sessions(self, user_id: str, ip_address: str) -> bool:
        """Check for suspicious concurrent sessions."""
        current_time = datetime.utcnow()
        user_sessions = [
            session for session in self.active_sessions.values()
            if (session.user_id == user_id and 
                (current_time - session.last_activity).total_seconds() < self.SESSION_TIMEOUT)
        ]
        
        # Check for sessions from different IPs
        different_ips = set(session.ip_address for session in user_sessions)
        if len(different_ips) > 1:
            return True
        
        # Check for too many concurrent sessions
        if len(user_sessions) >= self.MAX_CONCURRENT_SESSIONS:
            return True
        
        return False
    
    def _detect_credential_stuffing(self, attempt: AuthenticationAttempt) -> bool:
        """Detect credential stuffing attacks."""
        # Check for multiple different email attempts from same IP
        current_time = attempt.timestamp
        
        # Get all failed attempts from this IP in the last hour
        ip_failures = []
        for ip, failures in self.failed_attempts.items():
            if ip == attempt.ip_address:
                ip_failures.extend([
                    ts for ts in failures
                    if (current_time - ts).total_seconds() < 3600
                ])
        
        # If many failures from same IP, likely credential stuffing
        return len(ip_failures) > 20
    
    def _calculate_auth_risk_score(self, attempt: AuthenticationAttempt) -> int:
        """Calculate risk score for authentication attempt."""
        score = 0
        
        # Base score for failed attempts
        if not attempt.success:
            score += 30
        
        # Check IP reputation
        if self.security_monitor.threat_intel.is_malicious_ip(attempt.ip_address):
            score += 40
        
        if self.security_monitor.threat_intel.is_cloud_provider(attempt.ip_address):
            score += 15
        
        # Check user agent
        ua_lower = attempt.user_agent.lower()
        for suspicious_ua in ["bot", "crawler", "scanner", "curl", "wget"]:
            if suspicious_ua in ua_lower:
                score += 25
                break
        
        # Check for automation patterns
        if not attempt.user_agent or len(attempt.user_agent) < 10:
            score += 20
        
        # Check recent failure count from this IP
        recent_failures = [
            ts for ts in self.failed_attempts[attempt.ip_address]
            if (attempt.timestamp - ts).total_seconds() < self.FAILED_ATTEMPT_WINDOW
        ]
        score += min(len(recent_failures) * 5, 30)
        
        return min(score, 100)
    
    def _get_ip_location(self, ip_address: str) -> Optional[str]:
        """Get geographic location for IP address (simplified)."""
        # In production, use a proper GeoIP service like MaxMind
        # This is a simplified implementation
        try:
            # Basic IP range to location mapping (for demo)
            ip_obj = ipaddress.ip_address(ip_address)
            
            # US IP ranges (simplified)
            if ip_obj in ipaddress.ip_network("8.0.0.0/8"):
                return "US"
            if ip_obj in ipaddress.ip_network("24.0.0.0/8"):
                return "US"
            
            # European IP ranges (simplified)
            if ip_obj in ipaddress.ip_network("62.0.0.0/8"):
                return "EU"
            
            return "UNKNOWN"
            
        except Exception:
            return None
    
    def _update_user_tracking(self, user_id: str, ip_address: str, user_agent: str):
        """Update user tracking data."""
        try:
            # Update location tracking
            location = self._get_ip_location(ip_address)
            if location and location not in self.user_locations[user_id]:
                self.user_locations[user_id].append(location)
                if len(self.user_locations[user_id]) > 10:
                    self.user_locations[user_id].pop(0)
            
            # Update device tracking
            parsed_ua = parse(user_agent)
            device_fingerprint = f"{parsed_ua.browser.family}_{parsed_ua.os.family}"
            if device_fingerprint not in self.user_devices[user_id]:
                self.user_devices[user_id].append(device_fingerprint)
                if len(self.user_devices[user_id]) > 5:
                    self.user_devices[user_id].pop(0)
                    
        except Exception as e:
            logger.warning(f"Error updating user tracking: {e}")
    
    def _generate_session_id(self, user_id: str, ip_address: str) -> str:
        """Generate a session ID."""
        timestamp = str(time.time())
        data = f"{user_id}:{ip_address}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def update_session_activity(self, session_id: str):
        """Update session last activity timestamp."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].last_activity = datetime.utcnow()
    
    def is_session_suspicious(self, session_id: str) -> bool:
        """Check if a session is marked as suspicious."""
        session = self.active_sessions.get(session_id)
        return session.is_suspicious if session else False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        current_time = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, session in self.active_sessions.items()
            if (current_time - session.last_activity).total_seconds() > self.SESSION_TIMEOUT
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        if expired_sessions:
            logfire.info(
                "Cleaned up expired sessions",
                count=len(expired_sessions)
            )
    
    def get_user_security_summary(self, user_id: str) -> Dict[str, Any]:
        """Get security summary for a user."""
        current_time = datetime.utcnow()
        
        # Get active sessions
        active_sessions = [
            {
                "session_id": session.session_id,
                "ip_address": session.ip_address,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_suspicious": session.is_suspicious,
                "risk_factors": session.risk_factors
            }
            for session in self.active_sessions.values()
            if (session.user_id == user_id and 
                (current_time - session.last_activity).total_seconds() < self.SESSION_TIMEOUT)
        ]
        
        return {
            "user_id": user_id,
            "active_sessions": active_sessions,
            "known_locations": self.user_locations.get(user_id, []),
            "known_devices": self.user_devices.get(user_id, []),
            "session_count": len(active_sessions),
            "suspicious_sessions": len([s for s in active_sessions if s["is_suspicious"]])
        }

# Global authentication security monitor
_auth_security_monitor = None

def get_auth_security_monitor() -> AuthenticationSecurityMonitor:
    """Get the global authentication security monitor instance."""
    global _auth_security_monitor
    DISABLE_SECURITY = os.getenv('DISABLE_SECURITY', 'false').lower() == 'true'
    if _auth_security_monitor is None and not DISABLE_SECURITY:
        _auth_security_monitor = AuthenticationSecurityMonitor()
    return _auth_security_monitor