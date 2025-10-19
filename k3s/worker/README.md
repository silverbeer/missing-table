# Celery Worker Deployment for K3s

This directory contains Kubernetes manifests for deploying Celery workers to K3s (Rancher Desktop).

## Architecture

- **RabbitMQ**: Message broker (running in k3s)
- **Redis**: Result backend (running in k3s)
- **Celery Workers**: Process match data from match-scraper
- **Supabase**: Database (cloud - dev or prod)

## Files

### Active Configuration
- `deployment.yaml` - Worker deployment (environment-agnostic)
- `configmap-dev.yaml` - Dev environment config (active)
- `secret-dev.yaml` - Dev Supabase credentials (active)

### Templates
- `configmap-prod.yaml.template` - Prod config template
- `secret-prod.yaml.template` - Prod secrets template

## Quick Start (Dev Environment)

### 1. Build Worker Image
```bash
# From repo root
docker build -f backend/Dockerfile -t missing-table-worker:latest backend/
```

### 2. Deploy to K3s
```bash
# Make sure you're on the right context
kubectl config use-context rancher-desktop

# Apply manifests (dev)
kubectl apply -f k3s/worker/configmap-dev.yaml
kubectl apply -f k3s/worker/secret-dev.yaml
kubectl apply -f k3s/worker/deployment.yaml
```

### 3. Verify Deployment
```bash
# Check pods
kubectl get pods -n match-scraper -l app=missing-table-worker

# Check logs
kubectl logs -n match-scraper -l app=missing-table-worker --tail=50 -f

# Check RabbitMQ queues
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues
```

## Switching Environments (Dev ↔ Prod)

### Using Helper Script (Recommended)
```bash
# Switch to dev
./k3s/worker/switch-worker-env.sh dev

# Switch to prod
./k3s/worker/switch-worker-env.sh prod

# Check current environment
./k3s/worker/switch-worker-env.sh status
```

### Manual Switch
```bash
# Switch to prod
kubectl delete -f k3s/worker/configmap-dev.yaml
kubectl delete -f k3s/worker/secret-dev.yaml
kubectl apply -f k3s/worker/configmap-prod.yaml
kubectl apply -f k3s/worker/secret-prod.yaml
kubectl rollout restart deployment/missing-table-celery-worker -n match-scraper
```

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
   ./k3s/worker/switch-worker-env.sh prod
   ```

## Scaling Workers

```bash
# Scale to 4 workers
kubectl scale deployment/missing-table-celery-worker -n match-scraper --replicas=4

# Scale down to 1 worker
kubectl scale deployment/missing-table-celery-worker -n match-scraper --replicas=1
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
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues name messages consumers

# RabbitMQ Management UI
kubectl port-forward -n match-scraper rabbitmq-0 15672:15672
# Open http://localhost:15672 (admin/admin123)
```

### Redis Monitoring
```bash
# Check Redis keys
kubectl exec -n match-scraper redis-0 -- redis-cli keys "celery-*"

# Monitor Redis commands
kubectl exec -n match-scraper redis-0 -- redis-cli monitor
```

## Troubleshooting

### Workers Not Starting
```bash
# Check pod events
kubectl describe pod -n match-scraper <pod-name>

# Check logs for errors
kubectl logs -n match-scraper <pod-name>

# Verify ConfigMap and Secret exist
kubectl get configmap -n match-scraper missing-table-worker-config
kubectl get secret -n match-scraper missing-table-worker-secrets
```

### Workers Not Processing Messages
```bash
# Check if workers are connected to RabbitMQ
kubectl logs -n match-scraper -l app=missing-table-worker | grep "Connected to amqp"

# Check RabbitMQ connections
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_connections

# Verify queue bindings
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_bindings
```

### Database Connection Issues
```bash
# Check Supabase URL in ConfigMap
kubectl get configmap -n match-scraper missing-table-worker-config -o yaml

# Test database connection from pod
kubectl exec -n match-scraper <pod-name> -- uv run python -c "from dao.enhanced_data_access_fixed import SupabaseConnection; print(SupabaseConnection().client.table('teams').select('count').execute())"
```

### Rebuild and Redeploy
```bash
# Rebuild image
docker build -f backend/Dockerfile -t missing-table-worker:latest backend/

# Restart deployment (picks up new image)
kubectl rollout restart deployment/missing-table-celery-worker -n match-scraper

# Watch rollout status
kubectl rollout status deployment/missing-table-celery-worker -n match-scraper
```

## Configuration Details

### Environment Variables

**From ConfigMap:**
- `RABBITMQ_URL` - RabbitMQ connection string
- `CELERY_BROKER_URL` - Celery broker URL (same as RabbitMQ)
- `REDIS_URL` - Redis connection string
- `SUPABASE_URL` - Supabase project URL
- `ENVIRONMENT` - dev or production
- `LOG_LEVEL` - Logging level (INFO, DEBUG, WARNING)

**From Secret:**
- `SUPABASE_SERVICE_KEY` - Supabase service role key (full DB access)
- `SUPABASE_JWT_SECRET` - JWT verification secret
- `SERVICE_ACCOUNT_SECRET` - API authentication secret

### Worker Configuration

- **Queues**: `matches` (primary queue for match-scraper)
- **Concurrency**: 4 tasks per worker
- **Log Level**: INFO
- **Replicas**: 2 workers (default)

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
