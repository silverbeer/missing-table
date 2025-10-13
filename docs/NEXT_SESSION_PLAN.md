# Next Session: Match-Scraper Direct RabbitMQ Integration

**Date Created**: 2025-10-12
**Date Revised**: 2025-10-13
**Priority**: High
**Estimated Time**: 2-3 hours

## Context

Currently, match-scraper posts to the missing-table backend API, which then queues tasks to RabbitMQ/Celery. This creates a dependency on the backend API - if the backend is down, match submissions fail.

**Current Architecture** (Option 1):
```
Match-Scraper → HTTP API → Backend → RabbitMQ → Celery Workers
                            ❌ Single point of failure
```

**Target Architecture** (Option 2):
```
Match-Scraper → RabbitMQ (direct) → Celery Workers
               ✅ No backend dependency
               ✅ Message-based contract (no code sharing)
```

## What Was Completed This Session

✅ **Score Update Feature**: Implemented intelligent score updates in Celery workers
- Detects when matches need updating (status/score changes)
- Updates existing matches instead of skipping
- Deployed to GKE successfully

✅ **Documentation Updates**:
- Updated match-scraper integration guide
- Updated architecture documentation
- Updated GKE status documentation

✅ **Message Contract Design** (NEW):
- Created JSON Schema as single source of truth
- No shared Python code between repos (intentional decoupling)
- Contract-based validation in both repos

## Architecture Decision: Message-Based Contracts

### Why NOT Share Python Code

**Problem with shared packages**:
- ❌ Creates deployment dependency between repos
- ❌ Version coordination nightmare
- ❌ Can't deploy independently
- ❌ Testing requires both repos

**Solution: Message contracts**:
- ✅ JSON Schema as canonical contract
- ✅ Each repo has its own Pydantic models (duplicated)
- ✅ Contract tests ensure models stay in sync
- ✅ No cross-repo dependencies

### How Message Contracts Work

**Producer (match-scraper)**: Just sends JSON messages
```python
# No imports from missing-table!
app.send_task(
    'missing_table.tasks.process_match_data',  # Task name (string)
    args=[match_data],                          # JSON payload
    queue='matches'
)
```

**Consumer (celery worker)**: Receives and validates
```python
@app.task(name='missing_table.tasks.process_match_data')
def process_match_data(match_data: dict):
    validated = MatchData(**match_data)  # Pydantic validation
    # Process...
```

**Contract**: JSON Schema in docs (single source of truth)
- `docs/08-integrations/match-message-schema.json`

## Implementation Plan for Next Session

### Phase 1: Add Celery to Match-Scraper (~20 min)

**Files to modify**:
- `match-scraper/pyproject.toml` - Add dependencies

**Commands**:
```bash
cd /Users/silverbeer/gitrepos/match-scraper

# Add celery and kombu
uv add celery kombu
```

**Dependencies added**:
- `celery>=5.3.0` - Task queue framework
- `kombu>=5.3.0` - RabbitMQ messaging library

---

### Phase 2: Create Pydantic Models in Both Repos (~30 min)

**Key insight**: We INTENTIONALLY duplicate the model to avoid dependency hell.

#### 2a. Missing-Table Model (Already exists? Check and update)

**File**: `missing-table/backend/models/match_data.py`

```python
from pydantic import BaseModel, Field
from datetime import date
from typing import Literal

class MatchData(BaseModel):
    """Match data model - must match match-message-schema.json"""

    # Required fields
    home_team: str = Field(..., min_length=1)
    away_team: str = Field(..., min_length=1)
    date: date
    season: str = Field(..., min_length=1)
    age_group: str = Field(..., min_length=1)
    match_type: str = Field(..., min_length=1)

    # Optional fields
    division: str | None = None
    score_home: int | None = Field(None, ge=0)
    score_away: int | None = Field(None, ge=0)
    status: Literal["scheduled", "completed", "postponed", "cancelled"] | None = None
    match_id: str | None = None
    location: str | None = None
    notes: str | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "home_team": "Chicago Fire Juniors",
                    "away_team": "Indiana Fire Academy",
                    "date": "2025-10-13",
                    "season": "2024-25",
                    "age_group": "U14",
                    "match_type": "League",
                    "division": "Northeast",
                    "score_home": 2,
                    "score_away": 1,
                    "status": "completed"
                }
            ]
        }
```

