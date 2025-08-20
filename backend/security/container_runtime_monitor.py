"""
Advanced Container Runtime Behavior Monitoring System
Real-time monitoring of container activities, process behavior, and security events
"""

import asyncio
import json
import logging
import hashlib
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import logfire
from prometheus_client import Counter, Histogram, Gauge
import redis
import docker
import subprocess
from kubernetes import client, config
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Prometheus metrics
CONTAINER_SECURITY_EVENTS = Counter(
    'container_security_events_total',
    'Total number of container security events',
    ['event_type', 'severity', 'container_name']
)

RUNTIME_ANOMALIES_DETECTED = Counter(
    'runtime_anomalies_detected_total',
    'Total number of runtime anomalies detected',
    ['anomaly_type', 'container_id']
)

CONTAINER_RESOURCE_USAGE = Gauge(
    'container_resource_usage',
    'Container resource usage metrics',
    ['container_id', 'resource_type']
)

PROCESS_MONITORING_LATENCY = Histogram(
    'process_monitoring_latency_seconds',
    'Time taken to process container monitoring events',
    ['monitor_type']
)

SUSPICIOUS_PROCESSES_BLOCKED = Counter(
    'suspicious_processes_blocked_total',
    'Number of suspicious processes blocked',
    ['container_id', 'process_name']
)

class SecurityEventType(str, Enum):
    """Types of container security events"""
    PRIVILEGE_ESCALATION = "privilege_escalation"
    FILE_INTEGRITY_VIOLATION = "file_integrity_violation"
    NETWORK_ANOMALY = "network_anomaly"
    PROCESS_ANOMALY = "process_anomaly"
    SYSCALL_ANOMALY = "syscall_anomaly"
    MOUNT_ANOMALY = "mount_anomaly"
    CAPABILITY_VIOLATION = "capability_violation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONTAINER_ESCAPE_ATTEMPT = "container_escape_attempt"
    MALICIOUS_BINARY = "malicious_binary"

