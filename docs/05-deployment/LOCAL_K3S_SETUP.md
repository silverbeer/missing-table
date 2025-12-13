# Local K3s Messaging Infrastructure Setup

## Summary

This document describes the local K3s (Rancher Desktop) deployment of the messaging infrastructure on MacBook Air.

## What's Deployed

### Namespace: `match-scraper`

**Infrastructure Components:**
- `messaging-rabbitmq-0` - RabbitMQ 3.13-management (1/1 Running)
- `messaging-redis-0` - Redis 7-alpine (1/1 Running)
- `celery-workers` - 2 Celery worker pods (2/2 Running)

**Services:**
- `messaging-rabbitmq.match-scraper.svc.cluster.local:5672` (AMQP)
- `messaging-rabbitmq.match-scraper.svc.cluster.local:15672` (Management UI)
- `messaging-redis.match-scraper.svc.cluster.local:6379`

## Architecture

### Hybrid Deployment Model

```
GKE (Public Services - ~$5/month)
├── missing-table-dev namespace
│   ├── Backend (FastAPI)
│   └── Frontend (Vue.js)
└── missing-table-prod namespace
    ├── Backend (FastAPI)
    └── Frontend (Vue.js)

MacBook Air - Local K3s (Private Messaging - local hardware)
└── match-scraper namespace
    ├── RabbitMQ (message broker)
    ├── Redis (result backend)
    └── Celery Workers (2 replicas)
```

## Deployment Commands

### 1. Deploy RabbitMQ + Redis

```bash
kubectl config use-context rancher-desktop

helm upgrade --install messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  -n match-scraper --create-namespace
```

### 2. Build Backend Image

```bash
cd backend
docker build -t missing-table-backend:local -f Dockerfile .
```

### 3. Import Image to K3s (Rancher Desktop uses containerd)

```bash
docker save missing-table-backend:local | \
  "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/nerdctl" \
  --namespace k8s.io load
```

### 4. Deploy Celery Workers

```bash
helm upgrade --install celery-workers ./helm/missing-table \
  --values ./helm/missing-table/values-celery-workers-local.yaml \
  -n match-scraper
```

## Verification

```bash
# Check all resources
kubectl get all -n match-scraper

# Check worker logs
kubectl logs -f -n match-scraper deployment/celery-workers-missing-table-celery-worker

# Verify Celery connection
kubectl logs -n match-scraper deployment/celery-workers-missing-table-celery-worker \
  | grep "Connected to amqp"
```

## Configuration Files (Gitignored)

These files contain secrets and are NOT committed to git:

- `helm/messaging-platform/values-local.yaml`
  - RabbitMQ credentials: admin/admin123
  - Redis configuration

- `helm/missing-table/values-celery-workers-local.yaml`
  - Supabase credentials (local instance)
  - RabbitMQ connection settings
  - Redis connection settings

## Worker Configuration

**Celery Worker Details:**
- **Concurrency:** 2 workers per pod (4 total with 2 replicas)
- **Broker:** `amqp://admin:admin123@messaging-rabbitmq.match-scraper.svc.cluster.local:5672//`
- **Result Backend:** `redis://messaging-redis.match-scraper.svc.cluster.local:6379/0`

**Available Queues:**
- `celery` - Default queue
- `match_processing` - Match data processing
- `validation` - Match validation

**Registered Tasks:**
- `celery_tasks.match_tasks.process_match_data`
- `celery_tasks.validation_tasks.validate_match_data`

## Troubleshooting

### Image Pull Issues

If workers show `ErrImageNeverPull` or `ImagePullBackOff`:

1. Verify image exists in Docker:
   ```bash
   docker images | grep missing-table-backend
   ```

2. Import to K3s containerd:
   ```bash
   docker save missing-table-backend:local | \
     "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/nerdctl" \
     --namespace k8s.io load
   ```

3. Restart deployment:
   ```bash
   kubectl rollout restart deployment/celery-workers-missing-table-celery-worker -n match-scraper
   ```

### RabbitMQ Connection Issues

Check RabbitMQ is running:
```bash
kubectl get pods -n match-scraper | grep rabbitmq
kubectl logs -n match-scraper messaging-rabbitmq-0
```

### Celery Worker Not Starting

Check logs:
```bash
kubectl logs -n match-scraper deployment/celery-workers-missing-table-celery-worker --tail=100
```

Common issues:
- Dependencies still installing (wait ~2-3 minutes after pod start)
- Database connection issues (check `host.docker.internal` accessibility)
- RabbitMQ credentials mismatch

## Cost Savings

By running messaging infrastructure locally instead of GKE:
- **Before:** ~$72/month (full GKE deployment)
- **After:** ~$5/month (GKE public services only)
- **Savings:** ~$67/month (~90% reduction)

## Next Steps

1. Configure match-scraper to send jobs to this RabbitMQ instance
2. Test end-to-end workflow (scraper → RabbitMQ → workers → database)
3. (Optional) Implement fanout pattern for dual dev/prod deployment
4. (Optional) Optimize Dockerfile for faster rebuilds

## Related Documentation

- [CLAUDE.md](./CLAUDE.md) - Main development guide
- [docs/rabbitmq-celery/](./docs/rabbitmq-celery/) - RabbitMQ/Celery integration documentation
- [Helm charts](./helm/) - Kubernetes deployment configurations

---

**Last Updated:** 2025-10-22
**Environment:** MacBook Air - Rancher Desktop K3s
