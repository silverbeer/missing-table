"""
Advanced Network Traffic Analysis and Intrusion Detection System
Real-time network monitoring with ML-powered threat detection and automated response
"""

import asyncio
import json
import logging
import hashlib
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import DBSCAN
import logfire
from prometheus_client import Counter, Histogram, Gauge
import redis
import scapy
from scapy.all import sniff, IP, TCP, UDP, ICMP, ARP, DNS
import dpkt
import socket
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Prometheus metrics
NETWORK_INTRUSIONS_DETECTED = Counter(
    'network_intrusions_detected_total',
    'Total number of network intrusions detected',
    ['attack_type', 'severity', 'protocol']
)

TRAFFIC_ANALYSIS_LATENCY = Histogram(
    'traffic_analysis_latency_seconds',
    'Time taken to analyze network traffic',
    ['analysis_type']
)

NETWORK_CONNECTIONS_TOTAL = Counter(
    'network_connections_total',
    'Total number of network connections',
    ['protocol', 'direction', 'status']
)

SUSPICIOUS_IPS_BLOCKED = Counter(
    'suspicious_ips_blocked_total',
    'Number of suspicious IPs blocked',
    ['block_reason']
)

BANDWIDTH_USAGE_BYTES = Gauge(
    'bandwidth_usage_bytes',
    'Current bandwidth usage in bytes',
    ['direction', 'protocol']
)

class AttackType(str, Enum):
    """Types of network attacks"""
    PORT_SCAN = "port_scan"
    DDoS = "ddos"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    LATERAL_MOVEMENT = "lateral_movement"
    DNS_TUNNELING = "dns_tunneling"
    SUSPICIOUS_UPLOAD = "suspicious_upload"
    MALWARE_COMMUNICATION = "malware_communication"
    CRYPTO_MINING = "crypto_mining"

class ThreatSeverity(str, Enum):
    """Threat severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class NetworkProtocol(str, Enum):
    """Network protocols"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"
    SSH = "ssh"
    FTP = "ftp"
    SMTP = "smtp"

@dataclass
class NetworkFlow:
    """Network flow record"""
    flow_id: str
    timestamp: datetime
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: NetworkProtocol
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    duration_seconds: float
    flags: List[str]
    payload_sample: Optional[str]
    geolocation_src: Optional[str]
    geolocation_dst: Optional[str]
    reputation_score: float

@dataclass
class NetworkAnomaly:
    """Detected network anomaly"""
    anomaly_id: str
    attack_type: AttackType
    severity: ThreatSeverity
    confidence_score: float
    detected_at: datetime
    source_ip: str
    destination_ip: Optional[str]
    affected_ports: List[int]
    flow_ids: List[str]
    indicators: List[str]
    threat_intelligence: Dict[str, Any]
    mitigation_actions: List[str]
    context: Dict[str, Any]

@dataclass
class ThreatIntelligence:
    """Network threat intelligence data"""
    ip_address: str
    threat_type: str
    malware_family: Optional[str]
    threat_actor: Optional[str]
    first_seen: datetime
    last_seen: datetime
    confidence: float
    sources: List[str]
    additional_context: Dict[str, Any]

