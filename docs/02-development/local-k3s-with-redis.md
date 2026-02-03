# Local K3s Development with Redis

This guide explains how to set up a complete local development environment using Rancher Desktop (k3s) with Redis for caching.

## Overview

The local development stack consists of:
- **Supabase** (PostgreSQL) - runs via Docker (supabase CLI)
- **Redis** - runs in local k3s cluster for caching
- **Backend** - runs locally with `uv run python app.py`
- **Frontend** - runs locally with `npm run serve`

## Prerequisites

### 1. Install Required Tools

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Core tools
brew install git node python@3.13 helm

# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Supabase CLI
npm install -g supabase

# Rancher Desktop - download from https://rancherdesktop.io/
# After install, open Rancher Desktop and enable Kubernetes
```

### 2. Verify Rancher Desktop is Running

```bash
# Should show rancher-desktop context
kubectl config get-contexts

# Switch to rancher-desktop context
kubectl config use-context rancher-desktop

# Verify cluster is ready
kubectl get nodes
```

## Quick Start

If you just want to get everything running quickly:

```bash
# 1. Deploy Redis to k3s
./scripts/deploy-local-redis.sh

# 2. Start Supabase
cd supabase-local && npx supabase start && cd ..

# 3. Setup database (requires recent backup)
./scripts/setup-local-db.sh --restore

# 4. Start services with auto-reload
./missing-table.sh dev
```

## Step-by-Step Setup

### Step 1: Deploy Redis to Local K3s

Create the namespace and deploy Redis:

```bash
# Create namespace
kubectl create namespace missing-table --dry-run=client -o yaml | kubectl apply -f -

# Deploy Redis using helm chart
helm upgrade --install missing-table ./helm/missing-table \
  --namespace missing-table \
  --set redis.enabled=true \
  --set backend.replicaCount=0 \
  --set frontend.replicaCount=0 \
  --set celeryWorker.enabled=false
```

Verify Redis is running:

```bash
# Check pod status
kubectl get pods -n missing-table

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# missing-table-redis-xxxxxxxxx-xxxxx       1/1     Running   0          1m

# Test Redis connection
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli PING
# Expected: PONG
```

### Step 2: Start Local Supabase

```bash
cd supabase-local
npx supabase start
cd ..
```

This starts:
- **PostgreSQL**: localhost:54332
- **API**: localhost:54321
- **Studio**: localhost:54323

### Step 3: Setup Database

Create a backup first (if you have existing data):
```bash
./scripts/db_tools.sh backup
```

Then reset and seed the database:
```bash
# Without match data (reference data + test users only)
./scripts/setup-local-db.sh

# With match data from backup
./scripts/setup-local-db.sh --restore
```

This script:
1. Resets the database (applies schema + seed)
2. Flushes Redis cache (if available)
3. Seeds test users (tom, tom_ifa, tom_ifa_fan, tom_club)

### Step 4: Configure Environment

The backend needs to know where Redis is. Create/update `backend/.env.local`:

```bash
# Database (local Supabase)
DATABASE_URL=postgresql://postgres:postgres@localhost:54332/postgres
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=<your-local-service-key>  # Get from: npx supabase status

# Redis caching (via port-forward)
CACHE_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# Development settings
APP_ENV=local
LOG_LEVEL=debug
```

### Step 5: Start Port-Forward for Redis

The `missing-table.sh` script handles this automatically, but you can also do it manually:

```bash
# Manual port-forward (runs in foreground)
kubectl port-forward -n missing-table svc/missing-table-redis 6379:6379

# Or use the service script which handles it in background
./missing-table.sh start
```

### Step 6: Start Development Servers

```bash
# Option A: Use the service script (recommended)
./missing-table.sh dev  # Starts with auto-reload

# Option B: Start manually in separate terminals
# Terminal 1 - Backend
cd backend && APP_ENV=local uv run python app.py

# Terminal 2 - Frontend
cd frontend && npm run serve
```

## Verification

### Check All Services

```bash
# Check service status
./missing-table.sh status

