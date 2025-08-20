"""
Advanced Security Incident Correlation and Analysis System
ML-powered incident correlation, threat intelligence, and automated analysis
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logfire
from prometheus_client import Counter, Histogram, Gauge
import redis
import networkx as nx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Prometheus metrics
INCIDENT_CORRELATIONS_TOTAL = Counter(
    'incident_correlations_total',
    'Total number of incident correlations found',
    ['correlation_type', 'confidence_level']
)

CORRELATION_PROCESSING_TIME = Histogram(
    'correlation_processing_seconds',
    'Time taken to process incident correlations',
    ['analysis_type']
)

THREAT_ACTOR_ACTIVITIES = Gauge(
    'threat_actor_activities_total',
    'Number of activities attributed to threat actors',
    ['actor_group', 'technique']
)

ATTACK_CHAIN_LENGTH = Histogram(
    'attack_chain_length',
    'Length of detected attack chains',
    ['attack_type']
)

class CorrelationType(str, Enum):
    """Types of incident correlations"""
    TEMPORAL = "temporal"           # Time-based correlation
    SPATIAL = "spatial"             # Location/network-based
    BEHAVIORAL = "behavioral"       # Behavior pattern similarity
    ARTIFACT = "artifact"           # Common IOCs/artifacts
    CAMPAIGN = "campaign"           # Part of same attack campaign
    INFRASTRUCTURE = "infrastructure" # Shared attack infrastructure
    TTP = "ttp"                    # Tactics, Techniques, Procedures

class ConfidenceLevel(str, Enum):
    """Confidence levels for correlations"""
    HIGH = "high"       # 80-100%
    MEDIUM = "medium"   # 60-79%
    LOW = "low"         # 40-59%
    WEAK = "weak"       # 20-39%

class ThreatLevel(str, Enum):
    """Threat level assessment"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class IncidentEvent:
    """Individual security incident event"""
    event_id: str
    timestamp: datetime
    event_type: str
    source_ip: Optional[str]
    destination_ip: Optional[str]
    user_id: Optional[str]
    process_name: Optional[str]
    command_line: Optional[str]
    file_path: Optional[str]
    registry_key: Optional[str]
    network_protocol: Optional[str]
    port: Optional[int]
    indicators: List[str]
    metadata: Dict[str, Any]
    severity: str
    raw_log: str

@dataclass
class IncidentCorrelation:
    """Correlation between security incidents"""
    correlation_id: str
    incident_ids: List[str]
    correlation_type: CorrelationType
    confidence_score: float
    confidence_level: ConfidenceLevel
    correlation_factors: List[str]
    timeline_analysis: Dict[str, Any]
    threat_assessment: Dict[str, Any]
    recommended_actions: List[str]
    created_at: datetime

@dataclass
class AttackChain:
    """Detected attack chain/kill chain"""
    chain_id: str
    incident_ids: List[str]
    attack_stages: List[Dict[str, Any]]
    techniques_used: List[str]
    threat_actor_attribution: Optional[str]
    timeline: List[Dict[str, Any]]
    attack_objective: str
    impact_assessment: str
    mitigation_recommendations: List[str]

@dataclass
class ThreatIntelligence:
    """Threat intelligence data"""
    ioc_value: str
    ioc_type: str  # ip, domain, hash, etc.
    threat_type: str
    threat_actor: Optional[str]
    campaign: Optional[str]
    confidence: float
    first_seen: datetime
    last_seen: datetime
    sources: List[str]
    context: Dict[str, Any]

