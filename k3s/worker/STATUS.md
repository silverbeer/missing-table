# Celery Worker Status

**Last Updated**: 2025-10-19

## Current Configuration

- **Environment**: Dev (Supabase)
- **Replicas**: 2
- **Result Backend**: RPC (no Redis required)
- **Message Broker**: RabbitMQ (local k3s)
- **Database**: Dev Supabase

## Component Health

```
✅ Pods Running:              2/2 READY
✅ RabbitMQ Connection:       Connected
✅ Queue Consumers:           2 workers on 'matches' queue
✅ Result Backend:            RPC (lightweight)
✅ Database Connection:       Dev Supabase
```

## Quick Commands

```bash
# Check worker status
kubectl get pods -n match-scraper -l app=missing-table-worker

# View logs
kubectl logs -n match-scraper -l app=missing-table-worker -f

# Check queue
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues name messages consumers

# Check environment
kubectl get configmap -n match-scraper missing-table-worker-config -o yaml

# Switch to prod
./k3s/worker/switch-worker-env.sh prod

# Rebuild after code changes
./k3s/worker/rebuild-and-deploy.sh
```

## Architecture

```
┌──────────────────┐
│  match-scraper   │  (Local or CronJob)
│   (Publisher)    │
└────────┬─────────┘
         │ publishes
         ▼
┌──────────────────┐
│    RabbitMQ      │  (k3s)
│  matches queue   │
└────────┬─────────┘
         │ consumes
         ▼
┌──────────────────┐
│ Celery Workers   │  (k3s, 2 replicas)
│  (Consumers)     │
└────────┬─────────┘
         │ writes
         ▼
┌──────────────────┐
│  Dev Supabase    │  (Cloud)
│   (Database)     │
└──────────────────┘
```

## Testing

### Test with match-scraper CronJob
```bash
# Trigger test job
./scripts/test-k3s.sh trigger

# Monitor
kubectl logs -n match-scraper -l app=missing-table-worker -f
```

### Test with local match-scraper
```bash
# Port-forward RabbitMQ
kubectl port-forward -n match-scraper rabbitmq-0 5672:5672 &

# In match-scraper repo
export RABBITMQ_URL="amqp://admin:admin123@localhost:5672//"
python main.py scrape --league "MLS Next" --season "2024-2025"
```

## Recent Changes

**2025-10-19**: Disabled Redis result backend
- Changed from `redis://redis.match-scraper:6379/0` to `rpc://`
- Removed Redis dependency - not needed for match-scraper use case
- Workers now store results via RPC backend (uses RabbitMQ)
- All tasks execute successfully without Redis

**2025-10-19**: Initial deployment
- Deployed 2 workers to k3s
- Connected to dev Supabase
- Consuming from `matches` queue

## Troubleshooting

### Workers not processing tasks
1. Check logs: `kubectl logs -n match-scraper -l app=missing-table-worker --tail=100`
2. Check queue: `kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues`
3. Restart: `kubectl rollout restart deployment/missing-table-celery-worker -n match-scraper`

### Database connection errors
1. Check Supabase URL: `kubectl get configmap -n match-scraper missing-table-worker-config -o yaml`
2. Verify credentials: `kubectl get secret -n match-scraper missing-table-worker-secrets -o yaml`
3. Switch environment: `./k3s/worker/switch-worker-env.sh dev`

### Need to switch to prod
```bash
# Set up prod credentials first
cp k3s/worker/configmap-prod.yaml.template k3s/worker/configmap-prod.yaml
cp k3s/worker/secret-prod.yaml.template k3s/worker/secret-prod.yaml

# Edit with real credentials
vim k3s/worker/configmap-prod.yaml
vim k3s/worker/secret-prod.yaml

# Switch
./k3s/worker/switch-worker-env.sh prod
```

## Next Steps

- ⏭️ Test end-to-end with match-scraper
- ⏭️ Set up production Supabase credentials
- ⏭️ Monitor for a few days to ensure stability
- ⏭️ Consider adding Redis if task result tracking is needed
