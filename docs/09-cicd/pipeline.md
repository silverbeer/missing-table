# CI/CD Pipeline with Comprehensive Quality Gates

This document describes the comprehensive CI/CD pipeline implementation for the Missing Table application, featuring multi-stage quality gates, security scanning, and automated deployment with monitoring.

## Pipeline Overview

The CI/CD pipeline is implemented using both **GitHub Actions** and **Google Cloud Build** to provide flexibility and redundancy. The pipeline consists of 6 main stages with strict quality gates that must pass before proceeding to the next stage.

### Pipeline Stages

1. **Stage 1: Code Quality Checks**
2. **Stage 2: Security Scanning**
3. **Stage 3: Unit and Integration Testing**
4. **Stage 4: Container Security Scanning**
5. **Stage 5: Infrastructure Security Validation**
6. **Stage 6: Deployment with Monitoring**

## Quality Gate Requirements

### 🚫 Blocking Requirements (Pipeline Fails)

- **Zero critical security vulnerabilities**
- **Zero high security vulnerabilities**
- **Zero linting errors** (warnings allowed with justification)
- **90% minimum test coverage** for critical business logic
- **All security policies must pass** (Checkov, tfsec, Terrascan)
- **Container security scans must pass** (no critical/high vulnerabilities)
- **Infrastructure security validation must pass**

### ⚠️ Warning Requirements (Pipeline Continues)

- Medium security vulnerabilities (up to 5 allowed)
- Low security vulnerabilities (up to 10 allowed)
- Performance budget violations (Lighthouse scores)
- Code quality warnings with proper justification

## Pipeline Implementation

### GitHub Actions Workflows

#### 1. Main CI/CD Pipeline (`.github/workflows/ci-cd-pipeline.yml`)

The primary workflow that runs on every push and pull request:

```yaml
# Triggers
on:
  push:
    branches: [ main, develop, v1.* ]
  pull_request:
    branches: [ main, develop ]
  workflow_dispatch:
```

**Features:**
- Multi-stage pipeline with quality gates
- Matrix strategy for backend/frontend parallel processing
- Conditional deployment based on branch and quality gates
- Comprehensive artifact collection and reporting
- Slack notifications for pipeline status

#### 2. Performance Budget Validation (`.github/workflows/performance-budget.yml`)

Dedicated workflow for performance testing:

```yaml
# Triggers  
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
  workflow_dispatch:
```

**Features:**
- Lighthouse CI with desktop and mobile testing
- Core Web Vitals validation
- Performance budget enforcement
- Load testing with K6
- Performance report generation

#### 3. Scheduled Security Scanning (`.github/workflows/security-scan-scheduled.yml`)

Comprehensive security scanning workflow:

```yaml
# Triggers
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
    - cron: '0 2 * * 0'  # Weekly comprehensive scan
  workflow_dispatch:
```

**Features:**
- Dependency vulnerability scanning
- Static code security analysis
- Secrets detection
- Infrastructure security validation
- Container security scanning
- Comprehensive security reporting

### Cloud Build Pipeline (`cloudbuild.yaml`)

Alternative pipeline implementation for Google Cloud Build:

**Features:**
- Mirror of GitHub Actions functionality
- Native GCP integration
- Parallel execution optimization
- Quality gate validation
- Automated deployment to GKE
- Build artifact storage in Cloud Storage

## Stage Details

### Stage 1: Code Quality Checks

#### Backend (Python)
- **Ruff**: Linting and code formatting
- **MyPy**: Static type checking with strict mode
- **Black**: Code formatting validation

```bash
# Quality requirements
uv run ruff check --output-format=github .
uv run ruff format --check .
uv run mypy . --strict --ignore-missing-imports
```

#### Frontend (JavaScript/Vue)
- **ESLint**: JavaScript/Vue linting
- **Biome**: Alternative linting and formatting
- **TypeScript**: Type checking and compilation validation

```bash
# Quality requirements
npm run lint
npx @biomejs/biome check --reporter=github .
npx vue-tsc --noEmit
```

### Stage 2: Security Scanning

#### Backend Security Tools
- **Bandit**: Python security issues detection
- **Safety**: Dependency vulnerability scanning
- **Semgrep**: Advanced static analysis

#### Frontend Security Tools
- **NPM Audit**: Dependency vulnerability scanning
- **Retire.js**: Known vulnerability detection
- **ESLint Security Plugin**: Security-focused linting

