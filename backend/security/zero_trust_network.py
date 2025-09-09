"""
Zero-Trust Network Policy Enforcement System
Dynamic, context-aware network policy enforcement with continuous verification
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
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logfire
from prometheus_client import Counter, Histogram, Gauge
import redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Prometheus metrics
NETWORK_POLICIES_ENFORCED = Counter(
    'network_policies_enforced_total',
    'Total number of network policies enforced',
    ['policy_type', 'namespace', 'action']
)

POLICY_VIOLATIONS_BLOCKED = Counter(
    'policy_violations_blocked_total',
    'Number of policy violations blocked',
    ['source_namespace', 'destination_namespace', 'violation_type']
)

TRUST_SCORE_GAUGE = Gauge(
    'trust_score',
    'Current trust score for workloads',
    ['namespace', 'workload', 'workload_type']
)

POLICY_EVALUATION_LATENCY = Histogram(
    'policy_evaluation_latency_seconds',
    'Time taken to evaluate network policies',
    ['policy_engine']
)

ZERO_TRUST_VIOLATIONS = Counter(
    'zero_trust_violations_total',
    'Total zero-trust principle violations',
    ['violation_type', 'severity']
)

class TrustLevel(str, Enum):
    """Trust levels for workloads"""
    TRUSTED = "trusted"
    CONDITIONAL = "conditional"
    UNTRUSTED = "untrusted"
    QUARANTINED = "quarantined"

class PolicyAction(str, Enum):
    """Network policy actions"""
    ALLOW = "allow"
    DENY = "deny"
    LOG = "log"
    QUARANTINE = "quarantine"
    RATE_LIMIT = "rate_limit"

class TrafficType(str, Enum):
    """Types of network traffic"""
    INTER_NAMESPACE = "inter_namespace"
    INTRA_NAMESPACE = "intra_namespace"
    EGRESS_EXTERNAL = "egress_external"
    INGRESS_EXTERNAL = "ingress_external"
    CLUSTER_INTERNAL = "cluster_internal"

@dataclass
class WorkloadIdentity:
    """Workload identity and context"""
    namespace: str
    workload_name: str
    workload_type: str  # deployment, pod, service
    labels: Dict[str, str]
    service_account: str
    security_context: Dict[str, Any]
    image_digests: List[str]
    trust_level: TrustLevel
    trust_score: float
    last_verified: datetime

@dataclass
class NetworkRequest:
    """Network access request"""
    request_id: str
    timestamp: datetime
    source_workload: WorkloadIdentity
    destination_workload: Optional[WorkloadIdentity]
    destination_ip: str
    destination_port: int
    protocol: str
    traffic_type: TrafficType
    context: Dict[str, Any]

@dataclass
class NetworkPolicy:
    """Zero-trust network policy"""
    policy_id: str
    name: str
    namespace: str
    policy_type: str
    source_selector: Dict[str, Any]
    destination_selector: Dict[str, Any]
    allowed_ports: List[Dict[str, Any]]
    conditions: List[Dict[str, Any]]
    action: PolicyAction
    trust_requirements: Dict[str, Any]
    temporal_constraints: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class PolicyDecision:
    """Network policy decision"""
    decision_id: str
    request: NetworkRequest
    decision: PolicyAction
    matched_policies: List[str]
    trust_evaluation: Dict[str, Any]
    conditions_evaluated: List[Dict[str, Any]]
    confidence_score: float
    reasoning: List[str]
    additional_actions: List[str]
    decided_at: datetime

class ZeroTrustNetworkEnforcer:
    """Zero-trust network policy enforcement system"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=7)
        
        # Kubernetes client
        try:
            config.load_incluster_config()
        except:
            try:
                config.load_kube_config()
            except:
                logger.warning("Could not load Kubernetes config")
        
        self.k8s_v1 = client.CoreV1Api()
        self.k8s_networking = client.NetworkingV1Api()
        self.k8s_apps = client.AppsV1Api()
        
        # Trust scoring components
        self.workload_trust_scores: Dict[str, float] = {}
        self.trust_factors = {
            'image_signature_verified': 0.3,
            'vulnerability_scan_passed': 0.2,
            'security_context_compliant': 0.2,
            'behavioral_analysis_clean': 0.15,
            'compliance_verified': 0.15
        }
        
        # Policy engine state
        self.active_policies: Dict[str, NetworkPolicy] = {}
        self.policy_cache: Dict[str, PolicyDecision] = {}
        self.blocked_communications: Set[Tuple[str, str]] = set()
        
        # Zero-trust principles
        self.default_deny_all = True
        self.require_explicit_trust = True
        self.continuous_verification = True
        self.least_privilege_access = True
        
    async def initialize(self):
        """Initialize zero-trust network enforcement system"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/zero_trust_network",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_existing_policies()
        await self._discover_workloads()
        await self._start_policy_enforcement()
        await self._start_trust_evaluation()
        
        logfire.info("Zero-trust network enforcement system initialized")
    
    async def _create_tables(self):
        """Create zero-trust network database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workload_identities (
                    workload_id VARCHAR PRIMARY KEY,
                    namespace VARCHAR NOT NULL,
                    workload_name VARCHAR NOT NULL,
                    workload_type VARCHAR NOT NULL,
                    labels JSONB,
                    service_account VARCHAR,
                    security_context JSONB,
                    image_digests JSONB,
                    trust_level VARCHAR NOT NULL,
                    trust_score FLOAT NOT NULL,
                    last_verified TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_policies (
                    policy_id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    namespace VARCHAR NOT NULL,
                    policy_type VARCHAR NOT NULL,
                    source_selector JSONB,
                    destination_selector JSONB,
                    allowed_ports JSONB,
                    conditions JSONB,
                    action VARCHAR NOT NULL,
                    trust_requirements JSONB,
                    temporal_constraints JSONB,
                    metadata JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS network_requests (
                    request_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    source_workload_id VARCHAR,
                    destination_workload_id VARCHAR,
                    destination_ip INET NOT NULL,
                    destination_port INTEGER NOT NULL,
                    protocol VARCHAR NOT NULL,
                    traffic_type VARCHAR NOT NULL,
                    context JSONB,
                    decision VARCHAR NOT NULL,
                    matched_policies JSONB,
                    trust_evaluation JSONB,
                    conditions_evaluated JSONB,
                    confidence_score FLOAT,
                    reasoning JSONB,
                    additional_actions JSONB,
                    processing_time_ms FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS trust_evaluations (
                    evaluation_id VARCHAR PRIMARY KEY,
                    workload_id VARCHAR NOT NULL,
                    evaluation_timestamp TIMESTAMP NOT NULL,
                    trust_factors JSONB,
                    trust_score FLOAT NOT NULL,
                    trust_level VARCHAR NOT NULL,
                    risk_indicators JSONB,
                    verification_results JSONB,
                    next_evaluation TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS policy_violations (
                    violation_id VARCHAR PRIMARY KEY,
                    request_id VARCHAR REFERENCES network_requests(request_id),
                    violation_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    source_workload_id VARCHAR,
                    destination_info JSONB,
                    policy_context JSONB,
                    detected_at TIMESTAMP NOT NULL,
                    mitigation_actions JSONB,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_workload_identities_namespace ON workload_identities(namespace);
                CREATE INDEX IF NOT EXISTS idx_workload_identities_trust_level ON workload_identities(trust_level);
                CREATE INDEX IF NOT EXISTS idx_network_policies_namespace ON network_policies(namespace);
                CREATE INDEX IF NOT EXISTS idx_network_requests_timestamp ON network_requests(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trust_evaluations_workload_id ON trust_evaluations(workload_id);
                CREATE INDEX IF NOT EXISTS idx_policy_violations_detected_at ON policy_violations(detected_at);
            """)
    
    async def _load_existing_policies(self):
        """Load existing network policies"""
        async with self.db_pool.acquire() as conn:
            policies = await conn.fetch("SELECT * FROM network_policies WHERE is_active = TRUE")
            
            for policy_data in policies:
                policy = NetworkPolicy(
                    policy_id=policy_data['policy_id'],
                    name=policy_data['name'],
                    namespace=policy_data['namespace'],
                    policy_type=policy_data['policy_type'],
                    source_selector=policy_data['source_selector'] or {},
                    destination_selector=policy_data['destination_selector'] or {},
                    allowed_ports=policy_data['allowed_ports'] or [],
                    conditions=policy_data['conditions'] or [],
                    action=PolicyAction(policy_data['action']),
                    trust_requirements=policy_data['trust_requirements'] or {},
                    temporal_constraints=policy_data['temporal_constraints'] or {},
                    metadata=policy_data['metadata'] or {},
                    created_at=policy_data['created_at'],
                    updated_at=policy_data['updated_at']
                )
                self.active_policies[policy.policy_id] = policy
    
    async def _discover_workloads(self):
        """Discover and catalog workloads in the cluster"""
        try:
            # Get all namespaces
            namespaces = self.k8s_v1.list_namespace()
            
            for namespace in namespaces.items:
                if namespace.metadata.name in ['kube-system', 'kube-public']:
                    continue  # Skip system namespaces
                
                await self._catalog_namespace_workloads(namespace.metadata.name)
                
        except Exception as e:
            logger.error(f"Error discovering workloads: {e}")
    
    async def _catalog_namespace_workloads(self, namespace: str):
        """Catalog workloads in a specific namespace"""
        try:
            # Get deployments
            deployments = self.k8s_apps.list_namespaced_deployment(namespace)
            for deployment in deployments.items:
                await self._register_workload(
                    namespace=namespace,
                    workload_name=deployment.metadata.name,
                    workload_type="deployment",
                    labels=deployment.metadata.labels or {},
                    spec=deployment.spec
                )
            
            # Get pods
            pods = self.k8s_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                if pod.metadata.owner_references:
                    continue  # Skip pods owned by deployments
                
                await self._register_workload(
                    namespace=namespace,
                    workload_name=pod.metadata.name,
                    workload_type="pod",
                    labels=pod.metadata.labels or {},
                    spec=pod.spec
                )
                
        except Exception as e:
            logger.error(f"Error cataloging workloads in namespace {namespace}: {e}")
    
    async def _register_workload(self, namespace: str, workload_name: str, 
                               workload_type: str, labels: Dict[str, str], spec: Any):
        """Register a workload in the system"""
        workload_id = f"{namespace}:{workload_type}:{workload_name}"
        
        # Extract security context and image information
        security_context = {}
        image_digests = []
        service_account = "default"
        
        if hasattr(spec, 'template') and spec.template.spec:
            containers = spec.template.spec.containers or []
            service_account = spec.template.spec.service_account_name or "default"
            if hasattr(spec.template.spec, 'security_context'):
                security_context = asdict(spec.template.spec.security_context) if spec.template.spec.security_context else {}
        elif hasattr(spec, 'containers'):
            containers = spec.containers or []
            service_account = spec.service_account_name or "default"
            if hasattr(spec, 'security_context'):
                security_context = asdict(spec.security_context) if spec.security_context else {}
        else:
            containers = []
        
        for container in containers:
            if hasattr(container, 'image'):
                image_digests.append(container.image)
        
        # Calculate initial trust score
        trust_score = await self._calculate_initial_trust_score(
            namespace, workload_name, security_context, image_digests
        )
        trust_level = self._determine_trust_level(trust_score)
        
        workload = WorkloadIdentity(
            namespace=namespace,
            workload_name=workload_name,
            workload_type=workload_type,
            labels=labels,
            service_account=service_account,
            security_context=security_context,
            image_digests=image_digests,
            trust_level=trust_level,
            trust_score=trust_score,
            last_verified=datetime.now()
        )
        
        await self._store_workload_identity(workload_id, workload)
        
        # Update metrics
        TRUST_SCORE_GAUGE.labels(
            namespace=namespace,
            workload=workload_name,
            workload_type=workload_type
        ).set(trust_score)
    
    async def _calculate_initial_trust_score(self, namespace: str, workload_name: str,
                                           security_context: Dict[str, Any],
                                           image_digests: List[str]) -> float:
        """Calculate initial trust score for workload"""
        score = 0.0
        
        # Check security context compliance
        if security_context:
            if security_context.get('runAsNonRoot', False):
                score += self.trust_factors['security_context_compliant'] * 0.5
            if security_context.get('readOnlyRootFilesystem', False):
                score += self.trust_factors['security_context_compliant'] * 0.3
            if not security_context.get('privileged', False):
                score += self.trust_factors['security_context_compliant'] * 0.2
        
        # Check image signatures (mock implementation)
        verified_images = 0
        for image in image_digests:
            if await self._verify_image_signature(image):
                verified_images += 1
        
        if image_digests:
            image_trust = (verified_images / len(image_digests)) * self.trust_factors['image_signature_verified']
            score += image_trust
        
        # Check vulnerability scans (mock implementation)
        if await self._check_vulnerability_scan_status(workload_name):
            score += self.trust_factors['vulnerability_scan_passed']
        
        # Default compliance score for new workloads
        score += self.trust_factors['compliance_verified'] * 0.5
        
        return min(1.0, score)
    
    async def _verify_image_signature(self, image: str) -> bool:
        """Verify image signature (mock implementation)"""
        # In production, would integrate with image signing verification
        return not ('latest' in image or ':dev' in image)
    
    async def _check_vulnerability_scan_status(self, workload_name: str) -> bool:
        """Check vulnerability scan status (mock implementation)"""
        # In production, would integrate with vulnerability scanning systems
        return True
    
    def _determine_trust_level(self, trust_score: float) -> TrustLevel:
        """Determine trust level based on trust score"""
        if trust_score >= 0.8:
            return TrustLevel.TRUSTED
        elif trust_score >= 0.6:
            return TrustLevel.CONDITIONAL
        elif trust_score >= 0.3:
            return TrustLevel.UNTRUSTED
        else:
            return TrustLevel.QUARANTINED
    
    async def _store_workload_identity(self, workload_id: str, workload: WorkloadIdentity):
        """Store workload identity"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO workload_identities 
                (workload_id, namespace, workload_name, workload_type, labels,
                 service_account, security_context, image_digests, trust_level,
                 trust_score, last_verified)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (workload_id) DO UPDATE SET
                    labels = EXCLUDED.labels,
                    security_context = EXCLUDED.security_context,
                    image_digests = EXCLUDED.image_digests,
                    trust_level = EXCLUDED.trust_level,
                    trust_score = EXCLUDED.trust_score,
                    last_verified = EXCLUDED.last_verified,
                    updated_at = NOW()
            """, 
                workload_id, workload.namespace, workload.workload_name,
                workload.workload_type, json.dumps(workload.labels),
                workload.service_account, json.dumps(workload.security_context),
                json.dumps(workload.image_digests), workload.trust_level.value,
                workload.trust_score, workload.last_verified
            )
    
    async def _start_policy_enforcement(self):
        """Start policy enforcement tasks"""
        asyncio.create_task(self._enforce_default_deny_policies())
        asyncio.create_task(self._monitor_network_traffic())
        asyncio.create_task(self._update_kubernetes_policies())
    
    async def _start_trust_evaluation(self):
        """Start continuous trust evaluation"""
        asyncio.create_task(self._continuous_trust_evaluation())
    
    @logfire.instrument("Evaluate Network Request")
    async def evaluate_network_request(self, request: NetworkRequest) -> PolicyDecision:
        """Evaluate network request against zero-trust policies"""
        with logfire.span("policy_evaluation", request_id=request.request_id):
            start_time = datetime.now()
            
            # Check cache first
            cache_key = self._generate_cache_key(request)
            cached_decision = await self._get_cached_decision(cache_key)
            if cached_decision:
                return cached_decision
            
            # Evaluate trust levels
            trust_evaluation = await self._evaluate_trust_levels(request)
            
            # Find matching policies
            matched_policies = await self._find_matching_policies(request)
            
            # Evaluate conditions
            conditions_result = await self._evaluate_conditions(request, matched_policies)
            
            # Make decision
            decision = await self._make_policy_decision(
                request, matched_policies, trust_evaluation, conditions_result
            )
            
            # Store decision
            await self._store_network_request_decision(decision)
            
            # Cache decision
            await self._cache_decision(cache_key, decision)
            
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            POLICY_EVALUATION_LATENCY.labels(policy_engine="zero_trust").observe(processing_time)
            
            NETWORK_POLICIES_ENFORCED.labels(
                policy_type="zero_trust",
                namespace=request.source_workload.namespace,
                action=decision.decision.value
            ).inc()
            
            if decision.decision == PolicyAction.DENY:
                POLICY_VIOLATIONS_BLOCKED.labels(
                    source_namespace=request.source_workload.namespace,
                    destination_namespace=request.destination_workload.namespace if request.destination_workload else "external",
                    violation_type="zero_trust_deny"
                ).inc()
            
            logfire.info(
                "Network request evaluated",
                request_id=request.request_id,
                decision=decision.decision.value,
                confidence_score=decision.confidence_score,
                processing_time_ms=processing_time * 1000
            )
            
            return decision
    
    def _generate_cache_key(self, request: NetworkRequest) -> str:
        """Generate cache key for request"""
        key_data = f"{request.source_workload.namespace}:{request.source_workload.workload_name}:{request.destination_ip}:{request.destination_port}:{request.protocol}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def _evaluate_trust_levels(self, request: NetworkRequest) -> Dict[str, Any]:
        """Evaluate trust levels for request"""
        evaluation = {
            'source_trust_score': request.source_workload.trust_score,
            'source_trust_level': request.source_workload.trust_level.value,
            'destination_trust_score': 0.0,
            'destination_trust_level': TrustLevel.UNTRUSTED.value,
            'trust_requirement_met': False
        }
        
        if request.destination_workload:
            evaluation['destination_trust_score'] = request.destination_workload.trust_score
            evaluation['destination_trust_level'] = request.destination_workload.trust_level.value
        
        # Check if minimum trust requirements are met
        min_trust_required = 0.6  # Configurable threshold
        evaluation['trust_requirement_met'] = (
            request.source_workload.trust_score >= min_trust_required and
            (not request.destination_workload or 
             request.destination_workload.trust_score >= min_trust_required)
        )
        
        return evaluation
    
    async def _find_matching_policies(self, request: NetworkRequest) -> List[NetworkPolicy]:
        """Find policies that match the network request"""
        matching_policies = []
        
        for policy in self.active_policies.values():
            if await self._policy_matches_request(policy, request):
                matching_policies.append(policy)
        
        # Sort by specificity (more specific policies first)
        matching_policies.sort(key=lambda p: self._calculate_policy_specificity(p), reverse=True)
        
        return matching_policies
    
    async def _policy_matches_request(self, policy: NetworkPolicy, request: NetworkRequest) -> bool:
        """Check if policy matches request"""
        # Check namespace
        if policy.namespace != request.source_workload.namespace and policy.namespace != "default":
            return False
        
        # Check source selector
        if not self._selector_matches_workload(policy.source_selector, request.source_workload):
            return False
        
        # Check destination selector
        if request.destination_workload:
            if not self._selector_matches_workload(policy.destination_selector, request.destination_workload):
                return False
        
        # Check port and protocol
        if not self._port_matches_policy(policy.allowed_ports, request.destination_port, request.protocol):
            return False
        
        return True
    
    def _selector_matches_workload(self, selector: Dict[str, Any], workload: WorkloadIdentity) -> bool:
        """Check if selector matches workload"""
        if not selector:
            return True  # Empty selector matches all
        
        # Check label selectors
        match_labels = selector.get('matchLabels', {})
        for key, value in match_labels.items():
            if workload.labels.get(key) != value:
                return False
        
        # Check workload type
        if 'workloadType' in selector:
            if selector['workloadType'] != workload.workload_type:
                return False
        
        # Check service account
        if 'serviceAccount' in selector:
            if selector['serviceAccount'] != workload.service_account:
                return False
        
        return True
    
    def _port_matches_policy(self, allowed_ports: List[Dict[str, Any]], 
                           port: int, protocol: str) -> bool:
        """Check if port and protocol match policy"""
        if not allowed_ports:
            return False  # No ports allowed
        
        for port_rule in allowed_ports:
            if port_rule.get('protocol', '').lower() == protocol.lower():
                if 'port' in port_rule:
                    if port_rule['port'] == port:
                        return True
                elif 'portRange' in port_rule:
                    port_range = port_rule['portRange']
                    if port_range['from'] <= port <= port_range['to']:
                        return True
        
        return False
    
    def _calculate_policy_specificity(self, policy: NetworkPolicy) -> int:
        """Calculate policy specificity score"""
        specificity = 0
        
        # More specific selectors get higher scores
        specificity += len(policy.source_selector.get('matchLabels', {})) * 10
        specificity += len(policy.destination_selector.get('matchLabels', {})) * 10
        
        # Specific ports get higher scores
        specificity += len(policy.allowed_ports) * 5
        
        # Conditions add specificity
        specificity += len(policy.conditions) * 3
        
        return specificity
    
    async def _make_policy_decision(self, request: NetworkRequest,
                                  matched_policies: List[NetworkPolicy],
                                  trust_evaluation: Dict[str, Any],
                                  conditions_result: Dict[str, Any]) -> PolicyDecision:
        """Make final policy decision"""
        decision_id = f"decision_{request.request_id}_{int(datetime.now().timestamp())}"
        
        # Default deny principle
        final_decision = PolicyAction.DENY
        confidence_score = 1.0
        reasoning = ["default_deny_all"]
        additional_actions = []
        
        # Check if any policy allows the request
        for policy in matched_policies:
            if policy.action == PolicyAction.ALLOW:
                # Check trust requirements
                if self._check_trust_requirements(policy, trust_evaluation):
                    # Check temporal constraints
                    if self._check_temporal_constraints(policy):
                        final_decision = PolicyAction.ALLOW
                        reasoning = [f"allowed_by_policy_{policy.name}"]
                        break
                else:
                    reasoning.append(f"trust_requirement_failed_{policy.name}")
            elif policy.action == PolicyAction.QUARANTINE:
                final_decision = PolicyAction.QUARANTINE
                additional_actions.append("isolate_workload")
                reasoning.append(f"quarantined_by_policy_{policy.name}")
            elif policy.action == PolicyAction.RATE_LIMIT:
                if final_decision != PolicyAction.ALLOW:
                    final_decision = PolicyAction.RATE_LIMIT
                additional_actions.append("apply_rate_limiting")
                reasoning.append(f"rate_limited_by_policy_{policy.name}")
        
        # Adjust confidence based on trust scores
        if trust_evaluation['trust_requirement_met']:
            confidence_score *= 0.9
        else:
            confidence_score *= 1.0
        
        # Create decision
        decision = PolicyDecision(
            decision_id=decision_id,
            request=request,
            decision=final_decision,
            matched_policies=[p.policy_id for p in matched_policies],
            trust_evaluation=trust_evaluation,
            conditions_evaluated=[conditions_result],
            confidence_score=confidence_score,
            reasoning=reasoning,
            additional_actions=additional_actions,
            decided_at=datetime.now()
        )
        
        return decision
    
    def _check_trust_requirements(self, policy: NetworkPolicy, 
                                trust_evaluation: Dict[str, Any]) -> bool:
        """Check if trust requirements are met"""
        requirements = policy.trust_requirements
        
        if not requirements:
            return True
        
        min_source_trust = requirements.get('minSourceTrustScore', 0.0)
        min_dest_trust = requirements.get('minDestinationTrustScore', 0.0)
        
        return (
            trust_evaluation['source_trust_score'] >= min_source_trust and
            trust_evaluation['destination_trust_score'] >= min_dest_trust
        )
    
    def _check_temporal_constraints(self, policy: NetworkPolicy) -> bool:
        """Check temporal constraints"""
        constraints = policy.temporal_constraints
        
        if not constraints:
            return True
        
        now = datetime.now()
        
        # Check time of day
        if 'allowedHours' in constraints:
            allowed_hours = constraints['allowedHours']
            if now.hour < allowed_hours['start'] or now.hour > allowed_hours['end']:
                return False
        
        # Check days of week
        if 'allowedDays' in constraints:
            allowed_days = constraints['allowedDays']
            if now.weekday() not in allowed_days:
                return False
        
        return True

# Continue with remaining enforcement methods...

# Global zero-trust network enforcer instance
zero_trust_enforcer = ZeroTrustNetworkEnforcer()

# Initialize zero-trust network enforcement
async def initialize_zero_trust_network_enforcement():
    """Initialize zero-trust network enforcement system"""
    await zero_trust_enforcer.initialize()
    logfire.info("Zero-trust network enforcement system ready")