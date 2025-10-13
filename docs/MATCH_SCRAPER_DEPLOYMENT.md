# Match-Scraper GKE Deployment Guide

Complete guide for deploying the match-scraper with direct RabbitMQ integration to Google Kubernetes Engine.

**Last Updated**: 2025-10-13
**Status**: ✅ Ready for deployment

## Architecture

```
Match-Scraper (GKE CronJob)
    ↓ (RabbitMQ messages)
RabbitMQ Queue (missing-table-dev namespace)
    ↓
Celery Workers (missing-table-dev namespace)
    ↓
Supabase Database
```

**Key Benefits:**
- ✅ No HTTP API dependency for match submission
- ✅ Resilient (works even if backend API is down)
- ✅ Decoupled services via message queue
- ✅ Automatic scheduling with Kubernetes CronJob
- ✅ Scalable (easy to add more workers)

## Prerequisites

1. **Docker** installed locally
2. **kubectl** configured for GKE cluster
3. **gcloud** CLI authenticated
4. **GKE cluster** running with `missing-table-dev` namespace
5. **RabbitMQ** deployed in the cluster
6. **Celery workers** running in the cluster

## Deployment Steps

### Step 1: Build Docker Image

```bash
# Navigate to match-scraper repo
cd /Users/silverbeer/gitrepos/match-scraper

# Build for GKE (AMD64 platform)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest \
  .

# Build takes ~5-10 minutes (Playwright browsers are large)
```

### Step 2: Push to Google Artifact Registry

```bash
# Authenticate with Google Cloud
gcloud auth configure-docker us-central1-docker.pkg.dev

# Push image
docker push us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest
```

### Step 3: Update Helm Values (RabbitMQ Configuration)

Edit `helm/missing-table/values-dev.yaml` (this file is gitignored):

```yaml
# Add RabbitMQ configuration
rabbitmq:
  username: admin
  password: admin123  # Use your actual password
  host: messaging-rabbitmq.missing-table-dev.svc.cluster.local
  port: 5672
```

**Note**: RabbitMQ host format depends on where RabbitMQ is deployed:
- Same namespace: `messaging-rabbitmq`
- Different namespace: `messaging-rabbitmq.messaging.svc.cluster.local`
- External: Full hostname/IP

### Step 4: Deploy Updated Secrets

The secrets template now includes `rabbitmq-url`:

```bash
# Switch to GKE context
kubectl config use-context gke_missing-table_us-central1_missing-table-dev

# Deploy/update Helm release (updates secrets)
cd /Users/silverbeer/gitrepos/missing-table
helm upgrade missing-table ./helm/missing-table \
  -n missing-table-dev \
  --values ./helm/missing-table/values-dev.yaml \
  --wait

# Verify secret was created
kubectl get secret missing-table-secrets -n missing-table-dev -o yaml | grep rabbitmq-url
```

### Step 5: Deploy CronJob

```bash
# Apply the CronJob manifest
kubectl apply -f k8s/match-scraper-cronjob.yaml

# Verify CronJob was created
kubectl get cronjobs -n missing-table-dev
```

Expected output:
```
NAME             SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
match-scraper    0 */6 * * *   False     0        <none>          5s
```

### Step 6: Test Manual Job Run

Don't wait for the schedule - test immediately:

```bash
# Create a test job from the CronJob
kubectl create job --from=cronjob/match-scraper match-scraper-test-1 -n missing-table-dev

# Watch job status
kubectl get jobs -n missing-table-dev -w

# Check logs (real-time)
kubectl logs -f job/match-scraper-test-1 -n missing-table-dev
```

Expected log output:
```
✓ Celery client initialized with broker: amqp://admin:***@messaging-rabbitmq:5672//
✓ RabbitMQ connection successful
🌐 Initializing browser...
✓ Match submitted to queue: abc123-def456-...
✓ Batch complete: 15 submitted, 0 failed
```

### Step 7: Verify Messages in RabbitMQ

```bash
# Port-forward to RabbitMQ management UI
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672

# Open browser: http://localhost:15672
# Login: admin / admin123
# Navigate to "Queues" tab
# Look for "matches" queue with messages
```

### Step 8: Monitor Celery Workers

```bash
# Check worker logs
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker --tail=50 -f

# Expected: Worker picking up tasks and processing matches
```

## Configuration

### Customize Scraping

Edit `k8s/match-scraper-cronjob.yaml`:

```yaml
env:
- name: AGE_GROUP
  value: "U16"  # Change age group

- name: DIVISION
  value: "Southwest"  # Change division
```

### Change Schedule

Edit the `schedule` field in `k8s/match-scraper-cronjob.yaml`:

```yaml
spec:
  schedule: "0 9 * * *"  # Daily at 9am UTC
```

Cron format: `minute hour day month weekday`

Examples:
- `0 */6 * * *` - Every 6 hours
- `0 9 * * *` - Daily at 9am
- `0 0,6,12,18 * * *` - 4 times daily (midnight, 6am, noon, 6pm)
- `*/30 * * * *` - Every 30 minutes

