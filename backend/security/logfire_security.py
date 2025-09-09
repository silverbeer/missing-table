"""
Advanced Security Metrics and Observability with Logfire
Centralized security monitoring, threat detection, and compliance tracking
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import logfire
import httpx
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
import redis
import asyncpg
from prometheus_client import Counter, Histogram, Gauge

# Configure Logfire for security monitoring
logfire.configure(
    service_name="missing-table-security",
    service_version="1.0.0",
    environment="production",
    console={"colors": "always"},
    pydantic_plugin=logfire.PydanticPlugin(record="all"),
)

# Security metrics
SECURITY_EVENTS_TOTAL = Counter(
    'security_events_total',
    'Total number of security events',
    ['event_type', 'severity', 'source']
)

THREAT_DETECTION_LATENCY = Histogram(
    'threat_detection_latency_seconds',
    'Time taken to detect threats',
    ['detection_method']
)

COMPLIANCE_SCORE = Gauge(
    'compliance_score_percentage',
    'Current compliance score percentage',
    ['framework']
)

VULNERABILITY_COUNT = Gauge(
    'vulnerability_count',
    'Number of active vulnerabilities',
    ['severity', 'component']
)

USER_BEHAVIOR_ANOMALIES = Counter(
    'user_behavior_anomalies_total',
    'Number of user behavior anomalies detected',
    ['user_id', 'anomaly_type']
)

class SecurityEventType(str, Enum):
    """Security event types for classification"""
    AUTHENTICATION_FAILURE = "auth_failure"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    MALWARE_DETECTION = "malware_detection"
    POLICY_VIOLATION = "policy_violation"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    NETWORK_INTRUSION = "network_intrusion"
    COMPLIANCE_VIOLATION = "compliance_violation"
    VULNERABILITY_EXPLOITATION = "vulnerability_exploitation"

class SeverityLevel(str, Enum):
    """Security event severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_id: str
    event_type: SecurityEventType
    severity: SeverityLevel
    timestamp: datetime
    source: str
    description: str
    user_id: Optional[str] = None
    resource: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    remediation_status: str = "pending"
    correlation_id: Optional[str] = None

@dataclass
class UserBehaviorMetrics:
    """User behavior analytics data"""
    user_id: str
    timestamp: datetime
    login_frequency: float
    access_patterns: List[str]
    data_access_volume: float
    unusual_hours: bool
    failed_attempts: int
    privilege_usage: List[str]
    network_locations: List[str]
    device_fingerprints: List[str]

@dataclass
class NetworkTrafficMetrics:
    """Network traffic analysis data"""
    timestamp: datetime
    source_ip: str
    destination_ip: str
    protocol: str
    port: int
    bytes_transferred: int
    packet_count: int
    connection_duration: float
    threat_indicators: List[str]
    geo_location: Optional[str] = None

@dataclass
class VulnerabilityMetrics:
    """Vulnerability tracking data"""
    vuln_id: str
    cve_id: Optional[str]
    severity: SeverityLevel
    component: str
    discovered_date: datetime
    remediation_date: Optional[datetime]
    status: str
    exploitability_score: float
    business_impact: str

