# RabbitMQ + Celery Integration Proposal

**Status:** Proposed
**Created:** 2025-10-10
**Author:** Architecture Discussion with Claude Code
**Target:** Post-beta launch implementation (after initial public testing)

---

## Executive Summary

This proposal outlines a plan to migrate from direct HTTP API calls to a message queue architecture using RabbitMQ and Celery. The primary goal is **learning modern distributed systems** while improving the match-scraper integration architecture.

**Key Decision:** Use a **hybrid deployment model** to maximize learning value while minimizing costs.

---

## Current Architecture

### Production (dev.missingtable.com on GKE)
```
┌─────────────────────────────────────────────┐
│ GKE Cluster (missing-table-dev)             │
│                                             │
│  ┌──────────────┐      ┌─────────────┐    │
│  │  Frontend    │◄─────┤  Ingress    │    │
│  │  (Vue 3)     │      │  (HTTPS)    │    │
│  └──────────────┘      └─────────────┘    │
│                                             │
│  ┌──────────────┐                          │
│  │  Backend     │                          │
│  │  (FastAPI)   │                          │
│  └──────┬───────┘                          │
│         │                                   │
│         │ HTTP/REST                         │
│         ▼                                   │
│  ┌─────────────────────────────┐           │
│  │  Supabase Cloud             │           │
│  │  (PostgreSQL + Auth)        │           │
│  └─────────────────────────────┘           │
│         ▲                                   │
│         │                                   │
│         │ HTTP POST /api/matches            │
│         │                                   │
│  ┌──────┴───────┐                          │
│  │ match-scraper│                          │
│  │ (CronJob)    │                          │
│  │ Daily 6AM UTC│                          │
│  └──────────────┘                          │
└─────────────────────────────────────────────┘
```

**Current Monthly Cost:** ~$30-40/month

---

## Proposed Architecture (Hybrid Model)

### Public Layer (GKE - No Changes)
```
┌─────────────────────────────────────────────┐
│ GKE Cluster (missing-table-dev)             │
│                                             │
│  ┌──────────────┐      ┌─────────────┐    │
│  │  Frontend    │◄─────┤  Ingress    │    │
│  │  (Vue 3)     │      │  (HTTPS)    │    │
│  └──────────────┘      └─────────────┘    │
│                                             │
│  ┌──────────────┐                          │
│  │  Backend     │  (Serves public traffic) │
│  │  (FastAPI)   │  (Read-only to Supabase) │
│  └──────┬───────┘                          │
│         │                                   │
│         │ Read matches, teams, standings   │
│         ▼                                   │
│  ┌─────────────────────────────┐           │
│  │  Supabase Cloud             │           │
│  │  (PostgreSQL + Auth)        │           │
│  └─────────────┬───────────────┘           │
└────────────────┼─────────────────────────────┘
                 │
                 │ Read/Write
                 │
┌────────────────┼─────────────────────────────┐
│ Local K3s      │ (Internal Processing)       │
│                ▼                             │
│  ┌─────────────────────────────┐            │
│  │   Celery Workers            │            │
│  │   (Write matches)           │            │
│  └──────────▲──────────────────┘            │
│             │                                │
│             │ Consume tasks                  │
│             │                                │
│  ┌──────────┴──────────┐                    │
│  │     RabbitMQ        │                    │
│  │  (Message Broker)   │                    │
│  └──────────▲──────────┘                    │
│             │                                │
│             │ Publish matches                │
│             │                                │
│  ┌──────────┴──────────┐                    │
│  │   match-scraper     │                    │
│  │  (Playwright)       │                    │
│  └─────────────────────┘                    │
│                                              │
│  ┌──────────────────────┐                   │
│  │  Redis               │                   │
│  │  (Result Backend)    │                   │
│  └──────────────────────┘                   │
│                                              │
│  ┌──────────────────────┐                   │
│  │  Celery Beat         │                   │
│  │  (Scheduler)         │                   │
│  └──────────────────────┘                   │
│                                              │
│  ┌──────────────────────┐                   │
│  │  Flower              │                   │
│  │  (Monitoring UI)     │                   │
│  └──────────────────────┘                   │
└──────────────────────────────────────────────┘
```

**Proposed Monthly Cost:** ~$35-45/month (+$5 from electricity)

---

## Cost Analysis