#### Cross-Platform Tools
- **Trivy**: Filesystem vulnerability scanning
- **TruffleHog**: Secrets detection
- **GitLeaks**: Git history secrets scanning

### Stage 3: Unit and Integration Testing

#### Backend Testing
- **pytest**: Unit and integration tests
- **Coverage**: 90% minimum line coverage requirement
- **Database Testing**: PostgreSQL integration tests

```bash
# Testing requirements
uv run pytest tests/ \
  --cov=. \
  --cov-fail-under=90 \
  --junitxml=pytest-results.xml
```

#### Frontend Testing
- **Vitest**: Unit testing framework
- **Vue Test Utils**: Component testing
- **Coverage**: 80% minimum line coverage requirement

### Stage 4: Container Security Scanning

#### Security Tools
- **Trivy**: Container image vulnerability scanning
- **Grype**: Additional vulnerability detection
- **Docker Scout**: Docker Hub integration (when available)

#### Security Requirements
- Non-root user execution
- Minimal base images (distroless preferred)
- No secrets in container layers
- Read-only filesystem where possible

### Stage 5: Infrastructure Security Validation

#### Terraform Security
- **Checkov**: Policy-as-code security scanning
- **tfsec**: Terraform-specific security checks
- **Terrascan**: Multi-cloud security policies

#### Kubernetes Security
- **kubesec**: Kubernetes security validation
- **Polaris**: Best practices validation
- **Falco**: Runtime security monitoring

#### Compliance Frameworks
- CIS Benchmarks
- NIST Cybersecurity Framework
- SOC 2 Type II
- GDPR compliance checks

### Stage 6: Deployment with Monitoring

#### Deployment Strategies
- **Production**: Blue-green deployment
- **Staging**: Rolling deployment
- **Feature branches**: No deployment

#### Post-Deployment Validation
- Health check validation
- Smoke testing
- Performance monitoring setup
- Logging configuration verification

## Configuration Files

### Quality Gates Configuration (`.github/workflows/quality-gates-config.yml`)

Defines specific thresholds and requirements:

```yaml
security_scanning:
  vulnerability_thresholds:
    critical: 0
    high: 0
    medium: 5
    low: 10

testing:
  coverage:
    backend:
      minimum_line_coverage: 90
    frontend:
      minimum_line_coverage: 80
```

### Tool-Specific Configurations

#### Backend Security (`backend/.safety-policy.json`)
```json
{
  "security": {
    "ignore-cvss-severity-below": 7.0,
    "continue-on-vulnerability-error": false
  }
}
```

#### Bandit Configuration (`backend/bandit.yaml`)
```yaml
confidence: [HIGH, MEDIUM]
severity: [HIGH, MEDIUM]
exclude_dirs: [/tests, /.venv]
```

#### Lighthouse Configuration (`frontend/lighthouse.config.js`)
```javascript
module.exports = {
  ci: {
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.90 }],
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }]
      }
    }
  }
};
```

## Environment Setup

### Required Secrets

#### GitHub Repository Secrets
```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_SA_KEY=base64-encoded-service-account-key
GCP_ZONE=us-central1-a

# Application URLs
APP_URL_STAGING=https://staging.example.com
APP_URL_PRODUCTION=https://app.example.com

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
LHCI_GITHUB_APP_TOKEN=github-app-token
```

#### Cloud Build Substitutions
```yaml
substitutions:
  _ENVIRONMENT: 'staging'
  _CLUSTER_NAME: 'missing-table-cluster'
  _ZONE: 'us-central1-a'
```

### Development Setup

1. **Install Dependencies**
   ```bash
   # Backend
   cd backend
   uv sync --dev
   
   # Frontend
   cd frontend
   npm ci
   ```

2. **Run Quality Checks Locally**
   ```bash
   # Backend
   uv run ruff check .
   uv run mypy .
   uv run pytest --cov=.
   
   # Frontend
   npm run lint
   npm run test:unit
   ```

3. **Security Scanning**
   ```bash
   # Backend
   uv run bandit -r .
   uv run safety check
   
   # Frontend
   npm audit
   npx retire
   ```

## Pipeline Monitoring and Metrics

### Key Performance Indicators (KPIs)

#### Pipeline Performance
- **Build Duration**: Target <30 minutes
- **Success Rate**: Target >95%
- **Mean Time to Recovery (MTTR)**: Target <15 minutes
- **Deployment Frequency**: Multiple times per day