#### 2b. Match-Scraper Model (NEW - duplicate of above)

**File**: `match-scraper/src/models/match_data.py`

```python
# SAME model definition as missing-table
# This is INTENTIONAL duplication to avoid cross-repo dependency
from pydantic import BaseModel, Field
from datetime import date
from typing import Literal

class MatchData(BaseModel):
    """Match data model - must match match-message-schema.json

    NOTE: This is a duplicate of the model in missing-table/backend.
    This is intentional to avoid cross-repo dependencies.
    Contract is enforced via match-message-schema.json and tests.
    """

    # Required fields
    home_team: str = Field(..., min_length=1)
    away_team: str = Field(..., min_length=1)
    date: date
    season: str = Field(..., min_length=1)
    age_group: str = Field(..., min_length=1)
    match_type: str = Field(..., min_length=1)

    # Optional fields
    division: str | None = None
    score_home: int | None = Field(None, ge=0)
    score_away: int | None = Field(None, ge=0)
    status: Literal["scheduled", "completed", "postponed", "cancelled"] | None = None
    match_id: str | None = None
    location: str | None = None
    notes: str | None = None
```

#### 2c. Contract Tests (CRITICAL - prevents drift)

**File**: `missing-table/backend/tests/test_match_contract.py`

```python
import json
from pathlib import Path
from models.match_data import MatchData

def test_match_data_matches_schema():
    """Ensure Pydantic model matches JSON schema contract."""
    schema_path = Path(__file__).parent.parent.parent / "docs/08-integrations/match-message-schema.json"
    schema = json.loads(schema_path.read_text())

    # Test required fields
    required_fields = set(schema['required'])
    model_required = {
        f for f, field in MatchData.model_fields.items()
        if field.is_required()
    }
    assert required_fields == model_required, \
        f"Required fields mismatch. Schema: {required_fields}, Model: {model_required}"

    # Test valid message
    valid_data = schema['examples'][0]
    model = MatchData(**valid_data)
    assert model.home_team == valid_data['home_team']
```

**File**: `match-scraper/tests/test_match_contract.py`

```python
# SAME test in match-scraper
# If schemas drift, this test will fail in CI
import json
from pathlib import Path
from src.models.match_data import MatchData

def test_match_data_matches_schema():
    """Ensure Pydantic model matches JSON schema contract."""
    # In match-scraper, we need to reference the schema from missing-table docs
    # Option 1: Copy schema to match-scraper during build
    # Option 2: Fetch from URL in CI
    # For now, we'll assume schema is copied
    schema_path = Path(__file__).parent.parent / "schemas/match-message-schema.json"
    schema = json.loads(schema_path.read_text())

    required_fields = set(schema['required'])
    model_required = {
        f for f, field in MatchData.model_fields.items()
        if field.is_required()
    }
    assert required_fields == model_required
```

---

### Phase 3: Create Celery Client in Match-Scraper (~30 min)

**File**: `match-scraper/src/celery/queue_client.py` (NEW)