class NetworkIntrusionDetector:
    """Advanced network intrusion detection system"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=5)
        
        # ML Models for traffic analysis
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.attack_classifier = RandomForestClassifier(
            n_estimators=200,
            random_state=42
        )
        self.scaler = StandardScaler()
        
        # Network monitoring state
        self.active_flows: Dict[str, NetworkFlow] = {}
        self.blocked_ips: Set[str] = set()
        self.threat_intel_cache: Dict[str, ThreatIntelligence] = {}
        
        # Signature-based detection rules
        self.attack_signatures = {
            'port_scan': {
                'pattern': 'multiple_ports_single_source',
                'threshold': 10,
                'timeframe': 60
            },
            'ddos': {
                'pattern': 'high_request_rate',
                'threshold': 1000,
                'timeframe': 10
            },
            'brute_force': {
                'pattern': 'repeated_auth_failures',
                'threshold': 5,
                'timeframe': 300
            }
        }
        
        # Network baseline parameters
        self.baseline_metrics = {
            'normal_bandwidth_mbps': 100.0,
            'normal_connections_per_minute': 50.0,
            'normal_unique_ips_per_hour': 20.0
        }
    
    async def initialize(self):
        """Initialize network intrusion detection system"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/network_security",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_threat_intelligence()
        await self._train_ml_models()
        await self._start_packet_capture()
        
        logfire.info("Network intrusion detection system initialized")
    
    async def _create_tables(self):
        """Create network security database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS network_flows (
                    flow_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    source_ip INET NOT NULL,
                    destination_ip INET NOT NULL,
                    source_port INTEGER NOT NULL,
                    destination_port INTEGER NOT NULL,
                    protocol VARCHAR NOT NULL,
                    bytes_sent BIGINT DEFAULT 0,
                    bytes_received BIGINT DEFAULT 0,
                    packets_sent INTEGER DEFAULT 0,
                    packets_received INTEGER DEFAULT 0,
                    duration_seconds FLOAT DEFAULT 0,
                    flags JSONB,
                    payload_sample TEXT,
                    geolocation_src VARCHAR,
                    geolocation_dst VARCHAR,
                    reputation_score FLOAT DEFAULT 50.0,
                    features JSONB,
                    is_anomalous BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_anomalies (
                    anomaly_id VARCHAR PRIMARY KEY,
                    attack_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    detected_at TIMESTAMP NOT NULL,
                    source_ip INET NOT NULL,
                    destination_ip INET,
                    affected_ports JSONB,
                    flow_ids JSONB,
                    indicators JSONB,
                    threat_intelligence JSONB,
                    mitigation_actions JSONB,
                    context JSONB,
                    status VARCHAR DEFAULT 'active',
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS threat_intelligence (
                    ip_address INET PRIMARY KEY,
                    threat_type VARCHAR NOT NULL,
                    malware_family VARCHAR,
                    threat_actor VARCHAR,
                    first_seen TIMESTAMP NOT NULL,
                    last_seen TIMESTAMP NOT NULL,
                    confidence FLOAT NOT NULL,
                    sources JSONB,
                    additional_context JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS blocked_ips (
                    ip_address INET PRIMARY KEY,
                    block_reason VARCHAR NOT NULL,
                    blocked_at TIMESTAMP NOT NULL,
                    blocked_until TIMESTAMP,
                    block_count INTEGER DEFAULT 1,
                    last_activity TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_baselines (
                    metric_name VARCHAR PRIMARY KEY,
                    baseline_value FLOAT NOT NULL,
                    standard_deviation FLOAT,
                    last_calculated TIMESTAMP NOT NULL,
                    sample_size INTEGER,
                    confidence_interval JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_network_flows_timestamp ON network_flows(timestamp);
                CREATE INDEX IF NOT EXISTS idx_network_flows_source_ip ON network_flows(source_ip);
                CREATE INDEX IF NOT EXISTS idx_network_flows_dest_ip ON network_flows(destination_ip);
                CREATE INDEX IF NOT EXISTS idx_network_anomalies_detected_at ON network_anomalies(detected_at);
                CREATE INDEX IF NOT EXISTS idx_network_anomalies_source_ip ON network_anomalies(source_ip);
                CREATE INDEX IF NOT EXISTS idx_network_anomalies_attack_type ON network_anomalies(attack_type);
            """)
    
    async def _load_threat_intelligence(self):
        """Load threat intelligence data"""
        async with self.db_pool.acquire() as conn:
            threat_data = await conn.fetch("SELECT * FROM threat_intelligence")
            
            for threat in threat_data:
                intel = ThreatIntelligence(
                    ip_address=str(threat['ip_address']),
                    threat_type=threat['threat_type'],
                    malware_family=threat['malware_family'],
                    threat_actor=threat['threat_actor'],
                    first_seen=threat['first_seen'],
                    last_seen=threat['last_seen'],
                    confidence=threat['confidence'],
                    sources=threat['sources'] or [],
                    additional_context=threat['additional_context'] or {}
                )
                self.threat_intel_cache[intel.ip_address] = intel
        
        # Load from external threat feeds (mock implementation)
        await self._update_threat_feeds()
    
    async def _update_threat_feeds(self):
        """Update threat intelligence from external feeds"""
        # Mock threat intelligence data
        mock_threats = [
            {
                'ip_address': '192.168.100.50',
                'threat_type': 'malware_c2',
                'confidence': 0.9,
                'sources': ['feed1', 'feed2']
            },
            {
                'ip_address': '10.0.0.100',
                'threat_type': 'scanning_host',
                'confidence': 0.7,
                'sources': ['internal_detection']
            }
        ]
        
        for threat_data in mock_threats:
            intel = ThreatIntelligence(
                ip_address=threat_data['ip_address'],
                threat_type=threat_data['threat_type'],
                malware_family=None,
                threat_actor=None,
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                confidence=threat_data['confidence'],
                sources=threat_data['sources'],
                additional_context={}
            )
            self.threat_intel_cache[intel.ip_address] = intel
    
    async def _train_ml_models(self):
        """Train ML models for network anomaly detection"""
        # Get historical network flow data
        async with self.db_pool.acquire() as conn:
            training_data = await conn.fetch("""
                SELECT * FROM network_flows 
                WHERE timestamp > NOW() - INTERVAL '7 days'
                AND features IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 10000
            """)
        
        if len(training_data) < 100:
            # Generate synthetic training data
            training_data = self._generate_synthetic_network_data()
        
        # Prepare features for training
        features_df = self._prepare_network_features(training_data)
        
        if not features_df.empty:
            # Train anomaly detector
            X = features_df.fillna(0)
            X_scaled = self.scaler.fit_transform(X)
            self.anomaly_detector.fit(X_scaled)
            
            # Train attack classifier with labeled data
            await self._train_attack_classifier(training_data)
            
            logfire.info(
                "Network ML models trained",
                training_samples=len(training_data),
                features=len(features_df.columns)
            )
    
    def _generate_synthetic_network_data(self) -> List[Dict[str, Any]]:
        """Generate synthetic network data for training"""
        synthetic_data = []
        
        # Normal traffic patterns
        for i in range(1000):
            synthetic_data.append({
                'flow_id': f'syn_flow_{i}',
                'timestamp': datetime.now() - timedelta(days=np.random.randint(1, 7)),
                'source_ip': f'192.168.1.{np.random.randint(1, 254)}',
                'destination_ip': f'10.0.0.{np.random.randint(1, 254)}',
                'source_port': np.random.randint(1024, 65535),
                'destination_port': np.random.choice([80, 443, 22, 21, 25]),
                'protocol': np.random.choice(['tcp', 'udp']),
                'bytes_sent': np.random.exponential(1000),
                'bytes_received': np.random.exponential(2000),
                'packets_sent': np.random.poisson(10),
                'packets_received': np.random.poisson(15),
                'duration_seconds': np.random.exponential(30),
                'features': {
                    'packet_rate': np.random.normal(1.0, 0.3),
                    'byte_rate': np.random.normal(100.0, 30.0),
                    'port_entropy': np.random.normal(2.0, 0.5),
                    'connection_duration': np.random.exponential(30),
                    'payload_entropy': np.random.normal(7.0, 1.0)
                },
                'is_anomalous': False
            })
        
        # Anomalous traffic patterns
        for i in range(100):
            synthetic_data.append({
                'flow_id': f'syn_anom_{i}',
                'timestamp': datetime.now() - timedelta(days=np.random.randint(1, 7)),
                'source_ip': f'192.168.1.{np.random.randint(1, 254)}',
                'destination_ip': f'10.0.0.{np.random.randint(1, 254)}',
                'source_port': np.random.randint(1024, 65535),
                'destination_port': np.random.randint(1, 1024),  # Scanning behavior
                'protocol': 'tcp',
                'bytes_sent': np.random.exponential(100),      # Small packets
                'bytes_received': np.random.exponential(50),   # Minimal response
                'packets_sent': np.random.poisson(50),         # High packet count
                'packets_received': np.random.poisson(5),      # Low response
                'duration_seconds': np.random.exponential(1),  # Short connections
                'features': {
                    'packet_rate': np.random.normal(10.0, 3.0),   # High rate
                    'byte_rate': np.random.normal(50.0, 15.0),    # Low byte rate
                    'port_entropy': np.random.normal(8.0, 1.0),   # High entropy
                    'connection_duration': np.random.exponential(1), # Short duration
                    'payload_entropy': np.random.normal(3.0, 1.0)   # Low entropy
                },
                'is_anomalous': True
            })
        
        return synthetic_data
    
    def _prepare_network_features(self, flow_data: List[Any]) -> pd.DataFrame:
        """Prepare network features for ML models"""
        features_list = []
        
        for flow in flow_data:
            if isinstance(flow, dict):
                features = flow.get('features', {})
            else:
                features = json.loads(flow.get('features', '{}'))
            
            if features:
                features_list.append(features)
        
        return pd.DataFrame(features_list) if features_list else pd.DataFrame()
    
    async def _train_attack_classifier(self, training_data: List[Any]):
        """Train classifier for attack type detection"""
        try:
            # Prepare labeled data
            X, y = [], []
            
            for flow in training_data:
                features = flow.get('features', {}) if isinstance(flow, dict) else json.loads(flow.get('features', '{}'))
                
                if features:
                    feature_vector = [
                        features.get('packet_rate', 0),
                        features.get('byte_rate', 0),
                        features.get('port_entropy', 0),
                        features.get('connection_duration', 0),
                        features.get('payload_entropy', 0)
                    ]
                    X.append(feature_vector)
                    
                    # Simplified labeling based on characteristics
                    if features.get('packet_rate', 0) > 5 and features.get('port_entropy', 0) > 5:
                        y.append('port_scan')
                    elif features.get('byte_rate', 0) > 1000:
                        y.append('ddos')
                    else:
                        y.append('normal')
            
            if len(X) > 10 and len(set(y)) > 1:
                X = np.array(X)
                X_scaled = self.scaler.transform(X)
                
                # Encode labels
                label_encoder = LabelEncoder()
                y_encoded = label_encoder.fit_transform(y)
                
                # Train classifier
                self.attack_classifier.fit(X_scaled, y_encoded)
                
                logfire.info(
                    "Attack classifier trained",
                    samples=len(X),
                    classes=len(set(y))
                )
        
        except Exception as e:
            logger.error(f"Error training attack classifier: {e}")
    
    async def _start_packet_capture(self):
        """Start network packet capture and analysis"""
        # In production, this would start actual packet capture
        # For now, we'll simulate with a background task
        asyncio.create_task(self._simulate_network_traffic())
    
    async def _simulate_network_traffic(self):
        """Simulate network traffic for testing"""
        while True:
            try:
                # Generate simulated network flow
                flow = self._generate_test_flow()
                await self.analyze_network_flow(flow)
                
                # Wait before next flow
                await asyncio.sleep(np.random.exponential(1.0))
                
            except Exception as e:
                logger.error(f"Error in network simulation: {e}")
                await asyncio.sleep(5)
    
    def _generate_test_flow(self) -> NetworkFlow:
        """Generate test network flow"""
        flow_id = f"test_flow_{int(datetime.now().timestamp())}_{np.random.randint(1000, 9999)}"
        
        # Occasionally generate suspicious flow
        is_suspicious = np.random.random() < 0.1
        
        if is_suspicious:
            # Port scan simulation
            source_ip = "192.168.1.100"
            dest_port = np.random.randint(1, 1024)
            bytes_sent = np.random.randint(50, 200)
            packets_sent = np.random.randint(1, 3)
            duration = np.random.uniform(0.1, 1.0)
        else:
            # Normal traffic
            source_ip = f"192.168.1.{np.random.randint(1, 50)}"
            dest_port = np.random.choice([80, 443, 22])
            bytes_sent = np.random.randint(500, 5000)
            packets_sent = np.random.randint(5, 50)
            duration = np.random.uniform(5.0, 300.0)
        
        return NetworkFlow(
            flow_id=flow_id,
            timestamp=datetime.now(),
            source_ip=source_ip,
            destination_ip="10.0.0.50",
            source_port=np.random.randint(1024, 65535),
            destination_port=dest_port,
            protocol=NetworkProtocol.TCP,
            bytes_sent=bytes_sent,
            bytes_received=np.random.randint(100, 1000),
            packets_sent=packets_sent,
            packets_received=np.random.randint(1, 20),
            duration_seconds=duration,
            flags=["SYN", "ACK"],
            payload_sample=None,
            geolocation_src="US",
            geolocation_dst="US",
            reputation_score=np.random.uniform(60, 95)
        )
    
    @logfire.instrument("Analyze Network Flow")
    async def analyze_network_flow(self, flow: NetworkFlow) -> List[NetworkAnomaly]:
        """Analyze network flow for anomalies and threats"""
        with logfire.span("network_flow_analysis", flow_id=flow.flow_id):
            start_time = datetime.now()
            anomalies = []
            
            # Extract features
            features = self._extract_network_features(flow)
            
            # Store flow with features
            await self._store_network_flow(flow, features)
            
            # Check threat intelligence
            threat_intel = await self._check_threat_intelligence(flow.source_ip)
            
            # Run detection algorithms
            ml_anomalies = await self._detect_ml_anomalies(flow, features)
            anomalies.extend(ml_anomalies)
            
            signature_anomalies = await self._detect_signature_anomalies(flow, features)
            anomalies.extend(signature_anomalies)
            
            statistical_anomalies = await self._detect_statistical_anomalies(flow, features)
            anomalies.extend(statistical_anomalies)
            
            behavioral_anomalies = await self._detect_behavioral_anomalies(flow, features)
            anomalies.extend(behavioral_anomalies)
            
            # Store anomalies
            for anomaly in anomalies:
                await self._store_network_anomaly(anomaly)
                
                # Update metrics
                NETWORK_INTRUSIONS_DETECTED.labels(
                    attack_type=anomaly.attack_type.value,
                    severity=anomaly.severity.value,
                    protocol=flow.protocol.value
                ).inc()
                
                # Trigger mitigation if high severity
                if anomaly.severity in [ThreatSeverity.CRITICAL, ThreatSeverity.HIGH]:
                    await self._trigger_mitigation(anomaly)
            
            # Update connection metrics
            NETWORK_CONNECTIONS_TOTAL.labels(
                protocol=flow.protocol.value,
                direction="inbound" if self._is_internal_ip(flow.destination_ip) else "outbound",
                status="suspicious" if anomalies else "normal"
            ).inc()
            
            # Update bandwidth metrics
            BANDWIDTH_USAGE_BYTES.labels(
                direction="ingress",
                protocol=flow.protocol.value
            ).inc(flow.bytes_received)
            
            BANDWIDTH_USAGE_BYTES.labels(
                direction="egress",
                protocol=flow.protocol.value
            ).inc(flow.bytes_sent)
            
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            TRAFFIC_ANALYSIS_LATENCY.labels(analysis_type="complete").observe(processing_time)
            
            logfire.info(
                "Network flow analyzed",
                flow_id=flow.flow_id,
                source_ip=flow.source_ip,
                anomalies_detected=len(anomalies),
                processing_time_ms=processing_time * 1000
            )
            
            return anomalies
    
    def _extract_network_features(self, flow: NetworkFlow) -> Dict[str, float]:
        """Extract features from network flow"""
        features = {}
        
        # Traffic volume features
        features['bytes_per_packet_sent'] = flow.bytes_sent / max(flow.packets_sent, 1)
        features['bytes_per_packet_received'] = flow.bytes_received / max(flow.packets_received, 1)
        features['packet_rate'] = flow.packets_sent / max(flow.duration_seconds, 0.1)
        features['byte_rate'] = flow.bytes_sent / max(flow.duration_seconds, 0.1)
        
        # Connection characteristics
        features['connection_duration'] = flow.duration_seconds
        features['bytes_ratio'] = flow.bytes_sent / max(flow.bytes_received, 1)
        features['packets_ratio'] = flow.packets_sent / max(flow.packets_received, 1)
        
        # Port and protocol features
        features['is_well_known_port'] = 1.0 if flow.destination_port <= 1024 else 0.0
        features['is_dynamic_port'] = 1.0 if flow.source_port >= 32768 else 0.0
        features['port_number'] = float(flow.destination_port)
        
        # Reputation and geolocation
        features['reputation_score'] = flow.reputation_score
        features['is_internal_src'] = 1.0 if self._is_internal_ip(flow.source_ip) else 0.0
        features['is_internal_dst'] = 1.0 if self._is_internal_ip(flow.destination_ip) else 0.0
        
        # Time-based features
        features['hour_of_day'] = flow.timestamp.hour
        features['day_of_week'] = flow.timestamp.weekday()
        features['is_business_hours'] = 1.0 if 9 <= flow.timestamp.hour <= 17 else 0.0
        
        return features
    
    def _is_internal_ip(self, ip_address: str) -> bool:
        """Check if IP address is internal"""
        try:
            ip = ipaddress.ip_address(ip_address)
            return (
                ip.is_private or
                ip.is_loopback or
                ip.is_link_local or
                str(ip).startswith('10.') or
                str(ip).startswith('192.168.')
            )
        except:
            return False
    
    async def _check_threat_intelligence(self, ip_address: str) -> Optional[ThreatIntelligence]:
        """Check IP against threat intelligence"""
        return self.threat_intel_cache.get(ip_address)
    
    async def _detect_ml_anomalies(self, flow: NetworkFlow, features: Dict[str, float]) -> List[NetworkAnomaly]:
        """Detect anomalies using ML models"""
        anomalies = []
        
        try:
            # Prepare feature vector
            feature_vector = [
                features.get('packet_rate', 0),
                features.get('byte_rate', 0),
                features.get('connection_duration', 0),
                features.get('bytes_ratio', 0),
                features.get('reputation_score', 50)
            ]
            
            feature_vector_scaled = self.scaler.transform([feature_vector])
            
            # Anomaly detection
            anomaly_score = self.anomaly_detector.decision_function(feature_vector_scaled)[0]
            is_anomaly = self.anomaly_detector.predict(feature_vector_scaled)[0] == -1
            
            if is_anomaly:
                # Classify attack type
                attack_type = await self._classify_attack_type(flow, features)
                severity = self._calculate_threat_severity(anomaly_score, features)
                
                anomaly = NetworkAnomaly(
                    anomaly_id=f"ml_{flow.flow_id}_{int(flow.timestamp.timestamp())}",
                    attack_type=attack_type,
                    severity=severity,
                    confidence_score=abs(anomaly_score),
                    detected_at=flow.timestamp,
                    source_ip=flow.source_ip,
                    destination_ip=flow.destination_ip,
                    affected_ports=[flow.destination_port],
                    flow_ids=[flow.flow_id],
                    indicators=[
                        f"anomaly_score_{abs(anomaly_score):.3f}",
                        f"packet_rate_{features.get('packet_rate', 0):.1f}",
                        f"byte_rate_{features.get('byte_rate', 0):.1f}"
                    ],
                    threat_intelligence={},
                    mitigation_actions=self._get_mitigation_actions(attack_type),
                    context={
                        "detection_method": "ml_isolation_forest",
                        "anomaly_score": float(anomaly_score),
                        "features": features
                    }
                )
                anomalies.append(anomaly)
        
        except Exception as e:
            logger.error(f"Error in ML anomaly detection: {e}")
        
        return anomalies
    
    async def _classify_attack_type(self, flow: NetworkFlow, features: Dict[str, float]) -> AttackType:
        """Classify the type of network attack"""
        # Rule-based classification
        if features.get('packet_rate', 0) > 10 and flow.destination_port < 1024:
            return AttackType.PORT_SCAN
        
        if features.get('byte_rate', 0) > 10000:
            return AttackType.DDoS
        
        if flow.destination_port in [22, 3389, 21] and features.get('connection_duration', 0) < 5:
            return AttackType.BRUTE_FORCE
        
        if flow.destination_port == 53 and features.get('packet_rate', 0) > 50:
            return AttackType.DNS_TUNNELING
        
        # Default to suspicious activity
        return AttackType.LATERAL_MOVEMENT
    
    def _calculate_threat_severity(self, anomaly_score: float, features: Dict[str, float]) -> ThreatSeverity:
        """Calculate threat severity"""
        severity_score = abs(anomaly_score)
        
        # Adjust based on reputation
        if features.get('reputation_score', 50) < 30:
            severity_score += 0.3
        
        # Adjust based on internal traffic
        if features.get('is_internal_src', 0) == 1 and features.get('is_internal_dst', 0) == 1:
            severity_score += 0.2  # Internal lateral movement is serious
        
        if severity_score > 0.8:
            return ThreatSeverity.CRITICAL
        elif severity_score > 0.6:
            return ThreatSeverity.HIGH
        elif severity_score > 0.4:
            return ThreatSeverity.MEDIUM
        else:
            return ThreatSeverity.LOW
    
    def _get_mitigation_actions(self, attack_type: AttackType) -> List[str]:
        """Get mitigation actions for attack type"""
        mitigation_map = {
            AttackType.PORT_SCAN: ["block_source_ip", "rate_limit", "alert_security_team"],
            AttackType.DDoS: ["rate_limit", "block_source_ip", "scale_infrastructure"],
            AttackType.BRUTE_FORCE: ["block_source_ip", "increase_auth_requirements", "alert_admin"],
            AttackType.DNS_TUNNELING: ["block_dns_queries", "investigate_payload", "quarantine_host"],
            AttackType.LATERAL_MOVEMENT: ["isolate_host", "investigate_credentials", "alert_security_team"]
        }
        
        return mitigation_map.get(attack_type, ["monitor", "alert_security_team"])
    
    async def _detect_signature_anomalies(self, flow: NetworkFlow, features: Dict[str, float]) -> List[NetworkAnomaly]:
        """Detect anomalies using signature-based rules"""
        anomalies = []
        
        # Port scan detection
        if await self._detect_port_scan(flow.source_ip):
            anomaly = NetworkAnomaly(
                anomaly_id=f"sig_portscan_{flow.flow_id}",
                attack_type=AttackType.PORT_SCAN,
                severity=ThreatSeverity.HIGH,
                confidence_score=0.9,
                detected_at=flow.timestamp,
                source_ip=flow.source_ip,
                destination_ip=flow.destination_ip,
                affected_ports=[flow.destination_port],
                flow_ids=[flow.flow_id],
                indicators=["multiple_port_connections", "rapid_connection_attempts"],
                threat_intelligence={},
                mitigation_actions=["block_source_ip", "investigate_host"],
                context={"detection_method": "signature_based", "rule": "port_scan"}
            )
            anomalies.append(anomaly)
        
        return anomalies
    
    async def _detect_port_scan(self, source_ip: str) -> bool:
        """Detect port scanning behavior"""
        # Check recent connections from this IP
        time_window = datetime.now() - timedelta(minutes=5)
        
        async with self.db_pool.acquire() as conn:
            port_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT destination_port)
                FROM network_flows 
                WHERE source_ip = $1 
                AND timestamp > $2
            """, source_ip, time_window)
        
        return port_count >= 10  # Threshold for port scan
    
    async def _detect_statistical_anomalies(self, flow: NetworkFlow, features: Dict[str, float]) -> List[NetworkAnomaly]:
        """Detect statistical anomalies"""
        anomalies = []
        
        # Check against baseline metrics
        if features.get('byte_rate', 0) > self.baseline_metrics['normal_bandwidth_mbps'] * 1000000:
            anomaly = NetworkAnomaly(
                anomaly_id=f"stat_bandwidth_{flow.flow_id}",
                attack_type=AttackType.DDoS,
                severity=ThreatSeverity.HIGH,
                confidence_score=0.8,
                detected_at=flow.timestamp,
                source_ip=flow.source_ip,
                destination_ip=flow.destination_ip,
                affected_ports=[flow.destination_port],
                flow_ids=[flow.flow_id],
                indicators=["abnormal_bandwidth_usage"],
                threat_intelligence={},
                mitigation_actions=["rate_limit", "investigate_traffic"],
                context={"detection_method": "statistical", "baseline_exceeded": True}
            )
            anomalies.append(anomaly)
        
        return anomalies
    
    async def _detect_behavioral_anomalies(self, flow: NetworkFlow, features: Dict[str, float]) -> List[NetworkAnomaly]:
        """Detect behavioral anomalies"""
        anomalies = []
        
        # Check for unusual time patterns
        if features.get('is_business_hours', 1) == 0 and features.get('byte_rate', 0) > 1000:
            anomaly = NetworkAnomaly(
                anomaly_id=f"behav_offhours_{flow.flow_id}",
                attack_type=AttackType.DATA_EXFILTRATION,
                severity=ThreatSeverity.MEDIUM,
                confidence_score=0.6,
                detected_at=flow.timestamp,
                source_ip=flow.source_ip,
                destination_ip=flow.destination_ip,
                affected_ports=[flow.destination_port],
                flow_ids=[flow.flow_id],
                indicators=["off_hours_activity", "high_data_transfer"],
                threat_intelligence={},
                mitigation_actions=["monitor", "investigate_user"],
                context={"detection_method": "behavioral", "pattern": "off_hours_transfer"}
            )
            anomalies.append(anomaly)
        
        return anomalies

# Continue with storage and mitigation methods...
# Global network intrusion detector instance
network_detector = NetworkIntrusionDetector()

# Initialize network intrusion detection
async def initialize_network_intrusion_detection():
    """Initialize network intrusion detection system"""
    await network_detector.initialize()
    logfire.info("Network intrusion detection system ready")