# Celery Worker Deployment for K3s

> **One worker runs in this namespace.** `deployment-prod.yaml` defines
> `missing-table-celery-worker-prod`, which consumes `matches.prod` and writes
> to the **cloud** Supabase. Its config is `missing-table-worker-prod-config`
> and `missing-table-worker-prod-secrets`.
>
> There is no local-database worker, and there is no need for one: local
> testing is covered by backup/restore (`./scripts/setup-local-db.sh
> --from-prod`). The cloud Supabase is the system of record; match-scraper
> writes to it, and local is synced from a backup, never from the queue.
>
> A second deployment, `missing-table-celery-worker-local`, was retired in
> SB-854. It consumed `matches` and wrote to the same cloud database, so the
> `-local` in its name described neither its queue nor its database. Nothing
> published to `matches`, so it had processed zero tasks while implying a
> safety that never existed — a naming that had already put 9 fixtures into
> production during what was believed to be a local test.
>
> It is not in LKE. No Celery worker or RabbitMQ runs there, so External
> Secrets Operator and AWS Secrets Manager do not feed it — its config is the
> ConfigMap and Secret in this namespace.


This directory contains Kubernetes manifests for deploying Celery workers to K3s (Rancher Desktop).

## Architecture

- **RabbitMQ**: Message broker (running in k3s)
- **Redis**: Result backend (running in k3s)
- **Celery Workers**: Process match data from match-scraper
- **Supabase**: Database (cloud - dev or prod)

## Files

### Active Configuration
- `deployment-prod.yaml` - The worker deployment (consumes `matches.prod`)
- `configmap-dev.yaml` / `secret-dev.yaml` - Dev config, for a `matches.dev`
  worker that is not currently deployed

### Templates
- `configmap-prod.yaml.template` - Prod config template
- `secret-prod.yaml.template` - Prod secrets template

## Quick Start

### 1. Build Worker Image
```bash
# From repo root
docker build -f backend/Dockerfile -t missing-table-worker:latest backend/
```

### 2. Deploy to K3s
```bash
# Make sure you're on the right context
kubectl config use-context rancher-desktop

kubectl apply -f k3s/worker/deployment-prod.yaml
```

This worker writes to the **cloud** Supabase. Applying it is a production
action.

### 3. Verify Deployment
```bash
# Check pods
kubectl get pods -n match-scraper -l app=missing-table-worker

# Check logs
kubectl logs -n match-scraper -l app=missing-table-worker --tail=50 -f

# Check RabbitMQ queues
kubectl exec -n match-scraper messaging-rabbitmq-0 -- rabbitmqctl list_queues
```

## Which database does the worker write to?

The cloud one. There is no switch, and `switch-worker-env.sh` was removed in
SB-854 along with the worker it pointed at — it targeted a deployment
(`missing-table-celery-worker`) that had not existed since the workers were
split, so it had been failing rather than switching anything.

To get production data locally, restore a backup:

```bash
./scripts/setup-local-db.sh --from-prod   # backup prod, then restore into local
```

That is the only supported direction. The queue never writes to a local
database.

## Setting Up Production

1. **Create Production Supabase Project**
   - Go to https://supabase.com/dashboard
   - Create new project: "missing-table-prod"
   - Wait for provisioning

2. **Get Credentials**
   - Go to Project Settings → API
   - Copy Project URL, anon key, service_role key
   - Copy JWT Secret from JWT Settings

3. **Create Production Manifests**
   ```bash
   # Copy templates
   cp k3s/worker/configmap-prod.yaml.template k3s/worker/configmap-prod.yaml
   cp k3s/worker/secret-prod.yaml.template k3s/worker/secret-prod.yaml

   # Edit and fill in real credentials
   vim k3s/worker/configmap-prod.yaml
   vim k3s/worker/secret-prod.yaml
   ```

4. **Deploy Production**
   ```bash
   kubectl apply -f k3s/worker/configmap-prod.yaml
   kubectl apply -f k3s/worker/secret-prod.yaml
   kubectl apply -f k3s/worker/deployment-prod.yaml
   ```

## Scaling Workers

```bash
# Scale to 4 workers
kubectl scale deployment/missing-table-celery-worker-prod -n match-scraper --replicas=4

# Scale down to 1 worker
kubectl scale deployment/missing-table-celery-worker-prod -n match-scraper --replicas=1
```

