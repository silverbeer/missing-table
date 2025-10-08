# AI Agents Architecture for MLS Next Data Integration

## Overview

This document outlines the design and implementation of a multi-agent system for automatically scraping MLS Next data and integrating it with the missing-table application. The architecture emphasizes modern Kubernetes practices, cost management, and API-first communication patterns.

## Goals

### Primary Learning Objectives
1. **Kubernetes Mastery**: Modern tooling with Helm, ArgoCD, and GitOps workflows
2. **AI Agent Implementation**: Master/sub-agent patterns with practical real-world application
3. **Cost Management**: Resource optimization and monitoring in K8s environments

### Secondary Objectives
- API-first microservice communication
- Security best practices with JWT authentication
- Observability and monitoring integration
- Scalable data processing patterns

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Master Agent  │───▶│  Scraper Agent  │    │   Database Agent│
│  (Orchestrator) │    │   (MLS Next)    │───▶│   (HTTP API)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       ▼
         │                       │              ┌─────────────────┐
         │                       │              │   FastAPI       │
         │                       │              │   Backend       │
         │                       │              └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   CronJob   │  │  Services   │  │ Deployments │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Architecture

### Master Agent (Orchestrator)

**Location**: `backend/agents/master_agent.py`

**Core Responsibilities**:
- **Scheduling**: Coordinate scraper and database agents on defined intervals
- **Health Monitoring**: Track agent status and handle failures gracefully
- **Rate Limiting**: Ensure ethical scraping practices and API rate compliance
- **Retry Logic**: Implement exponential backoff for failed operations
- **Metrics Collection**: Gather performance and success metrics

**Key Features**:
```python
class MasterAgent:
    async def orchestrate_data_collection(self):
        # 1. Trigger scraper agent
        # 2. Wait for completion and validate data
        # 3. Trigger database agent with scraped data
        # 4. Monitor and log results
        # 5. Handle errors and retries
```

**Configuration**:
- Configurable scheduling intervals
- Circuit breaker patterns for failure handling
- Integration with K8s health checks

### Scraper Agent (MLS Next Integration)

**Location**: `backend/agents/scraper_agent.py`

**Data Sources**:
- Primary: https://www.mlssoccer.com/mlsnext/
- API Endpoints (if available):
  - Stats API: `https://stats-api.mlssoccer.com`
  - Forge Data API: `https://dapi.mlssoccer.com/v2`
  - Sports API: `https://sportapi.mlssoccer.com/api`

**Core Responsibilities**:
- **Web Scraping**: Extract game schedules and scores from MLS Next
- **Data Parsing**: Convert HTML/JSON to structured data formats
- **Age Group Processing**: Handle all age categories (U13, U14, U15, U16, U17, U19)
- **Rate Limiting**: Respect robots.txt and implement delays
- **Data Validation**: Ensure scraped data integrity

**Implementation Strategy**:
```python
class ScraperAgent:
    async def scrape_age_group_schedules(self, age_groups: List[str]):
        # Iterate through age group URLs systematically
        # Parse schedule pages for game data
        # Extract: teams, dates, scores, venues
        # Return structured data for database agent
```

**Error Handling**:
- Robust parsing with multiple fallback strategies
- Graceful handling of website structure changes
- Comprehensive logging for debugging

### Database Agent (API Integration)

**Location**: `backend/agents/db_agent.py`

**Communication Pattern**: **HTTP API Only** (No Direct Database Access)

**Core Responsibilities**:
- **API Authentication**: Use JWT tokens for secure communication
- **Data Integration**: Update games, teams, and scores via FastAPI endpoints
- **Conflict Resolution**: Handle duplicate data and update strategies
- **Data Validation**: Leverage existing API validation logic

**API Integration Pattern**:
```python
class DatabaseAgent:
    def __init__(self, api_base_url: str, auth_token: str):
        self.api_client = AuthenticatedAPIClient(api_base_url, auth_token)
    
    async def update_games_bulk(self, games_data: List[GameData]):
        # POST /api/admin/games/bulk
        
    async def update_individual_game(self, game_id: str, game_data: GameData):
        # PUT /api/admin/games/{game_id}
        
    async def create_teams(self, teams_data: List[TeamData]):
        # POST /api/admin/teams
```