# Expected output:
# Backend:  running (PID: xxxxx)
# Frontend: running (PID: xxxxx)
# Redis:    port-forward active (PID: xxxxx)
```

### Verify Redis Caching

```bash
# Check Redis has data (after making some API calls)
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli DBSIZE
# Should show number of cached keys

# View cache keys
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli KEYS "mt:dao:*"
```

### Test Endpoints

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Supabase Studio**: http://localhost:54323

## Common Commands

### Service Management

```bash
./missing-table.sh start      # Start all services
./missing-table.sh stop       # Stop all services
./missing-table.sh restart    # Restart all services
./missing-table.sh status     # Check service status
./missing-table.sh dev        # Start with auto-reload (recommended)
./missing-table.sh logs       # View service logs
./missing-table.sh tail       # Follow logs in real-time
```

### Redis Commands

```bash
# Flush all cache (useful after DB changes)
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli FLUSHALL

# Check Redis memory usage
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli INFO memory

# Monitor Redis commands in real-time
kubectl exec -n missing-table svc/missing-table-redis -- redis-cli MONITOR
```

### Database Commands

```bash
# Reset database
./scripts/setup-local-db.sh

# Backup database
./scripts/db_tools.sh backup

# Restore from backup
./scripts/db_tools.sh restore

# List backups
./scripts/db_tools.sh list
```

## Troubleshooting

### Redis Pod Not Starting

```bash
# Check pod events
kubectl describe pod -n missing-table -l app.kubernetes.io/component=redis

# Check storage (PVC might be stuck)
kubectl get pvc -n missing-table
```

If PVC is stuck in Pending:
```bash
# Delete and recreate
kubectl delete pvc -n missing-table --all
helm upgrade --install missing-table ./helm/missing-table \
  --namespace missing-table \
  --set redis.enabled=true \
  --set backend.replicaCount=0 \
  --set frontend.replicaCount=0
```

### Port-Forward Dies

The port-forward can timeout or die. Restart it:

```bash
# Kill existing port-forward
pkill -f "port-forward.*missing-table-redis"

# Restart services (will recreate port-forward)
./missing-table.sh restart
```

### Rancher Desktop Not Responding

```bash
# Restart Rancher Desktop from menu bar
# Or via command line:
rdctl shutdown
rdctl start
```

### Cache Not Working

1. Verify `CACHE_ENABLED=true` in backend/.env.local
2. Check Redis is accessible:
   ```bash
   redis-cli -h localhost -p 6379 PING
   ```
3. Check backend logs for cache messages:
   ```bash
   ./missing-table.sh logs | grep -i cache
   ```

### Database Connection Issues

```bash
# Verify Supabase is running
cd supabase-local && npx supabase status

# Check PostgreSQL connectivity
PGPASSWORD=postgres psql -h localhost -p 54332 -U postgres -c "SELECT 1"
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Local Development                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Frontend   │────▶│   Backend    │────▶│  Supabase    │    │
│  │  :8080       │     │   :8000      │     │  (Docker)    │    │
│  └──────────────┘     └──────┬───────┘     │  :54321 API  │    │
│                              │             │  :54332 DB   │    │
│                              │             │  :54323 UI   │    │
│                              ▼             └──────────────┘    │
│                       ┌──────────────┐                          │
│                       │    Redis     │                          │
│                       │   (K3s)      │◀── port-forward :6379   │
│                       │  caching     │                          │
│                       └──────────────┘                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 Rancher Desktop (K3s)                     │  │
│  │  namespace: missing-table                                 │  │
│  │  ├── missing-table-redis (Deployment)                    │  │
│  │  ├── missing-table-redis (Service)                       │  │
│  │  └── missing-table-redis-pvc (PersistentVolumeClaim)    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Local Development Setup](../01-getting-started/local-development.md) - Basic setup without k3s
- [Database Operations](./database-operations.md) - Backup/restore procedures
- [Environment Management](./environment-management.md) - Switching between local/prod
- [LOCAL_K3S_SETUP.md](../05-deployment/LOCAL_K3S_SETUP.md) - Messaging infrastructure (RabbitMQ/Celery)

---

**Last Updated**: 2026-02-03