## Monitoring

### Worker Status
```bash
# Get worker pods
kubectl get pods -n match-scraper -l app=missing-table-worker

# Describe pod for details
kubectl describe pod -n match-scraper <pod-name>
```

### Worker Logs
```bash
# Tail logs from all workers
kubectl logs -n match-scraper -l app=missing-table-worker --tail=100 -f

# Logs from specific pod
kubectl logs -n match-scraper <pod-name> -f
```

### RabbitMQ Monitoring
```bash
# List queues with message counts
kubectl exec -n match-scraper messaging-rabbitmq-0 -- rabbitmqctl list_queues name messages consumers

# RabbitMQ Management UI
kubectl port-forward -n match-scraper messaging-rabbitmq-0 15672:15672
# Open http://localhost:15672 (admin/admin123)
```

### Redis Monitoring
```bash
# Check Redis keys
kubectl exec -n match-scraper messaging-redis-0 -- redis-cli keys "celery-*"

# Monitor Redis commands
kubectl exec -n match-scraper messaging-redis-0 -- redis-cli monitor
```

## Troubleshooting

### Workers Not Starting
```bash
# Check pod events
kubectl describe pod -n match-scraper <pod-name>

# Check logs for errors
kubectl logs -n match-scraper <pod-name>

# Verify ConfigMap and Secret exist
kubectl get configmap -n match-scraper missing-table-worker-prod-config
kubectl get secret -n match-scraper missing-table-worker-prod-secrets
```

### Workers Not Processing Messages
```bash
# Check if workers are connected to RabbitMQ
kubectl logs -n match-scraper -l app=missing-table-worker | grep "Connected to amqp"

# Check RabbitMQ connections
kubectl exec -n match-scraper messaging-rabbitmq-0 -- rabbitmqctl list_connections

# Verify queue bindings
kubectl exec -n match-scraper messaging-rabbitmq-0 -- rabbitmqctl list_bindings
```

### Database Connection Issues
```bash
# Check Supabase URL in ConfigMap
kubectl get configmap -n match-scraper missing-table-worker-prod-config -o yaml

# Test database connection from pod
kubectl exec -n match-scraper <pod-name> -- uv run python -c "from dao.enhanced_data_access_fixed import SupabaseConnection; print(SupabaseConnection().client.table('teams').select('count').execute())"
```

### Rebuild and Redeploy
```bash
# Rebuild image
docker build -f backend/Dockerfile -t missing-table-worker:latest backend/

# Restart deployment (picks up new image)
kubectl rollout restart deployment/missing-table-celery-worker-prod -n match-scraper

# Watch rollout status
kubectl rollout status deployment/missing-table-celery-worker-prod -n match-scraper
```

## Configuration Details

### Environment Variables

**From ConfigMap:**
- `RABBITMQ_URL` - RabbitMQ connection string
- `CELERY_BROKER_URL` - Celery broker URL (same as RabbitMQ)
- `REDIS_URL` - Redis connection string
- `SUPABASE_URL` - Supabase project URL
- `ENVIRONMENT` - production
- `LOG_LEVEL` - Logging level (INFO, DEBUG, WARNING)

**From Secret:**
- `SUPABASE_SERVICE_KEY` - Supabase service role key (full DB access)
- `SUPABASE_JWT_SECRET` - JWT verification secret
- `SERVICE_ACCOUNT_SECRET` - API authentication secret

### Worker Configuration

- **Queues**: `matches.prod` — the only queue match-scraper publishes to
- **Concurrency**: 2 tasks per worker
- **Log Level**: INFO
- **Replicas**: 1

### Resource Limits

- **Requests**: 512Mi memory, 250m CPU
- **Limits**: 1Gi memory, 500m CPU

Adjust in `deployment.yaml` if needed.

## Security Notes

- ⚠️ **Never commit** `secret-dev.yaml` or `secret-prod.yaml` to git (already in .gitignore)
- ⚠️ **Keep templates** (`.template` files) in git for reference
- ⚠️ **Rotate secrets** regularly (every 90 days minimum)
- ⚠️ **Use different credentials** for dev and prod
- ⚠️ **Service role keys** have full database access - protect them!