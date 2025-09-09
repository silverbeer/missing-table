# -*- coding: utf-8 -*-
"""
DAO Security Wrapper

This module provides a security wrapper for database access operations,
monitoring queries for SQL injection attempts and other security threats.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union
from functools import wraps
from datetime import datetime

import logfire
from opentelemetry import trace

from security_monitoring import get_security_monitor, SecurityEvent, SecurityEventType, SecuritySeverity
from security_middleware import get_db_query_monitor

logger = logging.getLogger(__name__)

class SecureDAO:
    """Security wrapper for DAO operations."""
    
    def __init__(self, dao_instance):
        self.dao = dao_instance
        self.security_monitor = get_security_monitor()
        self.db_query_monitor = get_db_query_monitor()
        self.tracer = trace.get_tracer(__name__)
    
    def _monitor_query(self, operation: str, query: str = None, params: Any = None, client_ip: str = "unknown"):
        """Monitor database query for security threats."""
        with self.tracer.start_as_current_span("database_operation") as span:
            span.set_attribute("db.operation", operation)
            span.set_attribute("db.client_ip", client_ip)
            
            if query:
                span.set_attribute("db.statement", query)
                # Monitor the query for SQL injection
                self.db_query_monitor.monitor_query(query, params, client_ip)
            
            # Log database operation
            logfire.debug(
                "Database operation executed",
                operation=operation,
                client_ip=client_ip,
                has_query=bool(query)
            )
    
    def _detect_suspicious_patterns(self, operation: str, params: Any = None) -> bool:
        """Detect suspicious patterns in database operations."""
        if not params:
            return False
        
        # Convert params to string for analysis
        if isinstance(params, dict):
            param_str = str(params.values())
        elif isinstance(params, (list, tuple)):
            param_str = str(params)
        else:
            param_str = str(params)
        
        # Check for SQL injection patterns
        if self.security_monitor.detect_sql_injection(param_str):
            return True
        
        # Check for suspicious data exfiltration patterns
        if operation.lower() in ['select', 'get'] and len(param_str) > 10000:
            return True
        
        return False
    
    def secure_execute(self, operation: str, method_name: str, *args, **kwargs):
        """Securely execute a DAO method with monitoring."""
        start_time = time.time()
        client_ip = kwargs.pop('_client_ip', 'unknown')
        
        with self.tracer.start_as_current_span(f"dao_{method_name}") as span:
            span.set_attribute("dao.method", method_name)
            span.set_attribute("dao.operation", operation)
            span.set_attribute("dao.client_ip", client_ip)
            
            try:
                # Check for suspicious patterns in parameters
                if self._detect_suspicious_patterns(operation, kwargs):
                    self.security_monitor.log_security_event(SecurityEvent(
                        event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                        severity=SecuritySeverity.CRITICAL,
                        source_ip=client_ip,
                        user_agent="dao_operation",
                        timestamp=datetime.utcnow(),
                        additional_context={
                            "operation": operation,
                            "method": method_name,
                            "params": str(kwargs)[:500]  # Truncate long params
                        }
                    ))
                    
                    span.set_status(trace.Status(trace.StatusCode.ERROR, "Suspicious database operation blocked"))
                    raise ValueError("Suspicious database operation detected")
                
                # Monitor the operation
                self._monitor_query(operation, client_ip=client_ip)
                
                # Execute the actual DAO method
                method = getattr(self.dao, method_name)
                result = method(*args, **kwargs)
                
                duration = time.time() - start_time
                span.set_attribute("dao.duration", duration)
                span.set_attribute("dao.success", True)
                
                # Log slow queries
                if duration > 5.0:  # 5 seconds
                    logfire.warn(
                        "Slow database query detected",
                        method=method_name,
                        operation=operation,
                        duration=duration,
                        client_ip=client_ip
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                span.set_attribute("dao.duration", duration)
                span.set_attribute("dao.success", False)
                span.set_attribute("dao.error", str(e))
                
                # Log database errors
                logfire.error(
                    "Database operation failed",
                    method=method_name,
                    operation=operation,
                    error=str(e),
                    duration=duration,
                    client_ip=client_ip
                )
                
                # Check if this might be an injection attempt that caused an error
                if any(keyword in str(e).lower() for keyword in ['syntax error', 'invalid', 'malformed']):
                    self.security_monitor.log_security_event(SecurityEvent(
                        event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                        severity=SecuritySeverity.HIGH,
                        source_ip=client_ip,
                        user_agent="dao_operation",
                        timestamp=datetime.utcnow(),
                        additional_context={
                            "operation": operation,
                            "method": method_name,
                            "error": str(e),
                            "reason": "database_error_suspicious"
                        }
                    ))
                
                raise
    
    # Wrap common DAO methods with security monitoring
    def get_all_games(self, client_ip: str = "unknown", **kwargs):
        """Get all games with security monitoring."""
        return self.secure_execute("SELECT", "get_all_games", _client_ip=client_ip, **kwargs)
    
    def get_all_teams(self, client_ip: str = "unknown", **kwargs):
        """Get all teams with security monitoring."""
        return self.secure_execute("SELECT", "get_all_teams", _client_ip=client_ip, **kwargs)
    
    def get_league_table(self, client_ip: str = "unknown", **kwargs):
        """Get league table with security monitoring."""
        return self.secure_execute("SELECT", "get_league_table", _client_ip=client_ip, **kwargs)
    
    def add_game(self, client_ip: str = "unknown", **kwargs):
        """Add game with security monitoring."""
        return self.secure_execute("INSERT", "add_game", _client_ip=client_ip, **kwargs)
    
    def update_game(self, client_ip: str = "unknown", **kwargs):
        """Update game with security monitoring."""
        return self.secure_execute("UPDATE", "update_game", _client_ip=client_ip, **kwargs)
    
    def delete_game(self, game_id: int, client_ip: str = "unknown"):
        """Delete game with security monitoring."""
        return self.secure_execute("DELETE", "delete_game", game_id, _client_ip=client_ip)
    
    def add_team(self, client_ip: str = "unknown", **kwargs):
        """Add team with security monitoring."""
        return self.secure_execute("INSERT", "add_team", _client_ip=client_ip, **kwargs)
    
    def get_games_by_team(self, team_id: int, client_ip: str = "unknown", **kwargs):
        """Get games by team with security monitoring."""
        return self.secure_execute("SELECT", "get_games_by_team", team_id, _client_ip=client_ip, **kwargs)
    
    # Reference data methods
    def get_all_age_groups(self, client_ip: str = "unknown"):
        """Get all age groups with security monitoring."""
        return self.secure_execute("SELECT", "get_all_age_groups", _client_ip=client_ip)
    
    def get_all_seasons(self, client_ip: str = "unknown"):
        """Get all seasons with security monitoring."""
        return self.secure_execute("SELECT", "get_all_seasons", _client_ip=client_ip)
    
    def get_current_season(self, client_ip: str = "unknown"):
        """Get current season with security monitoring."""
        return self.secure_execute("SELECT", "get_current_season", _client_ip=client_ip)
    
    def get_active_seasons(self, client_ip: str = "unknown"):
        """Get active seasons with security monitoring."""
        return self.secure_execute("SELECT", "get_active_seasons", _client_ip=client_ip)
    
    def get_all_game_types(self, client_ip: str = "unknown"):
        """Get all game types with security monitoring."""
        return self.secure_execute("SELECT", "get_all_game_types", _client_ip=client_ip)
    
    def get_all_divisions(self, client_ip: str = "unknown"):
        """Get all divisions with security monitoring."""
        return self.secure_execute("SELECT", "get_all_divisions", _client_ip=client_ip)
    
    # Admin CRUD methods
    def create_age_group(self, name: str, client_ip: str = "unknown"):
        """Create age group with security monitoring."""
        return self.secure_execute("INSERT", "create_age_group", name, _client_ip=client_ip)
    
    def update_age_group(self, age_group_id: int, name: str, client_ip: str = "unknown"):
        """Update age group with security monitoring."""
        return self.secure_execute("UPDATE", "update_age_group", age_group_id, name, _client_ip=client_ip)
    
    def delete_age_group(self, age_group_id: int, client_ip: str = "unknown"):
        """Delete age group with security monitoring."""
        return self.secure_execute("DELETE", "delete_age_group", age_group_id, _client_ip=client_ip)
    
    def create_season(self, name: str, start_date: str, end_date: str, client_ip: str = "unknown"):
        """Create season with security monitoring."""
        return self.secure_execute("INSERT", "create_season", name, start_date, end_date, _client_ip=client_ip)
    
    def update_season(self, season_id: int, name: str, start_date: str, end_date: str, client_ip: str = "unknown"):
        """Update season with security monitoring."""
        return self.secure_execute("UPDATE", "update_season", season_id, name, start_date, end_date, _client_ip=client_ip)
    
    def delete_season(self, season_id: int, client_ip: str = "unknown"):
        """Delete season with security monitoring."""
        return self.secure_execute("DELETE", "delete_season", season_id, _client_ip=client_ip)
    
    def create_division(self, name: str, description: Optional[str] = None, client_ip: str = "unknown"):
        """Create division with security monitoring."""
        return self.secure_execute("INSERT", "create_division", name, description, _client_ip=client_ip)
    
    def update_division(self, division_id: int, name: str, description: Optional[str] = None, client_ip: str = "unknown"):
        """Update division with security monitoring."""
        return self.secure_execute("UPDATE", "update_division", division_id, name, description, _client_ip=client_ip)
    
    def delete_division(self, division_id: int, client_ip: str = "unknown"):
        """Delete division with security monitoring."""
        return self.secure_execute("DELETE", "delete_division", division_id, _client_ip=client_ip)
    
    def update_team(self, team_id: int, name: str, city: str, academy_team: bool = False, client_ip: str = "unknown"):
        """Update team with security monitoring."""
        return self.secure_execute("UPDATE", "update_team", team_id, name, city, academy_team, _client_ip=client_ip)
    
    def delete_team(self, team_id: int, client_ip: str = "unknown"):
        """Delete team with security monitoring."""
        return self.secure_execute("DELETE", "delete_team", team_id, _client_ip=client_ip)
    
    # Pass-through methods for methods that don't need special monitoring
    def __getattr__(self, name):
        """Pass through to the wrapped DAO for methods not explicitly wrapped."""
        if hasattr(self.dao, name):
            attr = getattr(self.dao, name)
            if callable(attr):
                # Wrap callable methods with basic monitoring
                @wraps(attr)
                def wrapper(*args, **kwargs):
                    client_ip = kwargs.pop('_client_ip', 'unknown')
                    with self.tracer.start_as_current_span(f"dao_{name}") as span:
                        span.set_attribute("dao.method", name)
                        span.set_attribute("dao.client_ip", client_ip)
                        
                        try:
                            result = attr(*args, **kwargs)
                            span.set_attribute("dao.success", True)
                            return result
                        except Exception as e:
                            span.set_attribute("dao.success", False)
                            span.set_attribute("dao.error", str(e))
                            
                            logfire.error(
                                "DAO method failed",
                                method=name,
                                error=str(e),
                                client_ip=client_ip
                            )
                            raise
                
                return wrapper
            else:
                return attr
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

def create_secure_dao(dao_instance):
    """Create a secure wrapper around a DAO instance."""
    return SecureDAO(dao_instance)