class SecurityMetricsCollector:
    """Centralized security metrics collection and analysis"""
    
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.db_pool = None
        self.ml_models = {}
        self.scaler = StandardScaler()
        self._initialize_ml_models()
    
    async def initialize_db(self):
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/security_metrics",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
    
    async def _create_tables(self):
        """Create security metrics tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    event_id VARCHAR PRIMARY KEY,
                    event_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    source VARCHAR NOT NULL,
                    description TEXT,
                    user_id VARCHAR,
                    resource VARCHAR,
                    metadata JSONB,
                    remediation_status VARCHAR DEFAULT 'pending',
                    correlation_id VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS user_behavior (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    metrics JSONB NOT NULL,
                    anomaly_score FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_traffic (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    source_ip INET NOT NULL,
                    destination_ip INET NOT NULL,
                    protocol VARCHAR NOT NULL,
                    port INTEGER NOT NULL,
                    bytes_transferred BIGINT,
                    packet_count INTEGER,
                    connection_duration FLOAT,
                    threat_indicators JSONB,
                    geo_location VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS vulnerabilities (
                    vuln_id VARCHAR PRIMARY KEY,
                    cve_id VARCHAR,
                    severity VARCHAR NOT NULL,
                    component VARCHAR NOT NULL,
                    discovered_date TIMESTAMP NOT NULL,
                    remediation_date TIMESTAMP,
                    status VARCHAR NOT NULL,
                    exploitability_score FLOAT,
                    business_impact VARCHAR,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity);
                CREATE INDEX IF NOT EXISTS idx_user_behavior_user_id ON user_behavior(user_id);
                CREATE INDEX IF NOT EXISTS idx_network_traffic_timestamp ON network_traffic(timestamp);
                CREATE INDEX IF NOT EXISTS idx_vulnerabilities_severity ON vulnerabilities(severity);
            """)
    
    def _initialize_ml_models(self):
        """Initialize machine learning models for anomaly detection"""
        # User behavior anomaly detection
        self.ml_models['user_behavior'] = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        
        # Network traffic anomaly detection
        self.ml_models['network_traffic'] = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=150
        )
    
    @logfire.instrument("Record Security Event")
    async def record_security_event(self, event: SecurityEvent):
        """Record a security event with Logfire instrumentation"""
        with logfire.span("security_event_processing"):
            # Record metrics
            SECURITY_EVENTS_TOTAL.labels(
                event_type=event.event_type.value,
                severity=event.severity.value,
                source=event.source
            ).inc()
            
            # Store in database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO security_events 
                    (event_id, event_type, severity, timestamp, source, description, 
                     user_id, resource, metadata, remediation_status, correlation_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, 
                    event.event_id, event.event_type.value, event.severity.value,
                    event.timestamp, event.source, event.description,
                    event.user_id, event.resource, json.dumps(event.metadata),
                    event.remediation_status, event.correlation_id
                )
            
            # Cache recent events for real-time analysis
            await self._cache_recent_event(event)
            
            # Log to Logfire with structured data
            logfire.info(
                "Security event recorded",
                event_id=event.event_id,
                event_type=event.event_type.value,
                severity=event.severity.value,
                source=event.source,
                user_id=event.user_id,
                resource=event.resource,
                metadata=event.metadata
            )
            
            # Trigger real-time analysis
            await self._analyze_security_event(event)
    
    @logfire.instrument("User Behavior Analysis")
    async def analyze_user_behavior(self, metrics: UserBehaviorMetrics):
        """Analyze user behavior for anomalies using ML"""
        with logfire.span("user_behavior_analysis"):
            # Extract features for ML analysis
            features = [
                metrics.login_frequency,
                len(metrics.access_patterns),
                metrics.data_access_volume,
                int(metrics.unusual_hours),
                metrics.failed_attempts,
                len(metrics.privilege_usage),
                len(metrics.network_locations),
                len(metrics.device_fingerprints)
            ]
            
            # Predict anomaly
            anomaly_score = self.ml_models['user_behavior'].decision_function([features])[0]
            is_anomaly = self.ml_models['user_behavior'].predict([features])[0] == -1
            
            # Store behavior data
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_behavior (user_id, timestamp, metrics, anomaly_score)
                    VALUES ($1, $2, $3, $4)
                """, 
                    metrics.user_id, metrics.timestamp, 
                    json.dumps(asdict(metrics)), anomaly_score
                )
            
            if is_anomaly:
                # Record anomaly metrics
                USER_BEHAVIOR_ANOMALIES.labels(
                    user_id=metrics.user_id,
                    anomaly_type="behavioral_anomaly"
                ).inc()
                
                # Create security event for anomaly
                await self.record_security_event(SecurityEvent(
                    event_id=f"anomaly_{int(time.time())}_{metrics.user_id}",
                    event_type=SecurityEventType.ANOMALOUS_BEHAVIOR,
                    severity=SeverityLevel.MEDIUM,
                    timestamp=metrics.timestamp,
                    source="ml_behavior_analysis",
                    description=f"Anomalous behavior detected for user {metrics.user_id}",
                    user_id=metrics.user_id,
                    metadata={
                        "anomaly_score": float(anomaly_score),
                        "features": features,
                        "behavior_metrics": asdict(metrics)
                    }
                ))
                
                logfire.warn(
                    "User behavior anomaly detected",
                    user_id=metrics.user_id,
                    anomaly_score=float(anomaly_score),
                    metrics=asdict(metrics)
                )
            
            return {
                "user_id": metrics.user_id,
                "anomaly_score": float(anomaly_score),
                "is_anomaly": is_anomaly,
                "timestamp": metrics.timestamp.isoformat()
            }
    
    @logfire.instrument("Network Traffic Analysis")
    async def analyze_network_traffic(self, traffic: NetworkTrafficMetrics):
        """Analyze network traffic for intrusion detection"""
        with logfire.span("network_traffic_analysis"):
            # Extract features for analysis
            features = [
                traffic.port,
                traffic.bytes_transferred,
                traffic.packet_count,
                traffic.connection_duration,
                len(traffic.threat_indicators)
            ]
            
            # Predict anomaly
            anomaly_score = self.ml_models['network_traffic'].decision_function([features])[0]
            is_anomaly = self.ml_models['network_traffic'].predict([features])[0] == -1
            
            # Store traffic data
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO network_traffic 
                    (timestamp, source_ip, destination_ip, protocol, port, 
                     bytes_transferred, packet_count, connection_duration, 
                     threat_indicators, geo_location)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, 
                    traffic.timestamp, traffic.source_ip, traffic.destination_ip,
                    traffic.protocol, traffic.port, traffic.bytes_transferred,
                    traffic.packet_count, traffic.connection_duration,
                    json.dumps(traffic.threat_indicators), traffic.geo_location
                )
            
            # Check for known threat indicators
            threat_detected = len(traffic.threat_indicators) > 0
            
            if is_anomaly or threat_detected:
                severity = SeverityLevel.HIGH if threat_detected else SeverityLevel.MEDIUM
                
                await self.record_security_event(SecurityEvent(
                    event_id=f"network_{int(time.time())}_{hash(traffic.source_ip)}",
                    event_type=SecurityEventType.NETWORK_INTRUSION,
                    severity=severity,
                    timestamp=traffic.timestamp,
                    source="network_traffic_analysis",
                    description=f"Suspicious network traffic from {traffic.source_ip}",
                    metadata={
                        "anomaly_score": float(anomaly_score),
                        "threat_indicators": traffic.threat_indicators,
                        "traffic_metrics": asdict(traffic)
                    }
                ))
                
                logfire.warn(
                    "Network intrusion detected",
                    source_ip=traffic.source_ip,
                    destination_ip=traffic.destination_ip,
                    anomaly_score=float(anomaly_score),
                    threat_indicators=traffic.threat_indicators
                )
    
    @logfire.instrument("Vulnerability Tracking")
    async def track_vulnerability(self, vuln: VulnerabilityMetrics):
        """Track vulnerability lifecycle and remediation"""
        with logfire.span("vulnerability_tracking"):
            # Update vulnerability metrics
            VULNERABILITY_COUNT.labels(
                severity=vuln.severity.value,
                component=vuln.component
            ).inc()
            
            # Store vulnerability data
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO vulnerabilities 
                    (vuln_id, cve_id, severity, component, discovered_date, 
                     remediation_date, status, exploitability_score, business_impact)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (vuln_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        remediation_date = EXCLUDED.remediation_date
                """, 
                    vuln.vuln_id, vuln.cve_id, vuln.severity.value,
                    vuln.component, vuln.discovered_date, vuln.remediation_date,
                    vuln.status, vuln.exploitability_score, vuln.business_impact
                )
            
            logfire.info(
                "Vulnerability tracked",
                vuln_id=vuln.vuln_id,
                cve_id=vuln.cve_id,
                severity=vuln.severity.value,
                component=vuln.component,
                status=vuln.status
            )
    
    @logfire.instrument("Compliance Score Calculation")
    async def calculate_compliance_scores(self) -> Dict[str, float]:
        """Calculate compliance scores for different frameworks"""
        with logfire.span("compliance_calculation"):
            scores = {}
            frameworks = ["soc2", "cis_k8s", "nist", "pci_dss"]
            
            for framework in frameworks:
                # Get recent compliance events
                async with self.db_pool.acquire() as conn:
                    violations = await conn.fetchval("""
                        SELECT COUNT(*) FROM security_events 
                        WHERE event_type = 'compliance_violation'
                        AND metadata->>'framework' = $1
                        AND timestamp > NOW() - INTERVAL '24 hours'
                    """, framework)
                    
                    total_checks = await conn.fetchval("""
                        SELECT COUNT(*) FROM security_events 
                        WHERE source LIKE '%compliance%'
                        AND metadata->>'framework' = $1
                        AND timestamp > NOW() - INTERVAL '24 hours'
                    """, framework)
                
                # Calculate compliance score
                if total_checks > 0:
                    score = max(0, (total_checks - violations) / total_checks * 100)
                else:
                    score = 100.0  # No checks means no violations
                
                scores[framework] = score
                
                # Update metrics
                COMPLIANCE_SCORE.labels(framework=framework).set(score)
            
            logfire.info(
                "Compliance scores calculated",
                scores=scores
            )
            
            return scores
    
    async def _cache_recent_event(self, event: SecurityEvent):
        """Cache recent events for real-time analysis"""
        key = f"recent_events:{event.event_type.value}"
        await self.redis_client.lpush(key, json.dumps(asdict(event), default=str))
        await self.redis_client.ltrim(key, 0, 99)  # Keep last 100 events
        await self.redis_client.expire(key, 3600)  # Expire after 1 hour
    
    async def _analyze_security_event(self, event: SecurityEvent):
        """Perform real-time analysis on security events"""
        # Check for correlation with recent events
        correlations = await self._find_event_correlations(event)
        
        if correlations:
            logfire.warn(
                "Correlated security events detected",
                event_id=event.event_id,
                correlations=correlations
            )
    
    async def _find_event_correlations(self, event: SecurityEvent) -> List[str]:
        """Find correlations between security events"""
        correlations = []
        
        # Check for similar events from same user/source
        if event.user_id:
            key = f"recent_events:{event.event_type.value}"
            recent_events = await self.redis_client.lrange(key, 0, -1)
            
            for event_data in recent_events:
                recent_event = json.loads(event_data)
                if (recent_event.get('user_id') == event.user_id and 
                    recent_event.get('event_id') != event.event_id):
                    correlations.append(recent_event['event_id'])
        
        return correlations