### Option 1: Full GKE Deployment (Not Recommended)
| Component | Monthly Cost |
|-----------|-------------|
| Existing GKE (backend/frontend) | $30-40 |
| RabbitMQ StatefulSet (GKE) | $22 |
| Redis StatefulSet (GKE) | $11 |
| Celery Workers (2 replicas, GKE) | $44 |
| Celery Beat (GKE) | $4.50 |
| **Total** | **~$112/month** |

**Delta:** +$72/month (240% increase)

### Option 2: Hybrid Deployment (RECOMMENDED)
| Component | Monthly Cost |
|-----------|-------------|
| Existing GKE (backend/frontend) | $30-40 |
| RabbitMQ (Local K3s) | $0 |
| Redis (Local K3s) | $0 |
| Celery Workers (Local K3s) | $0 |
| Celery Beat (Local K3s) | $0 |
| match-scraper (Local K3s) | $0 |
| Electricity (Mac Mini) | $5 |
| **Total** | **~$35-45/month** |

**Delta:** +$5/month (12.5% increase)
**Savings vs Option 1:** $67/month ($804/year)

---

## Learning Objectives

### Distributed Systems Concepts
1. **Message Queue Patterns**
   - Publisher/consumer model
   - Message persistence and durability
   - Dead letter queues
   - Message acknowledgment
   - Exchange types (direct, topic, fanout)

2. **Distributed Task Processing**
   - Task serialization with Celery
   - Worker pool management
   - Result backends (Redis)
   - Task routing and prioritization
   - Chaining and grouping tasks

3. **Kubernetes StatefulSets**
   - Persistent storage with PVCs
   - Ordered pod creation/deletion
   - Stable network identities
   - Volume claim templates

4. **Helm Chart Development**
   - Chart templating
   - Values.yaml configuration
   - Dependencies management
   - Chart versioning and upgrades

5. **Observability & Monitoring**
   - RabbitMQ Management UI
   - Celery Flower (worker monitoring)
   - Prometheus metrics collection
   - Grafana Cloud dashboards
   - Distributed tracing

### Career Value
- ✅ Portfolio project demonstrating distributed systems
- ✅ Hands-on experience with RabbitMQ (used by major companies)
- ✅ Celery expertise (Python async task standard)
- ✅ Production Kubernetes experience
- ✅ Helm chart development skills

---

## Technical Implementation Plan

### Phase 1: Helm Chart Development (Week 1)

**Create Helm Chart Structure:**
```
helm/
├── messaging-platform/          # New chart for RabbitMQ/Celery
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-local.yaml       # Local K3s configuration
│   ├── values-gke.yaml         # GKE configuration (future)
│   └── templates/
│       ├── rabbitmq/
│       │   ├── statefulset.yaml
│       │   ├── service.yaml
│       │   ├── configmap.yaml
│       │   └── pvc.yaml
│       ├── redis/
│       │   ├── statefulset.yaml
│       │   ├── service.yaml
│       │   └── pvc.yaml
│       ├── celery/
│       │   ├── worker-deployment.yaml
│       │   ├── beat-deployment.yaml
│       │   └── flower-deployment.yaml
│       ├── observability/
│       │   ├── prometheus-config.yaml
│       │   ├── promtail-config.yaml
│       │   └── servicemonitor.yaml
│       └── secrets.yaml
```

**Key Helm Features:**
- Parameterized resource limits (CPU/memory)
- Environment-specific values files
- Support for both K3s and GKE deployments
- Built-in observability configuration
- Secret management with external-secrets (optional)

### Phase 2: Backend Integration (Week 2)

**Add Celery to missing-table backend:**