class AnomalySeverity(str, Enum):
    """Severity levels for anomalies"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class ContainerInfo:
    """Container information"""
    container_id: str
    name: str
    image: str
    image_sha: str
    namespace: str
    pod_name: str
    labels: Dict[str, str]
    security_context: Dict[str, Any]
    resource_limits: Dict[str, Any]
    network_mode: str
    volumes: List[Dict[str, Any]]
    created_at: datetime
    started_at: datetime

@dataclass
class ProcessEvent:
    """Process execution event"""
    event_id: str
    container_id: str
    process_id: int
    parent_process_id: int
    process_name: str
    command_line: str
    user_id: int
    group_id: int
    working_directory: str
    environment_vars: Dict[str, str]
    file_descriptors: List[str]
    capabilities: List[str]
    timestamp: datetime
    
@dataclass
class FileSystemEvent:
    """File system access event"""
    event_id: str
    container_id: str
    process_id: int
    operation: str  # read, write, create, delete, modify
    file_path: str
    file_permissions: str
    file_owner: str
    file_size: int
    access_mode: str
    timestamp: datetime

@dataclass
class NetworkEvent:
    """Network activity event"""
    event_id: str
    container_id: str
    process_id: int
    protocol: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    data_size: int
    direction: str  # inbound, outbound
    timestamp: datetime

@dataclass
class RuntimeAnomaly:
    """Runtime behavior anomaly"""
    anomaly_id: str
    container_id: str
    anomaly_type: SecurityEventType
    severity: AnomalySeverity
    confidence_score: float
    detected_at: datetime
    related_events: List[str]
    behavioral_indicators: List[str]
    baseline_deviation: Dict[str, float]
    threat_assessment: Dict[str, Any]
    recommended_actions: List[str]
    context: Dict[str, Any]

class ContainerRuntimeMonitor:
    """Advanced container runtime behavior monitoring system"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=6)
        
        # Docker and Kubernetes clients
        self.docker_client = docker.from_env()
        try:
            config.load_incluster_config()  # Running in cluster
        except:
            try:
                config.load_kube_config()  # Running locally
            except:
                logger.warning("Could not load Kubernetes config")
        
        self.k8s_v1 = client.CoreV1Api()
        
        # ML models for behavior analysis
        self.process_anomaly_detector = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=100
        )
        self.network_anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        
        # Behavioral baselines
        self.container_baselines: Dict[str, Dict[str, Any]] = {}
        self.known_good_processes: Set[str] = {
            '/bin/bash', '/bin/sh', '/usr/bin/python3', '/usr/bin/node',
            '/app/main', '/usr/local/bin/gunicorn', '/usr/bin/nginx'
        }
        self.suspicious_processes: Set[str] = {
            'nc', 'netcat', 'nmap', 'masscan', 'curl', 'wget',
            'base64', 'xxd', 'strings', 'strace', 'tcpdump'
        }
        
        # File integrity monitoring
        self.protected_paths: Set[str] = {
            '/etc/passwd', '/etc/shadow', '/etc/sudoers',
            '/bin/', '/sbin/', '/usr/bin/', '/usr/sbin/',
            '/lib/', '/usr/lib/', '/etc/ssl/'
        }
        
    async def initialize(self):
        """Initialize container runtime monitoring system"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/container_security",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_container_baselines()
        await self._train_ml_models()
        await self._start_monitoring()
        
        logfire.info("Container runtime monitoring system initialized")
    
    async def _create_tables(self):
        """Create container monitoring database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS containers (
                    container_id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    image VARCHAR NOT NULL,
                    image_sha VARCHAR,
                    namespace VARCHAR,
                    pod_name VARCHAR,
                    labels JSONB,
                    security_context JSONB,
                    resource_limits JSONB,
                    network_mode VARCHAR,
                    volumes JSONB,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    status VARCHAR DEFAULT 'running',
                    last_seen TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS process_events (
                    event_id VARCHAR PRIMARY KEY,
                    container_id VARCHAR REFERENCES containers(container_id),
                    process_id INTEGER NOT NULL,
                    parent_process_id INTEGER,
                    process_name VARCHAR NOT NULL,
                    command_line TEXT,
                    user_id INTEGER,
                    group_id INTEGER,
                    working_directory VARCHAR,
                    environment_vars JSONB,
                    file_descriptors JSONB,
                    capabilities JSONB,
                    timestamp TIMESTAMP NOT NULL,
                    is_suspicious BOOLEAN DEFAULT FALSE,
                    risk_score FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS filesystem_events (
                    event_id VARCHAR PRIMARY KEY,
                    container_id VARCHAR REFERENCES containers(container_id),
                    process_id INTEGER NOT NULL,
                    operation VARCHAR NOT NULL,
                    file_path VARCHAR NOT NULL,
                    file_permissions VARCHAR,
                    file_owner VARCHAR,
                    file_size BIGINT,
                    access_mode VARCHAR,
                    timestamp TIMESTAMP NOT NULL,
                    is_violation BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_events (
                    event_id VARCHAR PRIMARY KEY,
                    container_id VARCHAR REFERENCES containers(container_id),
                    process_id INTEGER NOT NULL,
                    protocol VARCHAR NOT NULL,
                    source_ip INET NOT NULL,
                    destination_ip INET NOT NULL,
                    source_port INTEGER NOT NULL,
                    destination_port INTEGER NOT NULL,
                    data_size BIGINT DEFAULT 0,
                    direction VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_anomalous BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS runtime_anomalies (
                    anomaly_id VARCHAR PRIMARY KEY,
                    container_id VARCHAR REFERENCES containers(container_id),
                    anomaly_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    detected_at TIMESTAMP NOT NULL,
                    related_events JSONB,
                    behavioral_indicators JSONB,
                    baseline_deviation JSONB,
                    threat_assessment JSONB,
                    recommended_actions JSONB,
                    context JSONB,
                    status VARCHAR DEFAULT 'active',
                    investigated_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS container_baselines (
                    container_id VARCHAR PRIMARY KEY,
                    image VARCHAR NOT NULL,
                    normal_processes JSONB,
                    typical_network_patterns JSONB,
                    expected_file_access JSONB,
                    resource_usage_patterns JSONB,
                    baseline_confidence FLOAT DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_process_events_container_id ON process_events(container_id);
                CREATE INDEX IF NOT EXISTS idx_process_events_timestamp ON process_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_filesystem_events_container_id ON filesystem_events(container_id);
                CREATE INDEX IF NOT EXISTS idx_network_events_container_id ON network_events(container_id);
                CREATE INDEX IF NOT EXISTS idx_runtime_anomalies_detected_at ON runtime_anomalies(detected_at);
                CREATE INDEX IF NOT EXISTS idx_runtime_anomalies_severity ON runtime_anomalies(severity);
            """)
    
    async def _load_container_baselines(self):
        """Load existing container behavioral baselines"""
        async with self.db_pool.acquire() as conn:
            baselines = await conn.fetch("SELECT * FROM container_baselines")
            
            for baseline in baselines:
                self.container_baselines[baseline['container_id']] = {
                    'image': baseline['image'],
                    'normal_processes': baseline['normal_processes'] or [],
                    'typical_network_patterns': baseline['typical_network_patterns'] or {},
                    'expected_file_access': baseline['expected_file_access'] or [],
                    'resource_usage_patterns': baseline['resource_usage_patterns'] or {},
                    'baseline_confidence': baseline['baseline_confidence'],
                    'last_updated': baseline['last_updated']
                }
    
    async def _train_ml_models(self):
        """Train ML models for anomaly detection"""
        # Get historical process events
        async with self.db_pool.acquire() as conn:
            process_data = await conn.fetch("""
                SELECT * FROM process_events 
                WHERE timestamp > NOW() - INTERVAL '7 days'
                ORDER BY timestamp DESC
                LIMIT 5000
            """)
            
            network_data = await conn.fetch("""
                SELECT * FROM network_events 
                WHERE timestamp > NOW() - INTERVAL '7 days'
                ORDER BY timestamp DESC
                LIMIT 5000
            """)
        
        # Train process anomaly detector
        if len(process_data) > 100:
            process_features = self._extract_process_features(process_data)
            if process_features:
                X_process = self.scaler.fit_transform(process_features)
                self.process_anomaly_detector.fit(X_process)
        
        # Train network anomaly detector
        if len(network_data) > 100:
            network_features = self._extract_network_features(network_data)
            if network_features:
                X_network = self.scaler.fit_transform(network_features)
                self.network_anomaly_detector.fit(X_network)
        
        logfire.info(
            "Container ML models trained",
            process_samples=len(process_data),
            network_samples=len(network_data)
        )
    
    def _extract_process_features(self, process_data: List[Any]) -> Optional[np.ndarray]:
        """Extract features from process events"""
        features = []
        
        for event in process_data:
            try:
                feature_vector = [
                    event['user_id'] or 0,
                    event['group_id'] or 0,
                    len(event['command_line'] or ''),
                    len(event['environment_vars'] or {}),
                    len(event['file_descriptors'] or []),
                    1.0 if event['process_name'] in self.suspicious_processes else 0.0,
                    event['process_id'] or 0
                ]
                features.append(feature_vector)
            except Exception as e:
                logger.warning(f"Error extracting process features: {e}")
                continue
        
        return np.array(features) if features else None
    
    def _extract_network_features(self, network_data: List[Any]) -> Optional[np.ndarray]:
        """Extract features from network events"""
        features = []
        
        for event in network_data:
            try:
                feature_vector = [
                    event['source_port'] or 0,
                    event['destination_port'] or 0,
                    event['data_size'] or 0,
                    1.0 if event['protocol'] == 'tcp' else 0.0,
                    1.0 if event['direction'] == 'outbound' else 0.0,
                    self._calculate_ip_reputation(str(event['destination_ip']))
                ]
                features.append(feature_vector)
            except Exception as e:
                logger.warning(f"Error extracting network features: {e}")
                continue
        
        return np.array(features) if features else None
    
    def _calculate_ip_reputation(self, ip_address: str) -> float:
        """Calculate IP reputation score (simplified)"""
        # In production, would integrate with threat intelligence
        if ip_address.startswith('10.') or ip_address.startswith('192.168.'):
            return 90.0  # Internal networks
        elif ip_address.startswith('127.'):
            return 95.0  # Localhost
        else:
            return 50.0  # External, unknown reputation
    
    async def _start_monitoring(self):
        """Start container monitoring tasks"""
        # Start monitoring tasks
        asyncio.create_task(self._monitor_containers())
        asyncio.create_task(self._monitor_processes())
        asyncio.create_task(self._monitor_filesystem())
        asyncio.create_task(self._monitor_network_activity())
        asyncio.create_task(self._resource_monitoring())
    
    async def _monitor_containers(self):
        """Monitor container lifecycle events"""
        while True:
            try:
                # Discover running containers
                containers = self.docker_client.containers.list()
                
                for container in containers:
                    await self._update_container_info(container)
                
                # Check for new/stopped containers
                await self._detect_container_changes()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring containers: {e}")
                await asyncio.sleep(60)
    
    async def _update_container_info(self, container):
        """Update container information in database"""
        try:
            container_info = ContainerInfo(
                container_id=container.id[:12],
                name=container.name,
                image=container.image.tags[0] if container.image.tags else container.image.id,
                image_sha=container.image.id,
                namespace="default",  # Would extract from Kubernetes
                pod_name="",  # Would extract from Kubernetes
                labels=container.labels or {},
                security_context={},  # Would extract from runtime
                resource_limits={},  # Would extract from container config
                network_mode=container.attrs.get('HostConfig', {}).get('NetworkMode', ''),
                volumes=[],  # Would extract volume mounts
                created_at=datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')),
                started_at=datetime.fromisoformat(container.attrs['State']['StartedAt'].replace('Z', '+00:00'))
            )
            
            await self._store_container_info(container_info)
            
        except Exception as e:
            logger.error(f"Error updating container info for {container.id}: {e}")
    
    async def _store_container_info(self, container_info: ContainerInfo):
        """Store container information"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO containers 
                (container_id, name, image, image_sha, namespace, pod_name,
                 labels, security_context, resource_limits, network_mode,
                 volumes, created_at, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (container_id) DO UPDATE SET
                    last_seen = NOW(),
                    status = 'running'
            """, 
                container_info.container_id, container_info.name,
                container_info.image, container_info.image_sha,
                container_info.namespace, container_info.pod_name,
                json.dumps(container_info.labels),
                json.dumps(container_info.security_context),
                json.dumps(container_info.resource_limits),
                container_info.network_mode,
                json.dumps(container_info.volumes),
                container_info.created_at, container_info.started_at
            )
    
    async def _monitor_processes(self):
        """Monitor process execution in containers"""
        while True:
            try:
                # Get running containers
                async with self.db_pool.acquire() as conn:
                    containers = await conn.fetch("""
                        SELECT container_id FROM containers 
                        WHERE status = 'running'
                        AND last_seen > NOW() - INTERVAL '5 minutes'
                    """)
                
                for container_row in containers:
                    container_id = container_row['container_id']
                    await self._monitor_container_processes(container_id)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring processes: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_container_processes(self, container_id: str):
        """Monitor processes in a specific container"""
        try:
            # Get container process list (simplified - would use runtime APIs)
            container = self.docker_client.containers.get(container_id)
            
            # Simulate process monitoring (in production would use runtime hooks)
            processes = self._get_simulated_processes(container_id)
            
            for process_info in processes:
                process_event = ProcessEvent(
                    event_id=f"proc_{container_id}_{process_info['pid']}_{int(datetime.now().timestamp())}",
                    container_id=container_id,
                    process_id=process_info['pid'],
                    parent_process_id=process_info.get('ppid', 0),
                    process_name=process_info['name'],
                    command_line=process_info.get('cmdline', ''),
                    user_id=process_info.get('uid', 0),
                    group_id=process_info.get('gid', 0),
                    working_directory=process_info.get('cwd', '/'),
                    environment_vars=process_info.get('env', {}),
                    file_descriptors=process_info.get('fds', []),
                    capabilities=process_info.get('caps', []),
                    timestamp=datetime.now()
                )
                
                await self._analyze_process_event(process_event)
                
        except Exception as e:
            logger.error(f"Error monitoring container processes {container_id}: {e}")
    
    def _get_simulated_processes(self, container_id: str) -> List[Dict[str, Any]]:
        """Get simulated process list (mock implementation)"""
        # In production, would integrate with container runtime APIs
        # or use eBPF/kernel modules for real-time process monitoring
        
        normal_processes = [
            {'pid': 1, 'name': '/app/main', 'cmdline': '/app/main --config /etc/app.conf', 'uid': 1000, 'gid': 1000},
            {'pid': 15, 'name': '/usr/bin/python3', 'cmdline': 'python3 /app/worker.py', 'uid': 1000, 'gid': 1000}
        ]
        
        # Occasionally simulate suspicious process
        if np.random.random() < 0.1:  # 10% chance
            suspicious_process = {
                'pid': np.random.randint(100, 1000),
                'name': '/usr/bin/nc',
                'cmdline': 'nc -l -p 4444',
                'uid': 0,  # Running as root
                'gid': 0,
                'cwd': '/tmp',
                'env': {'PATH': '/bin:/usr/bin'},
                'fds': ['/dev/tcp/192.168.1.100/4444'],
                'caps': ['CAP_NET_BIND_SERVICE']
            }
            normal_processes.append(suspicious_process)
        
        return normal_processes
    
    @logfire.instrument("Analyze Process Event")
    async def _analyze_process_event(self, event: ProcessEvent):
        """Analyze process event for anomalies"""
        with logfire.span("process_analysis", container_id=event.container_id):
            start_time = datetime.now()
            anomalies = []
            
            # Store the event
            await self._store_process_event(event)
            
            # Check against baseline
            baseline_anomalies = await self._check_process_baseline(event)
            anomalies.extend(baseline_anomalies)
            
            # ML-based detection
            ml_anomalies = await self._detect_process_ml_anomalies(event)
            anomalies.extend(ml_anomalies)
            
            # Rule-based detection
            rule_anomalies = await self._detect_process_rule_anomalies(event)
            anomalies.extend(rule_anomalies)
            
            # Store anomalies
            for anomaly in anomalies:
                await self._store_runtime_anomaly(anomaly)
                
                # Update metrics
                RUNTIME_ANOMALIES_DETECTED.labels(
                    anomaly_type=anomaly.anomaly_type.value,
                    container_id=event.container_id
                ).inc()
                
                # Take immediate action for critical anomalies
                if anomaly.severity == AnomalySeverity.CRITICAL:
                    await self._handle_critical_anomaly(anomaly)
            
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            PROCESS_MONITORING_LATENCY.labels(monitor_type="process").observe(processing_time)
            
            logfire.info(
                "Process event analyzed",
                container_id=event.container_id,
                process_name=event.process_name,
                anomalies_detected=len(anomalies)
            )
    
    async def _check_process_baseline(self, event: ProcessEvent) -> List[RuntimeAnomaly]:
        """Check process against baseline behavior"""
        anomalies = []
        
        baseline = self.container_baselines.get(event.container_id)
        if not baseline:
            # Create initial baseline
            await self._create_container_baseline(event.container_id)
            return anomalies
        
        normal_processes = baseline.get('normal_processes', [])
        
        # Check if process is in baseline
        if event.process_name not in normal_processes:
            anomaly = RuntimeAnomaly(
                anomaly_id=f"baseline_{event.event_id}",
                container_id=event.container_id,
                anomaly_type=SecurityEventType.PROCESS_ANOMALY,
                severity=AnomalySeverity.MEDIUM,
                confidence_score=0.7,
                detected_at=event.timestamp,
                related_events=[event.event_id],
                behavioral_indicators=["unknown_process"],
                baseline_deviation={"process_deviation": 1.0},
                threat_assessment={"risk_level": "medium", "process_legitimacy": "unknown"},
                recommended_actions=["investigate_process", "check_process_origin"],
                context={
                    "detection_method": "baseline_comparison",
                    "process_name": event.process_name,
                    "known_processes": normal_processes
                }
            )
            anomalies.append(anomaly)
        
        return anomalies
    
    async def _detect_process_rule_anomalies(self, event: ProcessEvent) -> List[RuntimeAnomaly]:
        """Detect process anomalies using rules"""
        anomalies = []
        
        # Check for suspicious processes
        if event.process_name in self.suspicious_processes:
            anomaly = RuntimeAnomaly(
                anomaly_id=f"rule_suspicious_{event.event_id}",
                container_id=event.container_id,
                anomaly_type=SecurityEventType.PROCESS_ANOMALY,
                severity=AnomalySeverity.HIGH,
                confidence_score=0.9,
                detected_at=event.timestamp,
                related_events=[event.event_id],
                behavioral_indicators=["suspicious_binary"],
                baseline_deviation={},
                threat_assessment={"risk_level": "high", "threat_type": "potential_backdoor"},
                recommended_actions=["block_process", "investigate_container", "alert_security_team"],
                context={
                    "detection_method": "rule_based",
                    "rule": "suspicious_process_detection",
                    "process_name": event.process_name
                }
            )
            anomalies.append(anomaly)
            
            # Update metrics
            SUSPICIOUS_PROCESSES_BLOCKED.labels(
                container_id=event.container_id,
                process_name=event.process_name
            ).inc()
        
        # Check for privilege escalation
        if event.user_id == 0 and event.process_name not in ['/bin/bash', '/bin/sh']:
            anomaly = RuntimeAnomaly(
                anomaly_id=f"rule_privesc_{event.event_id}",
                container_id=event.container_id,
                anomaly_type=SecurityEventType.PRIVILEGE_ESCALATION,
                severity=AnomalySeverity.CRITICAL,
                confidence_score=0.85,
                detected_at=event.timestamp,
                related_events=[event.event_id],
                behavioral_indicators=["root_execution", "privilege_escalation"],
                baseline_deviation={},
                threat_assessment={"risk_level": "critical", "threat_type": "privilege_escalation"},
                recommended_actions=["terminate_process", "isolate_container", "investigate_compromise"],
                context={
                    "detection_method": "rule_based",
                    "rule": "privilege_escalation_detection",
                    "user_id": event.user_id,
                    "process_name": event.process_name
                }
            )
            anomalies.append(anomaly)
        
        return anomalies

# Continue with remaining monitoring methods...

# Global container runtime monitor instance
container_monitor = ContainerRuntimeMonitor()

# Initialize container runtime monitoring
async def initialize_container_runtime_monitoring():
    """Initialize container runtime monitoring system"""
    await container_monitor.initialize()
    logfire.info("Container runtime monitoring system ready")