```python
"""
Celery client for submitting matches to RabbitMQ.

This client sends messages to the task queue without knowing
the implementation details of the worker. Contract is enforced
via the MatchData Pydantic model and JSON schema.
"""
import os
from celery import Celery
from src.models.match_data import MatchData
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MatchQueueClient:
    """Client for submitting matches to RabbitMQ/Celery."""

    def __init__(self, broker_url: Optional[str] = None):
        """
        Initialize Celery client.

        Args:
            broker_url: RabbitMQ connection URL. Defaults to RABBITMQ_URL env var.
        """
        self.broker_url = broker_url or os.getenv(
            'RABBITMQ_URL',
            'amqp://admin:admin123@localhost:5672//'  # pragma: allowlist secret
        )

        self.app = Celery(
            'match_scraper',
            broker=self.broker_url
        )

        logger.info(f"Initialized Celery client with broker: {self.broker_url}")

    def submit_match(self, match_data: dict) -> str:
        """
        Submit match data to RabbitMQ queue.

        Args:
            match_data: Match data dictionary (will be validated)

        Returns:
            Task ID for tracking

        Raises:
            ValidationError: If match_data doesn't match schema
        """
        # Validate before sending (fails fast)
        validated = MatchData(**match_data)

        # Send to queue
        # Task name must match the worker's task definition
        result = self.app.send_task(
            'missing_table.tasks.process_match_data',  # Task name
            args=[validated.model_dump(mode='json')],   # Serialize to dict
            queue='matches',                            # Queue name
            routing_key='matches'                       # Routing key
        )

        logger.info(f"Submitted match to queue: {result.id}")
        return result.id

    def submit_matches_batch(self, matches: list[dict]) -> list[str]:
        """
        Submit multiple matches in batch.

        Args:
            matches: List of match data dictionaries

        Returns:
            List of task IDs
        """
        task_ids = []
        for match_data in matches:
            try:
                task_id = self.submit_match(match_data)
                task_ids.append(task_id)
            except Exception as e:
                logger.error(f"Failed to submit match: {e}")
                # Continue with other matches

        return task_ids
```

**File**: `match-scraper/src/scraper/config.py` (UPDATE - add RabbitMQ URL)

```python
# Add to existing config
RABBITMQ_URL = os.getenv(
    'RABBITMQ_URL',
    'amqp://admin:admin123@localhost:5672//'  # pragma: allowlist secret
)
```

---

### Phase 4: Update Match-Scraper CLI (~20 min)

**File**: `match-scraper/src/cli/main.py` (UPDATE)

Add option to use Celery queue instead of HTTP API:

```python
import typer
from src.celery.queue_client import MatchQueueClient
from src.api.missing_table_client import MissingTableClient  # Existing HTTP client

app = typer.Typer()

@app.command()
def scrape(
    age_group: str = typer.Option(..., "-a", "--age-group"),
    division: str = typer.Option(..., "-d", "--division"),
    use_queue: bool = typer.Option(False, "--use-queue", help="Submit to RabbitMQ instead of HTTP API"),
):
    """Scrape matches and submit to missing-table."""

    # Scrape matches (existing code)
    matches = scraper.scrape(age_group, division)

    if use_queue:
        # NEW: Submit via RabbitMQ
        client = MatchQueueClient()
        task_ids = client.submit_matches_batch(matches)
        typer.echo(f"✅ Submitted {len(task_ids)} matches to queue")
    else:
        # Existing: Submit via HTTP API
        client = MissingTableClient()
        client.submit_matches(matches)
        typer.echo(f"✅ Submitted {len(matches)} matches to API")
```

---

### Phase 5: Create Match-Scraper Dockerfile (~15 min)

**File**: `match-scraper/Dockerfile` (NEW)

```dockerfile
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Install Playwright browsers
RUN uv run playwright install chromium --with-deps

# Copy application code
COPY . .

# Default command (can be overridden by CronJob)
CMD ["uv", "run", "mls-scraper", "scrape", \
     "--age-group", "U14", \
     "--division", "Northeast", \
     "--use-queue"]
```

---

### Phase 6: Create Kubernetes CronJob (~20 min)

**File**: `missing-table/k8s/match-scraper-cronjob.yaml` (NEW)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: match-scraper
  namespace: missing-table-dev
  labels:
    app: match-scraper
    component: scraper
