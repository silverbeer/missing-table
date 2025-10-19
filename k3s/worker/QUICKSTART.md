# Celery Worker Quick Start Guide

## 🎉 Setup Complete!

Your Celery workers are now running in k3s and connected to:
- **RabbitMQ**: Local k3s (message broker)
- **Supabase**: Dev environment (database)

## Current Status

```bash
kubectl get pods -n match-scraper -l app=missing-table-worker
```

**Expected Output:**
```
NAME                                           READY   STATUS    RESTARTS   AGE
missing-table-celery-worker-xxxxx-xxxxx       0/1     Running   0          5m
missing-table-celery-worker-xxxxx-xxxxx       0/1     Running   0          5m
```

⚠️ **Note**: Pods show `0/1 Ready` because readiness probe checks Redis (not deployed yet). This is **OK** - workers are functional and processing messages from RabbitMQ!

## Verify Workers Are Working

### 1. Check Worker Logs
```bash
kubectl logs -n match-scraper -l app=missing-table-worker --tail=50 -f
```

**What to look for:**
- ✅ `Connected to amqp://admin:**@rabbitmq.match-scraper:5672//`
- ✅ `celery@missing-table-celery-worker ready`
- ✅ Tasks registered: `process_match_data`, `validate_match_data`

### 2. Check RabbitMQ Queue
```bash
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues name messages consumers
```

**Expected Output:**
```
matches    0    3    # 3 consumers = 3 workers listening
```

### 3. Check Database Connection
Workers are connected to **dev Supabase**:
```bash
kubectl get configmap -n match-scraper missing-table-worker-config -o jsonpath='{.data.SUPABASE_URL}'
# Output: https://ppgxasqgqbnauvxozmjw.supabase.co
```

## Run match-scraper Locally

Now you can run match-scraper locally and it will send messages to the workers:

```bash
# In your match-scraper repo
cd ~/gitrepos/match-scraper

# Set RabbitMQ URL to connect to local k3s
export RABBITMQ_URL="amqp://admin:admin123@localhost:5672//"

# Port-forward RabbitMQ if needed
kubectl port-forward -n match-scraper rabbitmq-0 5672:5672 &

# Run match-scraper
python main.py scrape --league "MLS Next" --season "2024-2025"
```

**What happens:**
1. match-scraper scrapes matches and publishes to RabbitMQ `matches` queue
2. Workers consume messages from queue
3. Workers process match data and insert into **dev Supabase**
4. You can verify at https://ppgxasqgqbnauvxozmjw.supabase.co

## Switch Between Dev and Prod

### Switch to Production (when ready)
```bash
# 1. Set up production Supabase credentials first
cp k3s/worker/configmap-prod.yaml.template k3s/worker/configmap-prod.yaml
cp k3s/worker/secret-prod.yaml.template k3s/worker/secret-prod.yaml

# 2. Edit files with production credentials
vim k3s/worker/configmap-prod.yaml
vim k3s/worker/secret-prod.yaml

# 3. Switch to prod
./k3s/worker/switch-worker-env.sh prod
```

### Switch Back to Dev
```bash
./k3s/worker/switch-worker-env.sh dev
```

### Check Current Environment
```bash
./k3s/worker/switch-worker-env.sh status
```

## Rebuild Worker Image (after code changes)

When you modify backend code:

```bash
# 1. Rebuild image
docker build -f backend/Dockerfile -t missing-table-worker:latest backend/

# 2. Import to Rancher Desktop
docker save missing-table-worker:latest | nerdctl --namespace k8s.io load

# 3. Restart workers
kubectl rollout restart deployment/missing-table-celery-worker -n match-scraper
```

Or use the helper script (coming soon):
```bash
./k3s/worker/rebuild-and-deploy.sh
```

## Scale Workers

```bash
# Scale up to 4 workers
kubectl scale deployment/missing-table-celery-worker -n match-scraper --replicas=4

# Scale down to 1 worker
kubectl scale deployment/missing-table-celery-worker -n match-scraper --replicas=1
```

## Monitoring

### View Worker Logs in Real-Time
```bash
kubectl logs -n match-scraper -l app=missing-table-worker -f
```

### RabbitMQ Management UI
```bash
kubectl port-forward -n match-scraper rabbitmq-0 15672:15672
# Open http://localhost:15672
# Login: admin / admin123
```

### Check Queue Depth
```bash
watch -n 2 'kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues name messages consumers'
```

## Troubleshooting

### Workers Not Consuming Messages
```bash
# Check worker logs
kubectl logs -n match-scraper -l app=missing-table-worker --tail=100

# Check RabbitMQ connections
kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_connections

# Restart workers
kubectl rollout restart deployment/missing-table-celery-worker -n match-scraper
```

### Database Connection Issues
```bash
# Verify Supabase URL
kubectl get configmap -n match-scraper missing-table-worker-config -o yaml | grep SUPABASE_URL

# Test connection from pod
kubectl exec -n match-scraper -it <pod-name> -- \
  uv run python -c "from dao.enhanced_data_access_fixed import SupabaseConnection; print(SupabaseConnection().client.table('teams').select('count').execute())"
```

### Image Pull Issues
```bash
# Verify image exists in Rancher Desktop
nerdctl --namespace k8s.io images | grep missing-table-worker

# Re-import if needed
docker save missing-table-worker:latest | nerdctl --namespace k8s.io load
```

### Redis Connection Warnings
```
redis.exceptions.ConnectionError: Error -2 connecting to redis.match-scraper:6379
```

**This is expected** - Redis is not deployed yet. Workers can still process messages from RabbitMQ. Redis is only needed for storing task results.

To deploy Redis (optional):
```bash
# Coming in Phase 2 of RabbitMQ/Celery integration
helm install redis bitnami/redis -n match-scraper
```

## What's Next?

1. ✅ Workers deployed and connected to dev Supabase
2. ✅ Ready to process messages from match-scraper
3. ⏭️ Test by running match-scraper locally
4. ⏭️ Set up production environment when ready
5. ⏭️ Deploy Redis for task result storage (optional)

## Files Created

```
k3s/worker/
├── README.md                           # Full documentation
├── QUICKSTART.md                       # This file
├── switch-worker-env.sh                # Environment switcher script
├── deployment.yaml                     # Worker deployment
├── configmap-dev.yaml                  # Dev config (active)
├── secret-dev.yaml                     # Dev secrets (active)
├── configmap-prod.yaml.template        # Prod config template
└── secret-prod.yaml.template           # Prod secrets template
```

## Need Help?

- **Full documentation**: `k3s/worker/README.md`
- **Architecture**: `docs/03-architecture/README.md`
- **RabbitMQ/Celery guide**: `docs/rabbitmq-celery/README.md`