```python
# backend/celery_app.py
from celery import Celery
from dao.enhanced_data_access_fixed import EnhancedSportsDAO
from supabase import create_client
import os

app = Celery(
    'missing_table',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://admin:password@rabbitmq:5672//'),  # pragma: allowlist secret
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
)

@app.task(name='missing_table.process_match', bind=True, max_retries=3)
def process_match(self, match_data: dict):
    """
    Process a single match from match-scraper.

    Args:
        match_data: Match information dictionary

    Returns:
        dict: Processing result with match_id and status
    """
    try:
        supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        dao = EnhancedSportsDAO(supabase)

        result = dao.add_match(
            home_team_id=match_data['home_team_id'],
            away_team_id=match_data['away_team_id'],
            match_date=match_data['match_date'],
            home_score=match_data['home_score'],
            away_score=match_data['away_score'],
            season_id=match_data['season_id'],
            age_group_id=match_data['age_group_id'],
            match_type_id=match_data['match_type_id'],
            division_id=match_data.get('division_id'),
            status=match_data.get('status', 'scheduled'),
            source='match-scraper',
            external_match_id=match_data.get('match_id')
        )

        return {
            "success": True,
            "match_id": result,
            "external_match_id": match_data.get('match_id')
        }

    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@app.task(name='missing_table.process_matches_batch')
def process_matches_batch(matches: list[dict]):
    """
    Process multiple matches in parallel.

    Args:
        matches: List of match data dictionaries

    Returns:
        dict: Batch processing results
    """
    from celery import group

    # Create parallel task group
    job = group(process_match.s(match) for match in matches)
    result = job.apply_async()

    # Wait for all tasks (with timeout)
    results = result.get(timeout=600, propagate=False)

    return {
        "total": len(matches),
        "successful": sum(1 for r in results if r.get('success')),
        "failed": sum(1 for r in results if not r.get('success')),
        "results": results
    }
```

**Update Backend Dependencies:**
```toml
# backend/pyproject.toml
[project]
dependencies = [
    # ... existing dependencies ...
    "celery[redis]>=5.3.0",
    "flower>=2.0.0",  # Monitoring UI
]
```

**Update Dockerfile:**
```dockerfile
# backend/Dockerfile
FROM python:3.13-slim

# ... existing setup ...

# Support both web server and Celery worker modes
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]  # Default: web server
```

**Entrypoint Script:**
```bash
#!/bin/bash
# backend/entrypoint.sh

case "$1" in
    web)
        exec uvicorn app:app --host 0.0.0.0 --port 8000
        ;;
    worker)
        exec celery -A celery_app worker --loglevel=info --concurrency=4
        ;;
    beat)
        exec celery -A celery_app beat --loglevel=info
        ;;
    flower)
        exec celery -A celery_app flower --port=5555
        ;;
    *)
        exec "$@"
        ;;
esac
```

### Phase 3: match-scraper Integration (Week 3)

**Add RabbitMQ Publisher:**

```python
# match-scraper/src/api/rabbitmq_publisher.py
"""
RabbitMQ publisher for match-scraper.

Publishes scraped matches to RabbitMQ queue for processing by Celery workers.
"""

import pika
import json
from typing import List, Dict, Any
from src.scraper.models import Match
from src.utils.logger import get_logger

logger = get_logger()


class RabbitMQPublisher:
    """
    Publisher client for RabbitMQ message broker.

    Sends match data to RabbitMQ queue for asynchronous processing
    by Celery workers in the missing-table backend.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str = 'match_processing',
        durable: bool = True
    ):
        """
        Initialize RabbitMQ publisher.

        Args:
            rabbitmq_url: AMQP connection URL (e.g., amqp://user:pass@host:5672//)  # pragma: allowlist secret
            queue_name: Name of the queue to publish to
            durable: Whether queue should survive broker restarts
        """
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.durable = durable
        self.connection = None
        self.channel = None

        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.rabbitmq_url)
            )
            self.channel = self.connection.channel()

            # Declare queue (idempotent)
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=self.durable
            )

            logger.info(
                f"Connected to RabbitMQ",
                extra={
                    "queue": self.queue_name,
                    "durable": self.durable
                }
            )

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def publish_match(self, match: Match) -> bool:
        """
        Publish a single match to RabbitMQ.

        Args:
            match: Match object to publish

        Returns:
            bool: True if published successfully
        """
        try:
            message = {
                'task': 'missing_table.process_match',
                'args': [match.model_dump()],
                'kwargs': {},
                'id': f"match_{match.match_id}"
            }

            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json'
                )
            )

            logger.debug(
                f"Published match to RabbitMQ",
                extra={
                    "match_id": match.match_id,
                    "home_team": match.home_team,
                    "away_team": match.away_team
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to publish match {match.match_id}: {e}")
            return False

    def publish_matches(self, matches: List[Match]) -> Dict[str, Any]:
        """
        Publish multiple matches to RabbitMQ.

        Args:
            matches: List of Match objects to publish

        Returns:
            dict: Publishing results with counts
        """
        results = {
            "published": 0,
            "failed": 0,
            "total": len(matches)
        }

        for match in matches:
            if self.publish_match(match):
                results["published"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Batch publish complete",
            extra=results
        )

        return results

    def close(self):
        """Close RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed")
```