#### Quality Metrics
- **Security Vulnerabilities**: Zero critical/high
- **Test Coverage**: >90% backend, >80% frontend
- **Code Quality Score**: >8.0/10
- **Performance Budget**: All thresholds met

#### Security Metrics
- **Vulnerability Detection Time**: <24 hours
- **Vulnerability Resolution Time**: <7 days for high, <1 day for critical
- **Security Scan Coverage**: 100% of codebase
- **Compliance Score**: 100% for enabled frameworks

### Alerting and Notifications

#### Slack Integration
- Real-time pipeline status updates
- Security vulnerability alerts
- Performance budget violations
- Deployment success/failure notifications

#### Alert Escalation
- **Critical Issues**: Immediate notification + on-call escalation
- **High Issues**: Notification within 15 minutes
- **Repeated Failures**: Auto-escalation after 3 consecutive failures

### Reporting

#### Daily Reports
- Security scan summary
- Performance metrics
- Quality gate statistics
- Deployment success rate

#### Weekly Reports
- Vulnerability trend analysis
- Performance budget compliance
- Code quality improvements
- Pipeline optimization recommendations

## Troubleshooting

### Common Issues

#### Quality Gate Failures

1. **Security Vulnerabilities Detected**
   ```bash
   # Check security reports
   cat bandit-report.json | jq '.results[]'
   cat safety-report.json | jq '.vulnerabilities[]'
   
   # Remediation
   uv update  # Update dependencies
   # Review and fix code issues
   ```

2. **Test Coverage Below Threshold**
   ```bash
   # Generate coverage report
   uv run pytest --cov=. --cov-report=html
   
   # Review missing coverage
   open htmlcov/index.html
   ```

3. **Container Security Issues**
   ```bash
   # Scan local image
   trivy image your-image:tag
   
   # Update base image
   # Remove unnecessary packages
   # Use multi-stage builds
   ```

#### Performance Issues

1. **Pipeline Duration Too Long**
   - Enable parallel execution
   - Optimize Docker layer caching
   - Use matrix strategies for independent jobs

2. **Resource Limitations**
   - Increase machine type in Cloud Build
   - Optimize memory usage in tests
   - Use dependency caching

### Emergency Procedures

#### Bypassing Quality Gates (Emergency Only)
```yaml
# In workflow_dispatch
inputs:
  skip_security_scans:
    description: 'Skip security scans (emergency only)'
    type: boolean
    default: false
```

#### Hotfix Deployment Process
1. Create hotfix branch from main
2. Make minimal changes
3. Run abbreviated pipeline (security + basic tests)
4. Deploy with manual approval
5. Full post-deployment validation

## Best Practices

### Code Quality
- Write tests before code (TDD)
- Use type hints in Python
- Follow established coding standards
- Regular code reviews

### Security
- Never commit secrets
- Use Workload Identity for GCP
- Regular dependency updates
- Security training for team

### Performance
- Monitor bundle sizes
- Optimize images and assets
- Use CDN for static content
- Regular performance audits

### Pipeline Management
- Keep pipelines fast (<30 min)
- Fail fast on critical issues
- Comprehensive logging
- Regular pipeline reviews

## Compliance and Auditing

### Audit Trail
- All pipeline executions logged
- Security scan results retained for 1 year
- Deployment history tracked
- Change management documented

### Compliance Frameworks
- **SOC 2 Type II**: Continuous monitoring and reporting
- **ISO 27001**: Information security management
- **CIS Controls**: Security baseline implementation
- **NIST Framework**: Cybersecurity framework alignment

### Reporting Requirements
- Monthly security posture reports
- Quarterly compliance assessments
- Annual security reviews
- Incident response documentation

## Continuous Improvement

### Regular Reviews
- Monthly pipeline performance review
- Quarterly security assessment
- Bi-annual tool evaluation
- Annual compliance audit

### Metrics Collection
- Pipeline execution metrics
- Security vulnerability trends
- Performance budget compliance
- Developer productivity metrics

### Process Optimization
- Automated quality gate adjustments
- Tool integration improvements
- Pipeline performance optimization
- Security scanning enhancements

---

## Support and Documentation

- **Pipeline Documentation**: This file
- **Security Procedures**: `SECURITY.md`
- **Incident Response**: `INCIDENT_RESPONSE.md`
- **Team Contacts**: Internal team directory

For questions or issues with the CI/CD pipeline, contact the Platform Engineering team or create an issue in the repository.