class IncidentCorrelationEngine:
    """Advanced incident correlation and analysis engine"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=3)
        self.correlation_graph = nx.Graph()
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.scaler = StandardScaler()
        self.threat_intel_sources = []
        self.mitre_techniques = {}
        
    async def initialize(self):
        """Initialize correlation engine"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/incident_correlation",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_threat_intelligence()
        await self._load_mitre_attack_framework()
        
        logfire.info("Incident correlation engine initialized")
    
    async def _create_tables(self):
        """Create incident correlation database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS incident_events (
                    event_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    event_type VARCHAR NOT NULL,
                    source_ip INET,
                    destination_ip INET,
                    user_id VARCHAR,
                    process_name VARCHAR,
                    command_line TEXT,
                    file_path VARCHAR,
                    registry_key VARCHAR,
                    network_protocol VARCHAR,
                    port INTEGER,
                    indicators JSONB,
                    metadata JSONB,
                    severity VARCHAR,
                    raw_log TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS incident_correlations (
                    correlation_id VARCHAR PRIMARY KEY,
                    incident_ids JSONB NOT NULL,
                    correlation_type VARCHAR NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    confidence_level VARCHAR NOT NULL,
                    correlation_factors JSONB,
                    timeline_analysis JSONB,
                    threat_assessment JSONB,
                    recommended_actions JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS attack_chains (
                    chain_id VARCHAR PRIMARY KEY,
                    incident_ids JSONB NOT NULL,
                    attack_stages JSONB,
                    techniques_used JSONB,
                    threat_actor_attribution VARCHAR,
                    timeline JSONB,
                    attack_objective TEXT,
                    impact_assessment TEXT,
                    mitigation_recommendations JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS threat_intelligence (
                    ioc_id VARCHAR PRIMARY KEY,
                    ioc_value VARCHAR NOT NULL,
                    ioc_type VARCHAR NOT NULL,
                    threat_type VARCHAR,
                    threat_actor VARCHAR,
                    campaign VARCHAR,
                    confidence FLOAT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    sources JSONB,
                    context JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS correlation_patterns (
                    pattern_id VARCHAR PRIMARY KEY,
                    pattern_name VARCHAR NOT NULL,
                    pattern_type VARCHAR NOT NULL,
                    description TEXT,
                    detection_rules JSONB,
                    confidence_weight FLOAT DEFAULT 1.0,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_incident_events_timestamp ON incident_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_incident_events_type ON incident_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_incident_events_source_ip ON incident_events(source_ip);
                CREATE INDEX IF NOT EXISTS idx_incident_events_user_id ON incident_events(user_id);
                CREATE INDEX IF NOT EXISTS idx_correlations_type ON incident_correlations(correlation_type);
                CREATE INDEX IF NOT EXISTS idx_correlations_confidence ON incident_correlations(confidence_score);
                CREATE INDEX IF NOT EXISTS idx_threat_intel_ioc ON threat_intelligence(ioc_value);
                CREATE INDEX IF NOT EXISTS idx_threat_intel_type ON threat_intelligence(ioc_type);
            """)
    
    async def _load_threat_intelligence(self):
        """Load threat intelligence from various sources"""
        # Load from database
        async with self.db_pool.acquire() as conn:
            intel_data = await conn.fetch("SELECT * FROM threat_intelligence")
            
        # Cache in Redis for fast lookup
        for intel in intel_data:
            key = f"threat_intel:{intel['ioc_type']}:{intel['ioc_value']}"
            await self.redis_client.setex(
                key, 
                3600,  # 1 hour TTL
                json.dumps(dict(intel), default=str)
            )
    
    async def _load_mitre_attack_framework(self):
        """Load MITRE ATT&CK framework data"""
        # Mock MITRE techniques - in production would load from MITRE API
        self.mitre_techniques = {
            "T1055": {
                "name": "Process Injection",
                "tactic": "Defense Evasion",
                "description": "Adversaries may inject code into processes",
                "detection": ["process_creation", "memory_allocation"]
            },
            "T1021": {
                "name": "Remote Services",
                "tactic": "Lateral Movement",
                "description": "Adversaries may use remote services to move laterally",
                "detection": ["network_connection", "authentication"]
            },
            "T1059": {
                "name": "Command and Scripting Interpreter",
                "tactic": "Execution",
                "description": "Adversaries may execute commands",
                "detection": ["process_creation", "command_line"]
            }
        }
    
    @logfire.instrument("Process Incident Event")
    async def process_incident_event(self, event: IncidentEvent) -> List[IncidentCorrelation]:
        """Process a new incident event and find correlations"""
        with logfire.span("incident_processing", event_id=event.event_id):
            # Store the event
            await self._store_incident_event(event)
            
            # Find correlations
            correlations = []
            
            # Temporal correlations
            temporal_corrs = await self._find_temporal_correlations(event)
            correlations.extend(temporal_corrs)
            
            # Behavioral correlations
            behavioral_corrs = await self._find_behavioral_correlations(event)
            correlations.extend(behavioral_corrs)
            
            # Artifact correlations
            artifact_corrs = await self._find_artifact_correlations(event)
            correlations.extend(artifact_corrs)
            
            # Infrastructure correlations
            infra_corrs = await self._find_infrastructure_correlations(event)
            correlations.extend(infra_corrs)
            
            # Store correlations
            for correlation in correlations:
                await self._store_correlation(correlation)
            
            # Update correlation graph
            await self._update_correlation_graph(event, correlations)
            
            # Check for attack chains
            attack_chains = await self._detect_attack_chains(event, correlations)
            
            # Update metrics
            for correlation in correlations:
                INCIDENT_CORRELATIONS_TOTAL.labels(
                    correlation_type=correlation.correlation_type.value,
                    confidence_level=correlation.confidence_level.value
                ).inc()
            
            logfire.info(
                "Incident event processed",
                event_id=event.event_id,
                correlations_found=len(correlations),
                attack_chains=len(attack_chains)
            )
            
            return correlations
    
    async def _store_incident_event(self, event: IncidentEvent):
        """Store incident event in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO incident_events 
                (event_id, timestamp, event_type, source_ip, destination_ip,
                 user_id, process_name, command_line, file_path, registry_key,
                 network_protocol, port, indicators, metadata, severity, raw_log)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            """, 
                event.event_id, event.timestamp, event.event_type,
                event.source_ip, event.destination_ip, event.user_id,
                event.process_name, event.command_line, event.file_path,
                event.registry_key, event.network_protocol, event.port,
                json.dumps(event.indicators), json.dumps(event.metadata),
                event.severity, event.raw_log
            )
    
    async def _find_temporal_correlations(self, event: IncidentEvent) -> List[IncidentCorrelation]:
        """Find temporal correlations with recent events"""
        correlations = []
        
        # Look for events within time window
        time_window = timedelta(minutes=30)
        start_time = event.timestamp - time_window
        end_time = event.timestamp + time_window
        
        async with self.db_pool.acquire() as conn:
            related_events = await conn.fetch("""
                SELECT * FROM incident_events 
                WHERE timestamp BETWEEN $1 AND $2
                AND event_id != $3
                AND (
                    source_ip = $4 OR destination_ip = $4 OR
                    user_id = $5 OR
                    process_name = $6
                )
                ORDER BY timestamp
            """, start_time, end_time, event.event_id, 
                event.source_ip, event.user_id, event.process_name)
        
        if len(related_events) >= 2:  # Minimum threshold for correlation
            # Calculate confidence based on temporal proximity and common attributes
            confidence_score = self._calculate_temporal_confidence(event, related_events)
            
            if confidence_score >= 0.4:  # Minimum confidence threshold
                correlation = IncidentCorrelation(
                    correlation_id=f"temporal_{event.event_id}_{int(event.timestamp.timestamp())}",
                    incident_ids=[event.event_id] + [e['event_id'] for e in related_events],
                    correlation_type=CorrelationType.TEMPORAL,
                    confidence_score=confidence_score,
                    confidence_level=self._get_confidence_level(confidence_score),
                    correlation_factors=[
                        "temporal_proximity",
                        "common_source_ip" if any(e['source_ip'] == event.source_ip for e in related_events) else None,
                        "common_user" if any(e['user_id'] == event.user_id for e in related_events) else None
                    ],
                    timeline_analysis={
                        "time_window_minutes": 30,
                        "event_sequence": [
                            {"event_id": e['event_id'], "timestamp": e['timestamp'].isoformat()}
                            for e in related_events
                        ]
                    },
                    threat_assessment=await self._assess_threat_level([event] + related_events),
                    recommended_actions=["investigate_user_activity", "check_lateral_movement"],
                    created_at=datetime.now()
                )
                correlations.append(correlation)
        
        return correlations
    
    def _calculate_temporal_confidence(self, event: IncidentEvent, related_events: List[Any]) -> float:
        """Calculate confidence score for temporal correlation"""
        base_score = 0.3  # Base confidence for temporal proximity
        
        # Boost for common attributes
        for related_event in related_events:
            if related_event['source_ip'] == event.source_ip:
                base_score += 0.2
            if related_event['user_id'] == event.user_id:
                base_score += 0.2
            if related_event['process_name'] == event.process_name:
                base_score += 0.1
        
        # Boost for escalating severity
        severities = ['low', 'medium', 'high', 'critical']
        if event.severity in severities:
            event_severity_idx = severities.index(event.severity)
            for related_event in related_events:
                if (related_event['severity'] in severities and 
                    severities.index(related_event['severity']) < event_severity_idx):
                    base_score += 0.1
                    break
        
        return min(1.0, base_score)
    
    async def _find_behavioral_correlations(self, event: IncidentEvent) -> List[IncidentCorrelation]:
        """Find behavioral pattern correlations"""
        correlations = []
        
        # Look for similar behavior patterns
        if event.command_line or event.process_name:
            async with self.db_pool.acquire() as conn:
                # Find events with similar command patterns
                similar_events = await conn.fetch("""
                    SELECT * FROM incident_events 
                    WHERE (
                        similarity(command_line, $1) > 0.7 OR
                        similarity(process_name, $2) > 0.8
                    )
                    AND event_id != $3
                    AND timestamp > NOW() - INTERVAL '24 hours'
                    LIMIT 20
                """, event.command_line or '', event.process_name or '', event.event_id)
            
            if similar_events:
                # Use TF-IDF for command line similarity
                command_lines = [event.command_line or ''] + [e['command_line'] or '' for e in similar_events]
                
                try:
                    tfidf_matrix = self.tfidf_vectorizer.fit_transform(command_lines)
                    similarity_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
                    
                    # Find highly similar events
                    high_similarity_indices = np.where(similarity_scores > 0.7)[0]
                    
                    if len(high_similarity_indices) > 0:
                        confidence_score = np.mean(similarity_scores[high_similarity_indices])
                        
                        correlation = IncidentCorrelation(
                            correlation_id=f"behavioral_{event.event_id}_{int(event.timestamp.timestamp())}",
                            incident_ids=[event.event_id] + [similar_events[i]['event_id'] for i in high_similarity_indices],
                            correlation_type=CorrelationType.BEHAVIORAL,
                            confidence_score=float(confidence_score),
                            confidence_level=self._get_confidence_level(confidence_score),
                            correlation_factors=["command_line_similarity", "process_pattern_match"],
                            timeline_analysis={
                                "pattern_type": "command_execution",
                                "similarity_scores": similarity_scores[high_similarity_indices].tolist()
                            },
                            threat_assessment=await self._assess_threat_level([event] + [similar_events[i] for i in high_similarity_indices]),
                            recommended_actions=["analyze_command_patterns", "check_malware_signatures"],
                            created_at=datetime.now()
                        )
                        correlations.append(correlation)
                
                except Exception as e:
                    logger.error(f"Error in behavioral correlation analysis: {e}")
        
        return correlations
    
    async def _find_artifact_correlations(self, event: IncidentEvent) -> List[IncidentCorrelation]:
        """Find correlations based on common artifacts (IOCs)"""
        correlations = []
        
        # Extract IOCs from event
        iocs = await self._extract_iocs(event)
        
        if iocs:
            async with self.db_pool.acquire() as conn:
                # Find events with common IOCs
                for ioc in iocs:
                    related_events = await conn.fetch("""
                        SELECT * FROM incident_events 
                        WHERE indicators @> $1
                        AND event_id != $2
                        AND timestamp > NOW() - INTERVAL '7 days'
                    """, json.dumps([ioc]), event.event_id)
                    
                    if related_events:
                        # Check threat intelligence
                        threat_intel = await self._check_threat_intelligence(ioc)
                        
                        confidence_score = 0.6  # Base confidence for IOC match
                        if threat_intel:
                            confidence_score += 0.3  # Boost for known malicious IOC
                        
                        correlation = IncidentCorrelation(
                            correlation_id=f"artifact_{event.event_id}_{hashlib.md5(ioc.encode()).hexdigest()[:8]}",
                            incident_ids=[event.event_id] + [e['event_id'] for e in related_events],
                            correlation_type=CorrelationType.ARTIFACT,
                            confidence_score=confidence_score,
                            confidence_level=self._get_confidence_level(confidence_score),
                            correlation_factors=[f"common_ioc_{ioc}"],
                            timeline_analysis={
                                "ioc_value": ioc,
                                "threat_intelligence": threat_intel,
                                "ioc_frequency": len(related_events) + 1
                            },
                            threat_assessment=await self._assess_threat_level([event] + related_events),
                            recommended_actions=["block_ioc", "investigate_campaign"],
                            created_at=datetime.now()
                        )
                        correlations.append(correlation)
        
        return correlations
    
    async def _find_infrastructure_correlations(self, event: IncidentEvent) -> List[IncidentCorrelation]:
        """Find correlations based on shared infrastructure"""
        correlations = []
        
        if event.source_ip or event.destination_ip:
            async with self.db_pool.acquire() as conn:
                # Find events from same infrastructure
                related_events = await conn.fetch("""
                    SELECT * FROM incident_events 
                    WHERE (source_ip = $1 OR destination_ip = $1 OR 
                           source_ip = $2 OR destination_ip = $2)
                    AND event_id != $3
                    AND timestamp > NOW() - INTERVAL '24 hours'
                """, event.source_ip, event.destination_ip, event.event_id)
            
            if len(related_events) >= 2:
                confidence_score = min(0.8, 0.4 + (len(related_events) * 0.1))
                
                correlation = IncidentCorrelation(
                    correlation_id=f"infrastructure_{event.event_id}_{int(event.timestamp.timestamp())}",
                    incident_ids=[event.event_id] + [e['event_id'] for e in related_events],
                    correlation_type=CorrelationType.INFRASTRUCTURE,
                    confidence_score=confidence_score,
                    confidence_level=self._get_confidence_level(confidence_score),
                    correlation_factors=["shared_ip_infrastructure"],
                    timeline_analysis={
                        "infrastructure_ips": [event.source_ip, event.destination_ip],
                        "activity_frequency": len(related_events)
                    },
                    threat_assessment=await self._assess_threat_level([event] + related_events),
                    recommended_actions=["investigate_ip_reputation", "check_network_segmentation"],
                    created_at=datetime.now()
                )
                correlations.append(correlation)
        
        return correlations
    
    async def _extract_iocs(self, event: IncidentEvent) -> List[str]:
        """Extract Indicators of Compromise from event"""
        iocs = []
        
        # Add existing indicators
        iocs.extend(event.indicators)
        
        # Extract IPs
        if event.source_ip:
            iocs.append(event.source_ip)
        if event.destination_ip:
            iocs.append(event.destination_ip)
        
        # Extract file hashes from metadata
        if event.metadata:
            for key, value in event.metadata.items():
                if key.lower() in ['md5', 'sha1', 'sha256'] and isinstance(value, str):
                    iocs.append(value)
        
        return list(set(iocs))  # Remove duplicates
    
    async def _check_threat_intelligence(self, ioc: str) -> Optional[Dict[str, Any]]:
        """Check IOC against threat intelligence"""
        # Check Redis cache first
        cached_intel = await self.redis_client.get(f"threat_intel:*:{ioc}")
        if cached_intel:
            return json.loads(cached_intel)
        
        # Check database
        async with self.db_pool.acquire() as conn:
            intel = await conn.fetchrow("""
                SELECT * FROM threat_intelligence WHERE ioc_value = $1
            """, ioc)
            
            if intel:
                return dict(intel)
        
        return None
    
    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Convert confidence score to confidence level"""
        if score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.WEAK
    
    async def _assess_threat_level(self, events: List[Any]) -> Dict[str, Any]:
        """Assess overall threat level for correlated events"""
        severity_scores = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        max_severity = max(severity_scores.get(e.get('severity', 'low'), 1) for e in events)
        avg_severity = sum(severity_scores.get(e.get('severity', 'low'), 1) for e in events) / len(events)
        
        # Calculate threat score
        threat_score = (max_severity * 0.6 + avg_severity * 0.4) * 25  # Scale to 0-100
        
        if threat_score >= 75:
            threat_level = ThreatLevel.CRITICAL
        elif threat_score >= 60:
            threat_level = ThreatLevel.HIGH
        elif threat_score >= 40:
            threat_level = ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.LOW
        
        return {
            "threat_level": threat_level.value,
            "threat_score": round(threat_score, 2),
            "event_count": len(events),
            "max_severity": list(severity_scores.keys())[max_severity-1],
            "assessment_factors": [
                "event_severity",
                "correlation_patterns",
                "temporal_clustering"
            ]
        }
    
    async def _store_correlation(self, correlation: IncidentCorrelation):
        """Store correlation in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO incident_correlations 
                (correlation_id, incident_ids, correlation_type, confidence_score,
                 confidence_level, correlation_factors, timeline_analysis,
                 threat_assessment, recommended_actions)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                correlation.correlation_id, json.dumps(correlation.incident_ids),
                correlation.correlation_type.value, correlation.confidence_score,
                correlation.confidence_level.value, json.dumps(correlation.correlation_factors),
                json.dumps(correlation.timeline_analysis, default=str),
                json.dumps(correlation.threat_assessment),
                json.dumps(correlation.recommended_actions)
            )
    
    async def _update_correlation_graph(self, event: IncidentEvent, correlations: List[IncidentCorrelation]):
        """Update correlation graph for visualization"""
        # Add event as node
        self.correlation_graph.add_node(event.event_id, 
                                      timestamp=event.timestamp,
                                      event_type=event.event_type,
                                      severity=event.severity)
        
        # Add correlation edges
        for correlation in correlations:
            for incident_id in correlation.incident_ids:
                if incident_id != event.event_id:
                    self.correlation_graph.add_edge(
                        event.event_id, 
                        incident_id,
                        correlation_type=correlation.correlation_type.value,
                        confidence=correlation.confidence_score
                    )
    
    async def _detect_attack_chains(self, event: IncidentEvent, correlations: List[IncidentCorrelation]) -> List[AttackChain]:
        """Detect potential attack chains from correlations"""
        attack_chains = []
        
        # Look for sequences of events that form attack patterns
        if correlations:
            # Group correlated events by time
            all_incident_ids = set([event.event_id])
            for correlation in correlations:
                all_incident_ids.update(correlation.incident_ids)
            
            # Get all events in chronological order
            async with self.db_pool.acquire() as conn:
                chain_events = await conn.fetch("""
                    SELECT * FROM incident_events 
                    WHERE event_id = ANY($1)
                    ORDER BY timestamp ASC
                """, list(all_incident_ids))
            
            # Analyze for MITRE ATT&CK patterns
            attack_stages = self._analyze_attack_stages(chain_events)
            
            if len(attack_stages) >= 2:  # Minimum stages for attack chain
                chain = AttackChain(
                    chain_id=f"chain_{event.event_id}_{int(event.timestamp.timestamp())}",
                    incident_ids=list(all_incident_ids),
                    attack_stages=attack_stages,
                    techniques_used=self._identify_mitre_techniques(chain_events),
                    threat_actor_attribution=None,  # Would use attribution logic
                    timeline=[{
                        "event_id": e['event_id'],
                        "timestamp": e['timestamp'].isoformat(),
                        "stage": stage.get('stage', 'unknown')
                    } for e, stage in zip(chain_events, attack_stages)],
                    attack_objective="unknown",
                    impact_assessment="medium",
                    mitigation_recommendations=[
                        "implement_endpoint_detection",
                        "enhance_network_monitoring",
                        "update_incident_response_plan"
                    ]
                )
                attack_chains.append(chain)
                
                # Store attack chain
                await self._store_attack_chain(chain)
        
        return attack_chains
    
    def _analyze_attack_stages(self, events: List[Any]) -> List[Dict[str, Any]]:
        """Analyze events for attack stages (MITRE ATT&CK kill chain)"""
        stages = []
        
        for event in events:
            stage = {"event_id": event['event_id'], "stage": "unknown"}
            
            # Simple stage detection based on event characteristics
            if event['event_type'] in ['process_creation', 'file_execution']:
                stage['stage'] = 'execution'
            elif event['event_type'] in ['network_connection', 'dns_query']:
                stage['stage'] = 'command_and_control'
            elif event['event_type'] in ['file_access', 'registry_modification']:
                stage['stage'] = 'persistence'
            elif event['event_type'] in ['privilege_escalation']:
                stage['stage'] = 'privilege_escalation'
            elif event['event_type'] in ['lateral_movement']:
                stage['stage'] = 'lateral_movement'
            
            stages.append(stage)
        
        return stages
    
    def _identify_mitre_techniques(self, events: List[Any]) -> List[str]:
        """Identify MITRE ATT&CK techniques from events"""
        techniques = []
        
        for event in events:
            # Simple technique mapping
            if event.get('process_name') and 'powershell' in event['process_name'].lower():
                techniques.append('T1059.001')  # PowerShell
            if event.get('command_line') and 'whoami' in event['command_line'].lower():
                techniques.append('T1033')      # System Owner/User Discovery
            if event.get('network_protocol') == 'rdp':
                techniques.append('T1021.001')  # Remote Desktop Protocol
        
        return list(set(techniques))
    
    async def _store_attack_chain(self, chain: AttackChain):
        """Store attack chain in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO attack_chains 
                (chain_id, incident_ids, attack_stages, techniques_used,
                 threat_actor_attribution, timeline, attack_objective,
                 impact_assessment, mitigation_recommendations)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                chain.chain_id, json.dumps(chain.incident_ids),
                json.dumps(chain.attack_stages), json.dumps(chain.techniques_used),
                chain.threat_actor_attribution, json.dumps(chain.timeline, default=str),
                chain.attack_objective, chain.impact_assessment,
                json.dumps(chain.mitigation_recommendations)
            )

# Global correlation engine instance
correlation_engine = IncidentCorrelationEngine()

# FastAPI integration
class CorrelationAPI:
    """FastAPI endpoints for incident correlation"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.get("/api/correlations")
        async def get_correlations(hours: int = 24):
            """Get recent correlations"""
            async with correlation_engine.db_pool.acquire() as conn:
                correlations = await conn.fetch("""
                    SELECT * FROM incident_correlations 
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                    ORDER BY confidence_score DESC
                """, hours)
                
                return {"correlations": [dict(c) for c in correlations]}
        
        @self.app.get("/api/attack-chains")
        async def get_attack_chains(days: int = 7):
            """Get detected attack chains"""
            async with correlation_engine.db_pool.acquire() as conn:
                chains = await conn.fetch("""
                    SELECT * FROM attack_chains 
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    ORDER BY created_at DESC
                """, days)
                
                return {"attack_chains": [dict(c) for c in chains]}
        
        @self.app.post("/api/correlations/analyze")
        async def analyze_event(event_data: dict):
            """Analyze a new event for correlations"""
            event = IncidentEvent(**event_data)
            correlations = await correlation_engine.process_incident_event(event)
            
            return {
                "event_id": event.event_id,
                "correlations_found": len(correlations),
                "correlations": [asdict(c) for c in correlations]
            }

# Initialize correlation engine
async def initialize_incident_correlation():
    """Initialize incident correlation system"""
    await correlation_engine.initialize()
    logfire.info("Incident correlation engine ready")