# Global security metrics collector instance
security_metrics = SecurityMetricsCollector()

class SecurityMetricsAPI:
    """FastAPI endpoints for security metrics"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.security = HTTPBearer()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/api/security/events")
        async def record_event(event_data: dict):
            """Record a security event"""
            event = SecurityEvent(**event_data)
            await security_metrics.record_security_event(event)
            return {"status": "recorded", "event_id": event.event_id}
        
        @self.app.post("/api/security/behavior")
        async def analyze_behavior(behavior_data: dict):
            """Analyze user behavior"""
            metrics = UserBehaviorMetrics(**behavior_data)
            result = await security_metrics.analyze_user_behavior(metrics)
            return result
        
        @self.app.post("/api/security/network")
        async def analyze_network(traffic_data: dict):
            """Analyze network traffic"""
            traffic = NetworkTrafficMetrics(**traffic_data)
            await security_metrics.analyze_network_traffic(traffic)
            return {"status": "analyzed"}
        
        @self.app.get("/api/security/compliance")
        async def get_compliance_scores():
            """Get compliance scores"""
            scores = await security_metrics.calculate_compliance_scores()
            return {"compliance_scores": scores}

# Initialize on startup
async def initialize_security_metrics():
    """Initialize security metrics system"""
    await security_metrics.initialize_db()
    logfire.info("Security metrics system initialized")