**Update match-scraper Configuration:**

```python
# match-scraper/src/scraper/config.py

class ScrapingConfig(BaseModel):
    # ... existing fields ...

    # RabbitMQ configuration
    use_rabbitmq: bool = Field(
        default=False,
        description="Use RabbitMQ instead of HTTP API"
    )
    rabbitmq_url: Optional[str] = Field(
        default=None,
        description="RabbitMQ AMQP URL"
    )
    rabbitmq_queue: str = Field(
        default="match_processing",
        description="RabbitMQ queue name"
    )
```

**Update Scraper to Support Both Modes:**

```python
# match-scraper/src/scraper/mls_scraper.py

async def scrape_matches(self) -> list[Match]:
    # ... existing scraping logic ...

    # Post matches to API or RabbitMQ
    if self.config.use_rabbitmq:
        # Use RabbitMQ
        from src.api.rabbitmq_publisher import RabbitMQPublisher

        publisher = RabbitMQPublisher(
            rabbitmq_url=self.config.rabbitmq_url,
            queue_name=self.config.rabbitmq_queue
        )

        results = publisher.publish_matches(matches)
        publisher.close()

        logger.info(
            "Published matches to RabbitMQ",
            extra=results
        )
    else:
        # Use HTTP API (existing code)
        if self.enable_api_integration and self.api_integrator:
            api_results = await self.api_integrator.post_matches(
                matches, self.config.age_group, self.config.division
            )
```

### Phase 4: Observability Setup (Week 4)

**Grafana Cloud Integration:**

1. **Prometheus Metrics Export**
   - RabbitMQ metrics (queue depth, message rate, etc.)
   - Celery metrics (task success/failure, latency, etc.)
   - Redis metrics (memory usage, connections)
   - Custom application metrics

2. **Loki Log Aggregation**
   - Structured logs from all components
   - Correlation IDs for distributed tracing
   - Log-based alerting

3. **Dashboards**
   - Message queue overview (queue depth trends, throughput)
   - Celery worker health (active/idle workers, task latency)
   - End-to-end processing time (scrape → publish → process → DB)
   - Error rates and retry metrics

**Example Prometheus Configuration:**

```yaml
# helm/messaging-platform/templates/observability/prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: messaging
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      external_labels:
        cluster: k3s
        environment: local

    remote_write:
      - url: https://prometheus-prod-us-central-0.grafana.net/api/prom/push
        basic_auth:
          username: ${GRAFANA_CLOUD_USERNAME}
          password: ${GRAFANA_CLOUD_API_KEY}

    scrape_configs:
      # RabbitMQ metrics
      - job_name: 'rabbitmq'
        static_configs:
          - targets: ['rabbitmq:15692']
        metric_relabel_configs:
          - source_labels: [__name__]
            regex: 'rabbitmq_.*'
            action: keep

      # Celery metrics (via Flower)
      - job_name: 'celery'
        static_configs:
          - targets: ['flower:5555']
        metrics_path: /metrics

      # Redis metrics
      - job_name: 'redis'
        static_configs:
          - targets: ['redis-exporter:9121']
```

---

## Deployment Instructions

### Prerequisites
- Local K3s cluster running on Mac Mini
- Helm 3.x installed
- kubectl configured for K3s cluster
- Grafana Cloud account (free tier)

### Initial Deployment (Local K3s)

```bash
# 1. Create namespace
kubectl create namespace messaging

# 2. Create secrets
kubectl create secret generic rabbitmq-secrets \
  --from-literal=username=admin \
  --from-literal=password=$(openssl rand -base64 32) `# pragma: allowlist secret` \
  -n messaging

kubectl create secret generic supabase-secrets \
  --from-literal=url=${SUPABASE_URL} \
  --from-literal=key=${SUPABASE_SERVICE_ROLE_KEY} \
  -n messaging

kubectl create secret generic grafana-cloud-secrets \
  --from-literal=username=${GRAFANA_CLOUD_USERNAME} \
  --from-literal=api-key=${GRAFANA_CLOUD_API_KEY} \
  -n messaging

# 3. Deploy messaging platform
helm install messaging-platform ./helm/messaging-platform \
  -f ./helm/messaging-platform/values-local.yaml \
  --namespace messaging \
  --create-namespace

# 4. Verify deployment
kubectl get pods -n messaging
kubectl get pvc -n messaging