**Benefits of HTTP API Approach**:
- **Security**: Leverage existing authentication and authorization
- **Validation**: Use established data validation rules
- **Consistency**: Maintain existing error handling patterns
- **Monitoring**: Utilize existing API observability
- **Scalability**: Support for load balancing and rate limiting

## Kubernetes Integration

### Deployment Strategies

#### Option 1: Standalone Agent Microservice
```yaml
# k8s/deployments/agents-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: missing-table-agents
spec:
  replicas: 1
  selector:
    matchLabels:
      app: missing-table-agents
  template:
    spec:
      containers:
      - name: agents
        image: missing-table/agents:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

#### Option 2: CronJob for Scheduled Execution
```yaml
# k8s/cronjobs/agent-scheduler.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mls-data-scraper
spec:
  schedule: "0 6 * * *"  # Daily at 6 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scraper
            image: missing-table/agents:latest
            command: ["python", "-m", "agents.master_agent"]
          restartPolicy: OnFailure
```

#### Option 3: Sidecar Pattern
```yaml
# Extend existing backend deployment with agent sidecar
containers:
- name: backend
  image: missing-table/backend:latest
- name: agents
  image: missing-table/agents:latest
  env:
  - name: AGENT_MODE
    value: "sidecar"
```

### Resource Management and Cost Optimization

**Resource Quotas**:
```yaml
# k8s/resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: agents-quota
spec:
  hard:
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.cpu: "2"
    limits.memory: 2Gi
```

**Horizontal Pod Autoscaler (HPA)**:
```yaml
# k8s/hpa-agents.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agents-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: missing-table-agents
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Cost Management Strategies**:
- **Spot Instances**: Use preemptible nodes for non-critical agent workloads
- **Vertical Pod Autoscaling**: Right-size containers based on actual usage
- **Cluster Autoscaling**: Scale nodes down during low-usage periods
- **Resource Requests/Limits**: Prevent resource waste and ensure efficient scheduling

## ArgoCD GitOps Integration

### Application Definition
```yaml
# argocd/applications/missing-table-agents.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: missing-table-agents
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourusername/missing-table
    targetRevision: HEAD
    path: k8s/agents
  destination:
    server: https://kubernetes.default.svc
    namespace: missing-table
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### Environment-Specific Configurations

**Development Environment**:
```yaml
# argocd/applications/agents-dev.yaml
spec:
  source:
    helm:
      valueFiles:
      - values-dev.yaml
      parameters:
      - name: agents.scrapeInterval
        value: "*/30 * * * *"  # Every 30 minutes for testing
      - name: agents.logLevel
        value: "DEBUG"
```

**Production Environment**:
```yaml
# argocd/applications/agents-prod.yaml
spec:
  source:
    helm:
      valueFiles:
      - values-prod.yaml
      parameters:
      - name: agents.scrapeInterval
        value: "0 6 * * *"  # Daily at 6 AM
      - name: agents.logLevel
        value: "INFO"
```

### GitOps Workflow Benefits
- **Version Control**: All configuration changes tracked in Git
- **Rollback Capability**: Easy reversion to previous configurations
- **Environment Parity**: Consistent deployments across dev/staging/prod
- **Security**: No direct cluster access required for deployments

## Security Considerations

### Authentication and Authorization
- **JWT Token Management**: Secure token storage and rotation
- **Role-Based Access**: Agents use appropriate service account permissions
- **API Rate Limiting**: Respect external API limits and internal quotas

### Network Security
```yaml
# k8s/network-policies/agents-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agents-network-policy
spec:
  podSelector:
    matchLabels:
      app: missing-table-agents
  policyTypes:
  - Ingress
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: missing-table-backend
    ports:
    - protocol: TCP
      port: 8000
  - to: []  # Allow external MLS Next website access
    ports:
    - protocol: TCP
      port: 443
```

### Secret Management
```yaml
# k8s/secrets/agent-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-secrets
type: Opaque
data:
  api-token: <base64-encoded-jwt-token>
  scraper-user-agent: <base64-encoded-user-agent>