### Resource Limits

Adjust in `k8s/match-scraper-cronjob.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"  # Increase if OOM errors
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

## Troubleshooting

### Job Fails to Start

```bash
# Check job status
kubectl describe job match-scraper-test-1 -n missing-table-dev

# Common issues:
# - Image pull errors (check image name/tag)
# - Secret not found (check missing-table-secrets exists)
# - Resource limits too low
```

### RabbitMQ Connection Fails

```bash
# Check if RabbitMQ is running
kubectl get pods -n missing-table-dev | grep rabbitmq

# Check RabbitMQ service
kubectl get svc -n missing-table-dev | grep rabbitmq

# Test connection from inside cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n missing-table-dev -- \
  curl -u admin:admin123 http://messaging-rabbitmq:15672/api/overview
```

### Messages Not Being Processed

```bash
# Check Celery workers are running
kubectl get pods -n missing-table-dev | grep celery-worker

# Check worker logs
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker --tail=100

# Check RabbitMQ queue depth (should be decreasing)
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672
# Open http://localhost:15672 and check "matches" queue
```

### Pod Crashes (OOM)

```bash
# Check pod events
kubectl describe pod <pod-name> -n missing-table-dev

# Increase memory limits if seeing "OOMKilled"
# Edit k8s/match-scraper-cronjob.yaml and increase resources.limits.memory
```

## Operational Commands

### Pause CronJob

```bash
# Temporarily suspend scheduled runs
kubectl patch cronjob match-scraper -n missing-table-dev \
  -p '{"spec":{"suspend":true}}'
```

### Resume CronJob

```bash
kubectl patch cronjob match-scraper -n missing-table-dev \
  -p '{"spec":{"suspend":false}}'
```

### Delete CronJob

```bash
# Stop all scheduled runs
kubectl delete cronjob match-scraper -n missing-table-dev

# Also delete any running jobs
kubectl delete jobs -l app=match-scraper -n missing-table-dev
```

### Update Image

```bash
# After building new image with same tag:

# Force pull latest image
kubectl patch cronjob match-scraper -n missing-table-dev \
  -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"match-scraper","imagePullPolicy":"Always"}]}}}}}}'

# Or delete and recreate CronJob
kubectl delete cronjob match-scraper -n missing-table-dev
kubectl apply -f k8s/match-scraper-cronjob.yaml
```

### View Recent Job Runs

```bash
# List all jobs created by CronJob
kubectl get jobs -n missing-table-dev --selector=app=match-scraper

# View details of specific job
kubectl describe job <job-name> -n missing-table-dev

# Get logs from specific job
kubectl logs job/<job-name> -n missing-table-dev
```

## Cost Optimization

### Reduce Scraping Frequency

Less frequent scraping = lower costs:

```yaml
# Change from every 6 hours to daily
schedule: "0 9 * * *"
```

### Lower Resource Limits

If scraper completes successfully with lower resources:

```yaml
resources:
  requests:
    memory: "256Mi"  # Reduced from 512Mi
    cpu: "250m"      # Reduced from 500m
```

### Shorter Job History

Reduce storage by keeping fewer completed jobs:

```yaml
successfulJobsHistoryLimit: 1  # Keep only 1 (was 3)
failedJobsHistoryLimit: 1
```

## Monitoring

### Check CronJob Health

```bash
# View CronJob details
kubectl describe cronjob match-scraper -n missing-table-dev

# Check recent job runs
kubectl get jobs -n missing-table-dev --selector=app=match-scraper --sort-by=.metadata.creationTimestamp

# Count successful vs failed jobs
kubectl get jobs -n missing-table-dev --selector=app=match-scraper \
  --field-selector status.successful=1 | wc -l
```

### Set Up Alerts (Optional)

Use Google Cloud Monitoring to alert on:
- Job failures (status != successful)
- Job duration > 30 minutes
- RabbitMQ queue depth > 100 messages

## Rollback

If you need to revert to HTTP API submission:

```bash
# Option 1: Suspend CronJob and use old method
kubectl patch cronjob match-scraper -n missing-table-dev -p '{"spec":{"suspend":true}}'

# Option 2: Change CronJob to use HTTP API
# Edit k8s/match-scraper-cronjob.yaml:
# Replace: --use-queue --no-api
# With: --async-api
kubectl apply -f k8s/match-scraper-cronjob.yaml
```

## Next Steps

1. **Monitor first few runs** - Check logs and RabbitMQ
2. **Adjust schedule** - Based on match data update frequency
3. **Add more age groups/divisions** - Create multiple CronJobs if needed
4. **Set up alerts** - Get notified of failures
5. **Document learnings** - Update this guide with operational insights

## Related Documentation

- [RabbitMQ/Celery Architecture](./08-integrations/match-scraper.md)
- [Message Contract](./08-integrations/match-message-schema.json)
- [Implementation Plan](./NEXT_SESSION_PLAN.md)
- [GKE Status](./GKE_CURRENT_STATUS.md)

---

**Questions?** Check logs first, then review troubleshooting section above.