# 5. Access services
kubectl port-forward -n messaging svc/rabbitmq 15672:15672  # Management UI
kubectl port-forward -n messaging svc/flower 5555:5555      # Celery monitoring
```

### Testing the Integration

```bash
# 1. Run match-scraper in RabbitMQ mode
cd match-scraper
export USE_RABBITMQ=true
export RABBITMQ_URL="amqp://admin:password@localhost:5672//"  # pragma: allowlist secret
python -m src.cli.main scrape

# 2. Monitor in RabbitMQ Management UI
# Visit http://localhost:15672
# Login: admin / <password from secret>
# Check queues → match_processing

# 3. Monitor Celery workers in Flower
# Visit http://localhost:5555
# See active tasks and worker status

# 4. Verify matches in Supabase
# Check that matches appear in database
```

---

## Migration Strategy

### Phase 1: Parallel Operation (Weeks 1-2)
- Deploy RabbitMQ/Celery to local K3s
- Run match-scraper in **dual mode**:
  - Primary: HTTP API (existing, stable)
  - Secondary: RabbitMQ (new, testing)
- Compare results to ensure parity
- GKE production remains unchanged

### Phase 2: Gradual Cutover (Weeks 3-4)
- Switch match-scraper to **RabbitMQ primary**
- Keep HTTP as fallback
- Monitor error rates in Grafana Cloud
- GKE production still unchanged (reads from same Supabase)

### Phase 3: Full Migration (Week 5)
- Remove HTTP fallback from match-scraper
- Decommission old integration code
- GKE production validated with full RabbitMQ flow

### Rollback Plan
If issues arise:
1. Set `USE_RABBITMQ=false` in match-scraper config
2. Falls back to HTTP API immediately
3. RabbitMQ/Celery continues running (no data loss)
4. Debug and fix issues, retry migration

---

## Success Metrics

### Technical Metrics
- ✅ Match processing latency < 5 seconds (p95)
- ✅ Message queue depth < 100 messages
- ✅ Celery worker utilization 40-60% average
- ✅ Task failure rate < 1%
- ✅ End-to-end reliability > 99.5%

### Learning Metrics
- ✅ Complete understanding of RabbitMQ architecture
- ✅ Ability to debug Celery task failures
- ✅ Helm chart development proficiency
- ✅ StatefulSet management experience
- ✅ Grafana Cloud dashboard creation

### Cost Metrics
- ✅ Monthly cost increase < $10
- ✅ Resource utilization monitored
- ✅ No unexpected cloud charges

---

## Risks and Mitigations

### Risk 1: Local K3s Downtime
**Impact:** match-scraper can't publish to RabbitMQ
**Mitigation:**
- Configure match-scraper with HTTP fallback
- Set up UPS for Mac Mini
- Monitor K3s health with Grafana Cloud alerts

### Risk 2: Message Loss
**Impact:** Scraped matches not processed
**Mitigation:**
- RabbitMQ message persistence (durable queues)
- Celery task acknowledgment
- Retry logic with exponential backoff
- Dead letter queue for failed tasks

### Risk 3: Database Connection Issues
**Impact:** Celery workers can't write to Supabase
**Mitigation:**
- Connection pooling in workers
- Retry logic for transient failures
- Supabase connection health checks
- Alert on sustained failures

### Risk 4: Learning Curve
**Impact:** Delayed implementation or misconfigurations
**Mitigation:**
- Start with local development
- Reference official documentation
- Iterative testing and validation
- This proposal document as roadmap

---

## Future Enhancements

### Phase 2 Features (Post-initial deployment)
1. **Multi-worker scaling**
   - Scale Celery workers based on queue depth
   - Horizontal Pod Autoscaler (HPA) configuration

2. **Advanced routing**
   - Route matches by age group to dedicated workers
   - Priority queues for time-sensitive matches

3. **Result notifications**
   - Webhook callbacks when matches are processed
   - Email notifications for errors

4. **GKE deployment option**
   - Add values-gke.yaml for cloud deployment
   - Compare cost/performance vs hybrid model

### Phase 3 Features (Future)
1. **Real-time updates**
   - WebSocket integration for live score updates
   - Push notifications to frontend

2. **Advanced monitoring**
   - Custom Grafana dashboards
   - PagerDuty/OpsGenie integration
   - Automated alerting rules

3. **Data pipeline**
   - Additional Celery tasks for analytics
   - Periodic data aggregation jobs
   - Report generation

---

## References

### Documentation
- [RabbitMQ Official Docs](https://www.rabbitmq.com/documentation.html)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Helm Charts Guide](https://helm.sh/docs/topics/charts/)
- [K3s Documentation](https://docs.k3s.io/)
- [Grafana Cloud](https://grafana.com/docs/grafana-cloud/)

### Related Files
- `helm/missing-table/` - Existing missing-table Helm chart (GKE)
- `backend/app.py` - FastAPI backend (lines 1101-1263 have match endpoints)
- `match-scraper/src/api/missing_table_client.py` - Current HTTP API client
- `match-scraper/src/scraper/api_integration.py` - Current integration logic

### GitHub Issues
- Track progress with GitHub issue: "Implement RabbitMQ/Celery Integration"
- Create milestone: "Messaging Platform v1.0"

---

## Appendix A: Resource Requirements

### Local K3s (Mac Mini)
```yaml
RabbitMQ:
  cpu: 500m (0.5 cores)
  memory: 512Mi
  storage: 5Gi (PVC)

