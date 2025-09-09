"""
Advanced Compliance Status Monitoring System
Real-time compliance tracking across multiple frameworks with automated reporting
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logfire
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import redis
import yaml

# Configure compliance monitoring logger
logger = logging.getLogger(__name__)

# Prometheus metrics
COMPLIANCE_CHECKS_TOTAL = Counter(
    'compliance_checks_total',
    'Total number of compliance checks performed',
    ['framework', 'control', 'status']
)

COMPLIANCE_SCORE_GAUGE = Gauge(
    'compliance_score_percentage',
    'Current compliance score percentage',
    ['framework']
)

COMPLIANCE_VIOLATIONS = Counter(
    'compliance_violations_total',
    'Total compliance violations detected',
    ['framework', 'control', 'severity']
)

COMPLIANCE_REMEDIATION_TIME = Histogram(
    'compliance_remediation_duration_seconds',
    'Time taken to remediate compliance violations',
    ['framework', 'control']
)

class ComplianceFramework(str, Enum):
    """Supported compliance frameworks"""
    SOC2 = "soc2"
    CIS_K8S = "cis_k8s"
    NIST = "nist"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    HIPAA = "hipaa"

class ComplianceStatus(str, Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNDER_REVIEW = "under_review"

class ViolationSeverity(str, Enum):
    """Severity levels for compliance violations"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class ComplianceControl:
    """Individual compliance control definition"""
    control_id: str
    framework: ComplianceFramework
    title: str
    description: str
    requirements: List[str]
    test_procedures: List[str]
    automation_available: bool
    remediation_guidance: str
    business_impact: str
    frequency: str  # daily, weekly, monthly, quarterly
    
@dataclass
class ComplianceCheck:
    """Result of a compliance check"""
    check_id: str
    control: ComplianceControl
    timestamp: datetime
    status: ComplianceStatus
    score: float  # 0-100
    findings: List[str]
    evidence: List[str]
    remediation_required: bool
    estimated_effort: str
    next_check_date: datetime
    
@dataclass
class ComplianceViolation:
    """Compliance violation record"""
    violation_id: str
    control_id: str
    framework: ComplianceFramework
    severity: ViolationSeverity
    description: str
    discovered_date: datetime
    remediation_date: Optional[datetime]
    status: str
    assigned_to: Optional[str]
    evidence: List[str]
    business_impact: str
    remediation_plan: Optional[str]