spec:
  # Run every 6 hours (adjust as needed)
  schedule: "0 */6 * * *"

  # Don't allow concurrent scraping jobs
  concurrencyPolicy: Forbid

  # Keep history for debugging
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3

  jobTemplate:
    metadata:
      labels:
        app: match-scraper
        component: scraper
    spec:
      # Don't retry too many times (scraper handles retries internally)
      backoffLimit: 2

      template:
        metadata:
          labels:
            app: match-scraper
            component: scraper
        spec:
          restartPolicy: OnFailure

          containers:
          - name: match-scraper
            image: us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest
            imagePullPolicy: Always

            env:
            # RabbitMQ connection
            - name: RABBITMQ_URL
              valueFrom:
                secretKeyRef:
                  name: missing-table-secrets
                  key: rabbitmq-url

            # Scraper configuration
            - name: AGE_GROUP
              value: "U14"
            - name: DIVISION
              value: "Northeast"
            - name: LOG_LEVEL
              value: "INFO"

            resources:
              requests:
                memory: "512Mi"
                cpu: "500m"
              limits:
                memory: "1Gi"
                cpu: "1000m"

            # Health check (optional)
            livenessProbe:
              exec:
                command:
                - pgrep
                - python
              initialDelaySeconds: 30
              periodSeconds: 30
              failureThreshold: 3
```

**File**: `missing-table/helm/missing-table/templates/secrets.yaml` (UPDATE)

Add RabbitMQ URL to secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: missing-table-secrets
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  # Existing secrets...

  # RabbitMQ connection
  rabbitmq-url: "amqp://{{ .Values.rabbitmq.username }}:{{ .Values.rabbitmq.password }}@messaging-rabbitmq.messaging:5672//"
```

---

### Phase 7: Build & Deploy (~30 min)

#### 7a. Build and Push Match-Scraper Image

```bash
# Switch to match-scraper repo
cd /Users/silverbeer/gitrepos/match-scraper

# Build for GKE (AMD64 platform)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest \
  .

# Push to Google Artifact Registry
docker push us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest
```

#### 7b. Deploy CronJob to GKE

```bash
# Switch to GKE context
kubectl config use-context gke_missing-table_us-central1_missing-table-dev

# Apply CronJob manifest
kubectl apply -f /Users/silverbeer/gitrepos/missing-table/k8s/match-scraper-cronjob.yaml

# Verify CronJob created
kubectl get cronjobs -n missing-table-dev
```

#### 7c. Test Manually (Don't wait for schedule)

```bash
# Create a one-time job from the CronJob
kubectl create job --from=cronjob/match-scraper match-scraper-test-1 -n missing-table-dev

# Watch job status
kubectl get jobs -n missing-table-dev -w

# Check logs
kubectl logs -f job/match-scraper-test-1 -n missing-table-dev

# Check if tasks appeared in RabbitMQ
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672
# Open http://localhost:15672 (admin/admin123)
# Check "Queues" tab for "matches" queue
```

---

## Learning Opportunities (Interview Prep)

As you implement this, focus on understanding:

### 1. Message Queue Fundamentals
- **What is a message broker?** RabbitMQ holds messages between producer and consumer
- **Why use queues?** Decoupling, resilience, load balancing, async processing
- **AMQP protocol**: Advanced Message Queuing Protocol (RabbitMQ's protocol)

### 2. Celery Architecture
- **Producer**: Sends messages to queue (match-scraper)
- **Broker**: Holds messages (RabbitMQ)
- **Worker**: Processes messages (celery workers)
- **Result backend**: Stores task results (optional, we use Redis)

### 3. Distributed Systems Patterns
- **Message contracts**: JSON schema as contract between services
- **Intentional duplication**: Sometimes duplication > dependency
- **Circuit breaker**: If API fails, queue still works
- **Idempotency**: Same message processed twice = same result

### 4. Kubernetes Workloads
- **CronJob**: Scheduled task runner (like cron on Linux)
- **Job**: One-time task execution
- **Pod lifecycle**: How containers start, run, and stop

### 5. Interview Sound Bites

Practice explaining:
- "I built a distributed task processing system using RabbitMQ and Celery"
- "We used message-based contracts to decouple services without shared code"
- "The scraper can push work to the queue even if the API is down"
- "Used Kubernetes CronJobs for scheduled scraping with automatic retries"
- "Implemented idempotent message processing to handle duplicate submissions"

---

## Benefits of This Approach

✅ **Resilience**: Match-scraper works even if backend API is down
✅ **Decoupling**: No code dependencies between repos
✅ **Security**: RabbitMQ stays internal to cluster
✅ **Simplicity**: Just send JSON messages
✅ **Scheduling**: Automatic via CronJob
✅ **Scalability**: Easy to add more workers
✅ **Observability**: Monitor queue depth in RabbitMQ UI
✅ **Interview-ready**: Real distributed systems experience

---

## Key Decisions Made

1. ✅ **Message-based contracts** (not shared Python code)
2. ✅ **Duplicate Pydantic models** (intentional decoupling)
3. ✅ **Deploy as GKE CronJob** (not external)
4. ✅ **Keep HTTP API** as backup for manual submissions
5. ✅ **Schedule: Every 6 hours** (adjustable)
6. ✅ **Contract tests** in CI to prevent drift

---

## Files That Will Be Created/Modified

### New Files:
- ✅ `docs/08-integrations/match-message-schema.json` - Message contract (DONE)
- `match-scraper/src/models/match_data.py` - Pydantic model
- `match-scraper/src/celery/queue_client.py` - Celery client
- `match-scraper/Dockerfile` - Container image
- `match-scraper/tests/test_match_contract.py` - Contract test
- `missing-table/k8s/match-scraper-cronjob.yaml` - K8s CronJob
- `missing-table/backend/tests/test_match_contract.py` - Contract test

### Modified Files:
- `match-scraper/pyproject.toml` - Add celery, kombu
- `match-scraper/src/cli/main.py` - Add --use-queue option
- `match-scraper/src/scraper/config.py` - Add RABBITMQ_URL
- `missing-table/helm/missing-table/templates/secrets.yaml` - Add rabbitmq-url
- `missing-table/backend/models/match_data.py` - May need to create/update

---

## Testing Checklist

### Local Testing:
- [ ] Celery client can connect to RabbitMQ locally
- [ ] Message validation works (Pydantic)
- [ ] Contract tests pass in both repos
- [ ] Tasks appear in RabbitMQ queue

### GKE Testing:
- [ ] Docker image builds for AMD64
- [ ] Image pushes to Artifact Registry
- [ ] CronJob creates successfully
- [ ] Manual job runs successfully
- [ ] Tasks reach RabbitMQ in GKE
- [ ] Workers pick up and process tasks
- [ ] Match data inserted into database
- [ ] Logs accessible via kubectl

### Edge Cases:
- [ ] Invalid message rejected (schema validation)
- [ ] Duplicate matches handled correctly
- [ ] Worker failure retries task
- [ ] Queue survives backend API restart

---

## Rollback Plan

If issues arise:
1. ✅ Keep HTTP API endpoint active (already exists)
2. ✅ Switch match-scraper back to HTTP mode (default behavior)
3. ✅ Delete CronJob: `kubectl delete cronjob match-scraper -n missing-table-dev`
4. ✅ No data loss (backend API still works)

---

## Questions to Answer During Implementation

1. Does RabbitMQ in GKE have persistent storage? (Check PVC)
2. Should we add dead-letter queue for failed tasks?
3. What's the right scraping frequency? (currently 6 hours)
4. Do we need task result tracking? (task IDs in database)
5. Should CronJob scrape multiple age groups/divisions?

---

## Next Steps

1. ✅ Review this revised plan
2. Start fresh session
3. Follow implementation phases 1-7
4. Test thoroughly (local → GKE)
5. Update documentation
6. Monitor first few scheduled runs
7. Practice explaining the system for interviews

---

**Ready to build!** This will give you real distributed systems experience to talk about in interviews.

**Last Updated**: 2025-10-13