Redis:
  cpu: 250m (0.25 cores)
  memory: 256Mi
  storage: 2Gi (PVC)

Celery Worker (2 replicas):
  cpu: 200m each (0.4 cores total)
  memory: 256Mi each (512Mi total)

Celery Beat:
  cpu: 100m (0.1 cores)
  memory: 128Mi

Flower:
  cpu: 100m (0.1 cores)
  memory: 128Mi

Total:
  cpu: ~1.35 cores
  memory: ~1.5Gi
  storage: 7Gi
```

**Mac Mini Requirements:**
- Minimum: 8GB RAM, 4 cores, 50GB free storage
- Recommended: 16GB RAM, 6+ cores, 100GB free storage

---

## Appendix B: Helm Values Structure

### values-local.yaml (Example)
```yaml
environment: local
cluster: k3s

rabbitmq:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
  persistence:
    enabled: true
    size: 5Gi
  service:
    type: LoadBalancer
    port: 5672
    managementPort: 15672

redis:
  enabled: true
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
  persistence:
    enabled: true
    size: 2Gi

celery:
  worker:
    replicaCount: 2
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
    concurrency: 4

  beat:
    enabled: true
    resources:
      requests:
        cpu: 100m
        memory: 128Mi

  flower:
    enabled: true
    resources:
      requests:
        cpu: 100m
        memory: 128Mi

observability:
  prometheus:
    enabled: true
    remoteWrite:
      url: https://prometheus-prod-us-central-0.grafana.net/api/prom/push

  promtail:
    enabled: true
    lokiUrl: https://logs-prod-us-central1.grafana.net/loki/api/v1/push

supabase:
  existingSecret: supabase-secrets
  urlKey: url
  keyKey: key
```

---

## Appendix C: Testing Checklist

### Pre-deployment Testing
- [ ] Helm chart renders without errors (`helm template`)
- [ ] All Docker images build successfully
- [ ] Backend Celery tasks tested locally
- [ ] match-scraper RabbitMQ publisher tested locally
- [ ] Resource limits validated

### Post-deployment Testing
- [ ] All pods running and healthy
- [ ] RabbitMQ Management UI accessible
- [ ] Flower UI accessible
- [ ] Messages flow from match-scraper → RabbitMQ
- [ ] Celery workers consume messages
- [ ] Matches appear in Supabase database
- [ ] Grafana Cloud receives metrics
- [ ] Logs visible in Grafana Loki

### Integration Testing
- [ ] End-to-end: scrape → publish → process → DB
- [ ] Failure scenarios: worker crash, RabbitMQ restart
- [ ] Scale testing: multiple matches simultaneously
- [ ] Performance testing: latency measurements
- [ ] Rollback testing: revert to HTTP mode

### Production Validation
- [ ] GKE backend still serves public traffic
- [ ] dev.missingtable.com accessible and fast
- [ ] No data loss during migration
- [ ] Monitoring alerts configured
- [ ] Documentation updated

---

## Approval and Sign-off

**Proposed by:** Technical discussion
**Reviewed by:** [To be filled]
**Approved by:** [To be filled]
**Target Start Date:** Post-beta launch (after Oct 2025 weekend event)
**Estimated Completion:** 4-6 weeks from start

---

**Last Updated:** 2025-10-10
**Status:** Pending approval - ready for implementation after beta validation