class ComplianceMonitor:
    """Advanced compliance monitoring and reporting system"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=1)
        self.frameworks = {}
        self.controls = {}
        self._load_compliance_frameworks()
    
    async def initialize(self):
        """Initialize compliance monitoring system"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/compliance",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_controls_from_db()
        
        logfire.info("Compliance monitoring system initialized")
    
    def _load_compliance_frameworks(self):
        """Load compliance framework definitions"""
        frameworks_config = {
            ComplianceFramework.SOC2: {
                "name": "SOC 2 Type II",
                "version": "2017",
                "description": "System and Organization Controls for Service Organizations",
                "categories": ["CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9"],
                "reporting_frequency": "quarterly"
            },
            ComplianceFramework.CIS_K8S: {
                "name": "CIS Kubernetes Benchmark",
                "version": "1.7.0",
                "description": "Center for Internet Security Kubernetes Security Benchmark",
                "categories": ["1", "2", "3", "4", "5"],
                "reporting_frequency": "monthly"
            },
            ComplianceFramework.NIST: {
                "name": "NIST Cybersecurity Framework",
                "version": "1.1",
                "description": "Framework for Improving Critical Infrastructure Cybersecurity",
                "categories": ["ID", "PR", "DE", "RS", "RC"],
                "reporting_frequency": "quarterly"
            },
            ComplianceFramework.PCI_DSS: {
                "name": "PCI Data Security Standard",
                "version": "4.0",
                "description": "Payment Card Industry Data Security Standard",
                "categories": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
                "reporting_frequency": "quarterly"
            }
        }
        self.frameworks = frameworks_config
    
    async def _create_tables(self):
        """Create compliance monitoring database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS compliance_controls (
                    control_id VARCHAR PRIMARY KEY,
                    framework VARCHAR NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    requirements JSONB,
                    test_procedures JSONB,
                    automation_available BOOLEAN DEFAULT FALSE,
                    remediation_guidance TEXT,
                    business_impact VARCHAR,
                    frequency VARCHAR DEFAULT 'monthly',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS compliance_checks (
                    check_id VARCHAR PRIMARY KEY,
                    control_id VARCHAR REFERENCES compliance_controls(control_id),
                    timestamp TIMESTAMP NOT NULL,
                    status VARCHAR NOT NULL,
                    score FLOAT DEFAULT 0,
                    findings JSONB,
                    evidence JSONB,
                    remediation_required BOOLEAN DEFAULT FALSE,
                    estimated_effort VARCHAR,
                    next_check_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS compliance_violations (
                    violation_id VARCHAR PRIMARY KEY,
                    control_id VARCHAR REFERENCES compliance_controls(control_id),
                    framework VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    discovered_date TIMESTAMP NOT NULL,
                    remediation_date TIMESTAMP,
                    status VARCHAR DEFAULT 'open',
                    assigned_to VARCHAR,
                    evidence JSONB,
                    business_impact TEXT,
                    remediation_plan TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS compliance_reports (
                    report_id VARCHAR PRIMARY KEY,
                    framework VARCHAR NOT NULL,
                    report_type VARCHAR NOT NULL,
                    generated_date TIMESTAMP NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    overall_score FLOAT,
                    findings JSONB,
                    recommendations JSONB,
                    report_data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_compliance_checks_timestamp ON compliance_checks(timestamp);
                CREATE INDEX IF NOT EXISTS idx_compliance_checks_control ON compliance_checks(control_id);
                CREATE INDEX IF NOT EXISTS idx_compliance_violations_framework ON compliance_violations(framework);
                CREATE INDEX IF NOT EXISTS idx_compliance_violations_status ON compliance_violations(status);
                CREATE INDEX IF NOT EXISTS idx_compliance_reports_framework ON compliance_reports(framework);
            """)
    
    async def _load_controls_from_db(self):
        """Load compliance controls from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM compliance_controls")
            for row in rows:
                control = ComplianceControl(
                    control_id=row['control_id'],
                    framework=ComplianceFramework(row['framework']),
                    title=row['title'],
                    description=row['description'],
                    requirements=row['requirements'] or [],
                    test_procedures=row['test_procedures'] or [],
                    automation_available=row['automation_available'],
                    remediation_guidance=row['remediation_guidance'],
                    business_impact=row['business_impact'],
                    frequency=row['frequency']
                )
                self.controls[control.control_id] = control
    
    @logfire.instrument("Perform Compliance Check")
    async def perform_compliance_check(self, control_id: str) -> ComplianceCheck:
        """Perform a compliance check for a specific control"""
        with logfire.span("compliance_check", control_id=control_id):
            control = self.controls.get(control_id)
            if not control:
                raise ValueError(f"Control {control_id} not found")
            
            # Generate unique check ID
            check_id = f"check_{int(datetime.now().timestamp())}_{control_id}"
            
            # Perform automated compliance check
            status, score, findings, evidence = await self._execute_compliance_test(control)
            
            # Calculate next check date
            next_check = self._calculate_next_check_date(control.frequency)
            
            # Create compliance check record
            check = ComplianceCheck(
                check_id=check_id,
                control=control,
                timestamp=datetime.now(),
                status=status,
                score=score,
                findings=findings,
                evidence=evidence,
                remediation_required=status != ComplianceStatus.COMPLIANT,
                estimated_effort=self._estimate_remediation_effort(findings),
                next_check_date=next_check
            )
            
            # Store check result
            await self._store_compliance_check(check)
            
            # Update metrics
            COMPLIANCE_CHECKS_TOTAL.labels(
                framework=control.framework.value,
                control=control_id,
                status=status.value
            ).inc()
            
            # Handle violations if any
            if status != ComplianceStatus.COMPLIANT:
                await self._handle_compliance_violation(check)
            
            logfire.info(
                "Compliance check completed",
                control_id=control_id,
                status=status.value,
                score=score
            )
            
            return check
    
    async def _execute_compliance_test(self, control: ComplianceControl) -> tuple:
        """Execute automated compliance test for a control"""
        findings = []
        evidence = []
        score = 0.0
        
        try:
            # Execute test procedures based on control type
            if control.framework == ComplianceFramework.SOC2:
                score, findings, evidence = await self._test_soc2_control(control)
            elif control.framework == ComplianceFramework.CIS_K8S:
                score, findings, evidence = await self._test_cis_k8s_control(control)
            elif control.framework == ComplianceFramework.NIST:
                score, findings, evidence = await self._test_nist_control(control)
            elif control.framework == ComplianceFramework.PCI_DSS:
                score, findings, evidence = await self._test_pci_dss_control(control)
            
            # Determine status based on score
            if score >= 95:
                status = ComplianceStatus.COMPLIANT
            elif score >= 80:
                status = ComplianceStatus.PARTIALLY_COMPLIANT
            else:
                status = ComplianceStatus.NON_COMPLIANT
                
        except Exception as e:
            logger.error(f"Error executing compliance test for {control.control_id}: {e}")
            status = ComplianceStatus.UNDER_REVIEW
            findings = [f"Test execution failed: {str(e)}"]
        
        return status, score, findings, evidence
    
    async def _test_soc2_control(self, control: ComplianceControl) -> tuple:
        """Test SOC 2 compliance control"""
        score = 0.0
        findings = []
        evidence = []
        
        # Example SOC 2 CC6.1 - Logical access controls
        if control.control_id == "SOC2_CC6.1":
            # Check RBAC implementation
            rbac_score = await self._check_rbac_implementation()
            
            # Check encryption in transit
            encryption_score = await self._check_encryption_in_transit()
            
            # Check network segmentation
            network_score = await self._check_network_segmentation()
            
            score = (rbac_score + encryption_score + network_score) / 3
            
            if rbac_score < 90:
                findings.append("RBAC implementation needs improvement")
            if encryption_score < 95:
                findings.append("Encryption in transit not fully implemented")
            if network_score < 85:
                findings.append("Network segmentation policies incomplete")
            
            evidence = [
                "RBAC policy scan results",
                "TLS certificate validation",
                "Network policy audit"
            ]
        
        return score, findings, evidence
    
    async def _test_cis_k8s_control(self, control: ComplianceControl) -> tuple:
        """Test CIS Kubernetes Benchmark control"""
        score = 0.0
        findings = []
        evidence = []
        
        # Example CIS 5.1.1 - Cluster admin role usage
        if control.control_id == "CIS_5.1.1":
            # Check cluster admin bindings
            admin_bindings = await self._check_cluster_admin_bindings()
            
            if admin_bindings['count'] == 0:
                score = 100.0
                evidence.append("No cluster-admin bindings found")
            elif admin_bindings['count'] <= 2:
                score = 80.0
                findings.append("Limited cluster-admin usage detected")
                evidence.append(f"Found {admin_bindings['count']} cluster-admin bindings")
            else:
                score = 40.0
                findings.append("Excessive cluster-admin usage")
                evidence.append(f"Found {admin_bindings['count']} cluster-admin bindings")
        
        return score, findings, evidence
    
    async def _test_nist_control(self, control: ComplianceControl) -> tuple:
        """Test NIST Cybersecurity Framework control"""
        score = 0.0
        findings = []
        evidence = []
        
        # Example NIST PR.AC-1 - Identity management
        if control.control_id == "NIST_PR.AC-1":
            # Check service account management
            sa_score = await self._check_service_account_management()
            
            # Check identity verification
            id_score = await self._check_identity_verification()
            
            score = (sa_score + id_score) / 2
            
            if sa_score < 90:
                findings.append("Service account management needs improvement")
            if id_score < 85:
                findings.append("Identity verification processes incomplete")
            
            evidence = [
                "Service account audit results",
                "Identity management system logs"
            ]
        
        return score, findings, evidence
    
    async def _test_pci_dss_control(self, control: ComplianceControl) -> tuple:
        """Test PCI DSS compliance control"""
        score = 0.0
        findings = []
        evidence = []
        
        # Example PCI DSS 2.2.1 - Secure configuration
        if control.control_id == "PCI_2.2.1":
            # Check secure configuration baselines
            config_score = await self._check_secure_configuration()
            
            score = config_score
            
            if config_score < 95:
                findings.append("Configuration baselines need hardening")
            
            evidence = [
                "Configuration compliance scan",
                "Security baseline verification"
            ]
        
        return score, findings, evidence
    
    async def _check_rbac_implementation(self) -> float:
        """Check RBAC implementation quality"""
        # Mock implementation - would integrate with Kubernetes API
        return 92.0
    
    async def _check_encryption_in_transit(self) -> float:
        """Check encryption in transit implementation"""
        # Mock implementation - would check TLS certificates and policies
        return 96.0
    
    async def _check_network_segmentation(self) -> float:
        """Check network segmentation implementation"""
        # Mock implementation - would check network policies
        return 88.0
    
    async def _check_cluster_admin_bindings(self) -> dict:
        """Check cluster admin role bindings"""
        # Mock implementation - would query Kubernetes API
        return {"count": 1, "bindings": ["emergency-admin"]}
    
    async def _check_service_account_management(self) -> float:
        """Check service account management practices"""
        # Mock implementation
        return 94.0
    
    async def _check_identity_verification(self) -> float:
        """Check identity verification processes"""
        # Mock implementation
        return 87.0
    
    async def _check_secure_configuration(self) -> float:
        """Check secure configuration implementation"""
        # Mock implementation
        return 91.0
    
    def _calculate_next_check_date(self, frequency: str) -> datetime:
        """Calculate next check date based on frequency"""
        now = datetime.now()
        if frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "monthly":
            return now + timedelta(days=30)
        elif frequency == "quarterly":
            return now + timedelta(days=90)
        else:
            return now + timedelta(days=30)  # Default monthly
    
    def _estimate_remediation_effort(self, findings: List[str]) -> str:
        """Estimate remediation effort based on findings"""
        if not findings:
            return "None"
        elif len(findings) <= 2:
            return "Low (1-2 days)"
        elif len(findings) <= 5:
            return "Medium (3-7 days)"
        else:
            return "High (1-2 weeks)"
    
    async def _store_compliance_check(self, check: ComplianceCheck):
        """Store compliance check result in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO compliance_checks 
                (check_id, control_id, timestamp, status, score, findings, evidence,
                 remediation_required, estimated_effort, next_check_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                check.check_id, check.control.control_id, check.timestamp,
                check.status.value, check.score, json.dumps(check.findings),
                json.dumps(check.evidence), check.remediation_required,
                check.estimated_effort, check.next_check_date
            )
    
    async def _handle_compliance_violation(self, check: ComplianceCheck):
        """Handle compliance violation"""
        violation_id = f"violation_{int(datetime.now().timestamp())}_{check.control.control_id}"
        
        # Determine severity based on score and framework
        if check.score < 50:
            severity = ViolationSeverity.CRITICAL
        elif check.score < 70:
            severity = ViolationSeverity.HIGH
        elif check.score < 85:
            severity = ViolationSeverity.MEDIUM
        else:
            severity = ViolationSeverity.LOW
        
        violation = ComplianceViolation(
            violation_id=violation_id,
            control_id=check.control.control_id,
            framework=check.control.framework,
            severity=severity,
            description=f"Compliance violation in {check.control.title}",
            discovered_date=check.timestamp,
            remediation_date=None,
            status="open",
            assigned_to=None,
            evidence=check.evidence,
            business_impact=check.control.business_impact,
            remediation_plan=check.control.remediation_guidance
        )
        
        await self._store_compliance_violation(violation)
        
        # Update metrics
        COMPLIANCE_VIOLATIONS.labels(
            framework=violation.framework.value,
            control=violation.control_id,
            severity=violation.severity.value
        ).inc()
        
        logfire.warn(
            "Compliance violation detected",
            violation_id=violation_id,
            control_id=check.control.control_id,
            severity=severity.value
        )
    
    async def _store_compliance_violation(self, violation: ComplianceViolation):
        """Store compliance violation in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO compliance_violations 
                (violation_id, control_id, framework, severity, description,
                 discovered_date, status, evidence, business_impact, remediation_plan)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                violation.violation_id, violation.control_id, violation.framework.value,
                violation.severity.value, violation.description, violation.discovered_date,
                violation.status, json.dumps(violation.evidence), violation.business_impact,
                violation.remediation_plan
            )
    
    @logfire.instrument("Calculate Framework Compliance Score")
    async def calculate_framework_score(self, framework: ComplianceFramework) -> Dict[str, Any]:
        """Calculate overall compliance score for a framework"""
        with logfire.span("framework_score_calculation", framework=framework.value):
            async with self.db_pool.acquire() as conn:
                # Get recent checks for the framework
                checks = await conn.fetch("""
                    SELECT cc.control_id, cc.score, cc.timestamp, ctrl.title
                    FROM compliance_checks cc
                    JOIN compliance_controls ctrl ON cc.control_id = ctrl.control_id
                    WHERE ctrl.framework = $1
                    AND cc.timestamp > NOW() - INTERVAL '30 days'
                    ORDER BY cc.timestamp DESC
                """, framework.value)
                
                if not checks:
                    return {
                        "framework": framework.value,
                        "overall_score": 0.0,
                        "total_controls": 0,
                        "compliant_controls": 0,
                        "last_updated": None
                    }
                
                # Calculate aggregated score
                control_scores = {}
                for check in checks:
                    control_id = check['control_id']
                    if control_id not in control_scores:
                        control_scores[control_id] = check['score']
                
                overall_score = sum(control_scores.values()) / len(control_scores)
                compliant_controls = sum(1 for score in control_scores.values() if score >= 95)
                
                # Update Prometheus metric
                COMPLIANCE_SCORE_GAUGE.labels(framework=framework.value).set(overall_score)
                
                result = {
                    "framework": framework.value,
                    "overall_score": round(overall_score, 2),
                    "total_controls": len(control_scores),
                    "compliant_controls": compliant_controls,
                    "last_updated": max(check['timestamp'] for check in checks).isoformat(),
                    "control_breakdown": [
                        {
                            "control_id": control_id,
                            "score": score,
                            "status": "compliant" if score >= 95 else "non_compliant"
                        }
                        for control_id, score in control_scores.items()
                    ]
                }
                
                logfire.info(
                    "Framework compliance score calculated",
                    framework=framework.value,
                    overall_score=overall_score,
                    total_controls=len(control_scores),
                    compliant_controls=compliant_controls
                )
                
                return result
    
    async def generate_compliance_report(self, framework: ComplianceFramework, 
                                       period_days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Get framework score
        framework_score = await self.calculate_framework_score(framework)
        
        # Get violations
        async with self.db_pool.acquire() as conn:
            violations = await conn.fetch("""
                SELECT * FROM compliance_violations
                WHERE framework = $1
                AND discovered_date BETWEEN $2 AND $3
                ORDER BY severity, discovered_date DESC
            """, framework.value, start_date, end_date)
            
            # Get remediation metrics
            remediation_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_violations,
                    COUNT(CASE WHEN remediation_date IS NOT NULL THEN 1 END) as remediated,
                    AVG(EXTRACT(EPOCH FROM (remediation_date - discovered_date))) as avg_remediation_time
                FROM compliance_violations
                WHERE framework = $1
                AND discovered_date BETWEEN $2 AND $3
            """, framework.value, start_date, end_date)
        
        report = {
            "report_id": f"report_{int(datetime.now().timestamp())}_{framework.value}",
            "framework": framework.value,
            "framework_info": self.frameworks[framework],
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": period_days
            },
            "compliance_score": framework_score,
            "violations": {
                "total": remediation_stats['total_violations'],
                "remediated": remediation_stats['remediated'],
                "open": remediation_stats['total_violations'] - (remediation_stats['remediated'] or 0),
                "avg_remediation_time_hours": (remediation_stats['avg_remediation_time'] or 0) / 3600,
                "details": [dict(v) for v in violations]
            },
            "recommendations": self._generate_recommendations(framework_score, violations),
            "generated_at": datetime.now().isoformat()
        }
        
        # Store report
        await self._store_compliance_report(report)
        
        return report
    
    def _generate_recommendations(self, framework_score: Dict[str, Any], 
                                violations: List[Any]) -> List[str]:
        """Generate compliance recommendations"""
        recommendations = []
        
        # Score-based recommendations
        if framework_score['overall_score'] < 80:
            recommendations.append("Priority: Implement immediate remediation for critical controls")
        
        if framework_score['compliant_controls'] / framework_score['total_controls'] < 0.9:
            recommendations.append("Focus on achieving compliance for remaining controls")
        
        # Violation-based recommendations
        severity_counts = {}
        for violation in violations:
            severity = violation['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        if severity_counts.get('critical', 0) > 0:
            recommendations.append("Address critical violations immediately")
        
        if severity_counts.get('high', 0) > 2:
            recommendations.append("Implement systematic approach for high-severity violations")
        
        return recommendations
    
    async def _store_compliance_report(self, report: Dict[str, Any]):
        """Store compliance report in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO compliance_reports 
                (report_id, framework, report_type, generated_date, period_start, 
                 period_end, overall_score, findings, recommendations, report_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                report['report_id'], report['framework'], 'comprehensive',
                datetime.fromisoformat(report['generated_at']),
                datetime.fromisoformat(report['period']['start_date']),
                datetime.fromisoformat(report['period']['end_date']),
                report['compliance_score']['overall_score'],
                json.dumps(report['violations']['details']),
                json.dumps(report['recommendations']),
                json.dumps(report)
            )

# Global compliance monitor instance
compliance_monitor = ComplianceMonitor()

# FastAPI integration
class ComplianceAPI:
    """FastAPI endpoints for compliance monitoring"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.get("/api/compliance/frameworks")
        async def list_frameworks():
            """List supported compliance frameworks"""
            return {
                "frameworks": [
                    {
                        "id": framework.value,
                        "info": compliance_monitor.frameworks[framework]
                    }
                    for framework in ComplianceFramework
                ]
            }
        
        @self.app.get("/api/compliance/{framework}/score")
        async def get_framework_score(framework: ComplianceFramework):
            """Get compliance score for a framework"""
            score = await compliance_monitor.calculate_framework_score(framework)
            return score
        
        @self.app.post("/api/compliance/{framework}/check/{control_id}")
        async def perform_check(framework: ComplianceFramework, control_id: str):
            """Perform compliance check for a specific control"""
            try:
                check = await compliance_monitor.perform_compliance_check(control_id)
                return {
                    "check_id": check.check_id,
                    "status": check.status.value,
                    "score": check.score,
                    "findings": check.findings
                }
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
        
        @self.app.get("/api/compliance/{framework}/report")
        async def generate_report(framework: ComplianceFramework, period_days: int = 30):
            """Generate compliance report"""
            report = await compliance_monitor.generate_compliance_report(framework, period_days)
            return report

# Initialize compliance monitoring
async def initialize_compliance_monitoring():
    """Initialize compliance monitoring system"""
    await compliance_monitor.initialize()
    logfire.info("Compliance monitoring system ready")