```

## Monitoring and Observability

### Prometheus Metrics
```python
# agents/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics for agent monitoring
scrape_attempts_total = Counter('mls_scrape_attempts_total', 'Total scrape attempts')
scrape_duration_seconds = Histogram('mls_scrape_duration_seconds', 'Scrape duration')
games_updated_total = Counter('mls_games_updated_total', 'Total games updated')
api_requests_total = Counter('mls_api_requests_total', 'Total API requests to backend')
```

### Grafana Dashboard Queries
```promql
# Scraping success rate
rate(mls_scrape_attempts_total{status="success"}[5m]) / rate(mls_scrape_attempts_total[5m])

# Average scrape duration
rate(mls_scrape_duration_seconds_sum[5m]) / rate(mls_scrape_duration_seconds_count[5m])

# Games update rate
rate(mls_games_updated_total[5m])
```

### Logging Strategy
```python
# agents/logging_config.py
import structlog

logger = structlog.get_logger()

# Structured logging for better observability
logger.info("scrape_started", 
           age_group="U15", 
           target_url="https://www.mlssoccer.com/mlsnext/schedule/u15/")

logger.error("scrape_failed", 
            age_group="U15", 
            error=str(e), 
            retry_attempt=3)
```

## Implementation Timeline

### Phase 1: Foundation (Week 1-2)
- [ ] Create base agent framework
- [ ] Implement master agent orchestration
- [ ] Set up local development environment
- [ ] Basic logging and error handling

### Phase 2: Data Integration (Week 3-4)
- [ ] Implement MLS Next scraper agent
- [ ] Create database agent with HTTP API integration
- [ ] Data validation and transformation logic
- [ ] End-to-end testing with sample data

### Phase 3: Kubernetes Deployment (Week 5-6)
- [ ] Create K8s deployment manifests
- [ ] Set up ArgoCD applications
- [ ] Implement monitoring and alerting
- [ ] Resource optimization and cost management

### Phase 4: Production Readiness (Week 7-8)
- [ ] Security hardening and network policies
- [ ] Performance tuning and scalability testing
- [ ] Documentation and runbooks
- [ ] Production deployment and monitoring

## Testing Strategy

### Unit Testing
```python
# tests/test_agents/test_scraper_agent.py
import pytest
from agents.scraper_agent import ScraperAgent

@pytest.mark.asyncio
async def test_scrape_age_group_schedules():
    agent = ScraperAgent()
    data = await agent.scrape_age_group_schedules(["U15"])
    assert len(data) > 0
    assert all(game.has_required_fields() for game in data)
```

### Integration Testing
```python
# tests/test_agents/test_integration.py
@pytest.mark.integration
async def test_end_to_end_data_flow():
    # Test full pipeline: scrape -> process -> API update
    master = MasterAgent()
    result = await master.orchestrate_data_collection()
    assert result.success
    assert result.games_updated > 0
```

### Load Testing
```bash
# Use k6 for load testing API endpoints
k6 run tests/load/agent-api-load-test.js
```

## Troubleshooting Guide

### Common Issues

**Scraping Failures**:
- Check robots.txt compliance
- Verify rate limiting configuration
- Review HTML structure changes
- Monitor external API availability

**API Authentication Issues**:
- Validate JWT token expiration
- Check service account permissions
- Verify API endpoint availability
- Review network policies

**Resource Constraints**:
- Monitor CPU/memory usage
- Check resource quotas and limits
- Review HPA scaling metrics
- Analyze cost optimization opportunities

### Debugging Commands
```bash
# Check agent pod logs
kubectl logs -f deployment/missing-table-agents -n missing-table

# Verify CronJob execution
kubectl get cronjobs -n missing-table
kubectl describe cronjob mls-data-scraper -n missing-table

# Monitor resource usage
kubectl top pods -n missing-table

# Check ArgoCD sync status
argocd app get missing-table-agents
```

## Future Enhancements

### Advanced Features
- **Machine Learning**: Anomaly detection for unusual game data
- **Real-time Updates**: WebSocket integration for live score updates
- **Multi-league Support**: Extend to other sports leagues
- **Data Analytics**: Advanced metrics and trend analysis

### Scalability Improvements
- **Event-driven Architecture**: Use message queues for agent communication
- **Microservice Decomposition**: Split agents into smaller, focused services
- **Caching Strategy**: Implement Redis caching for frequently accessed data
- **Database Sharding**: Horizontal scaling for large datasets

This architecture provides a solid foundation for learning modern Kubernetes practices while implementing a practical AI agent system for automated data collection and integration.