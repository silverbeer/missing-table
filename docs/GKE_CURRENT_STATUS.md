# GKE Deployment - Current Status

**Branch**: `feature/rabbitmq-celery-integration`
**Last Updated**: October 13, 2025
**Status**: ✅ Fully Operational with Complete RabbitMQ/Celery Integration

## Quick Access

- **Frontend**: https://dev.missingtable.com
- **Backend API**: https://dev.missingtable.com/api
- **Namespace**: `missing-table-dev` (all services consolidated)
- **Region**: `us-central1`

## Current Deployment ✅

### Infrastructure
1. **GKE Autopilot**: Cluster fully provisioned
2. **HTTPS**: Google-managed SSL certificates (auto-renewing)
3. **Domain**: Custom domain with Cloud DNS
4. **Artifact Registry**: Docker images at `us-central1-docker.pkg.dev/missing-table/missing-table`

### Running Services (missing-table-dev namespace)

**Application Services:**
- **Backend**: 1 replica running (image: `backend:dev`)
- **Frontend**: 1 replica running (image: `frontend:dev`)
- **Celery Workers**: 2 replicas running (image: `backend:dev`)

**Messaging Infrastructure:**
- **RabbitMQ**: 1 StatefulSet with 2Gi persistent storage (message broker)
- **Redis**: 1 StatefulSet with 1Gi persistent storage (result backend)

**Match Scraper:**
- **CronJob**: Runs every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
  - Image: `match-scraper:latest`
  - Features: RabbitMQ integration, headless Playwright scraping
  - Automatically submits scraped matches to queue

### What's Working ✅

1. ✅ **Infrastructure**: GKE Autopilot cluster fully provisioned via Terraform
2. ✅ **Authentication**: Backend-centered auth flow (resolves k8s networking issues)
3. ✅ **HTTPS & Domain**: SSL certificates active, custom domain configured
4. ✅ **Async Match Submission**: RabbitMQ + Celery + Redis architecture deployed
5. ✅ **Entity Resolution**: Backend automatically resolves team names to IDs
6. ✅ **Match-Scraper Integration**: Service account authentication working
7. ✅ **Horizontal Scaling**: Celery workers scaled to 2+ replicas
8. ✅ **Monitoring**: Full observability with kubectl logs and RabbitMQ UI

## Recent Enhancements

### Async Task Processing Architecture (Deployed)
- **Match Submission**: POST `/api/matches/submit` queues tasks to RabbitMQ
- **Task Status**: GET `/api/matches/task/{task_id}` polls for completion
- **Background Processing**: Celery workers process matches asynchronously
- **Entity Resolution**: Workers resolve team names, age groups, divisions automatically
- **Deduplication**: Uses `external_match_id` to prevent duplicates
- **Resilience**: Automatic retries on transient failures

### Deployment Details
```
Image: us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev
Platform: linux/amd64 (GKE)
Build Tool: ./build-and-push.sh (handles platform targeting)
```

## Known Issues ⚠️

None currently. All systems operational.

## What Was Fixed in This Session

### 1. Frontend API URLs (Critical)
- **Problem**: 8 hardcoded `http://localhost:8000` URLs in `src/stores/auth.js`
- **Solution**: Added `API_URL` constant using `process.env.VUE_APP_API_URL`
- **Files**: `frontend/src/stores/auth.js`

### 2. Content Security Policy
- **Problem**: CSP hardcoded `localhost:8000` in `connect-src` directive
- **Solution**: Made CSP use environment variable
- **Files**: `frontend/src/plugins/security.js`

### 3. Environment Variables in Images
- **Problem**: `.env.local` files baked into Docker images
- **Solution**: Added `.env*` exclusions to `.dockerignore`
- **Files**: `backend/.dockerignore`

### 4. CORS Configuration
- **Problem**: Backend didn't allow frontend LoadBalancer origin
- **Solution**: Added `CORS_ORIGINS` env var support
- **Files**: `backend/app.py`, `helm/missing-table/values-dev.yaml`

### 5. Production Build Configuration
- **Problem**: Frontend built with wrong API URL
- **Solution**: Created `.env.production` with GKE backend URL
- **Files**: `frontend/.env.production` (not committed - has production URLs)

## Files Changed (Committed)

```
22 files changed, 1457 insertions(+), 82 deletions(-)

New Files:
- docs/GKE_DEPLOYMENT.md (comprehensive deployment guide)
- scripts/build-and-push.sh (build automation)
- terraform/gke/ (complete Terraform infrastructure)
  - modules/network/ (VPC and subnets)
  - modules/cluster/ (GKE Autopilot)
  - environments/dev/ (dev configuration)
  - environments/prod/ (placeholder)

Modified Files:
- .gitignore (Terraform state, .env files)
- backend/.dockerignore (exclude .env files)
- backend/app.py (CORS_ORIGINS support)
- frontend/Dockerfile (port 8080)
- frontend/src/plugins/security.js (CSP uses env var)
- frontend/src/stores/auth.js (API_URL constant)
- helm/missing-table/values.yaml (resource increases)
- helm/missing-table/values-dev.yaml (GKE configuration)
```

## Quick Start

### Access the Application

```bash
# 1. Get cluster credentials (if needed)
gcloud container clusters get-credentials gke-dev-cluster \
  --region=us-central1 \
  --project=missing-table

# 2. Check pod status (all services in one namespace)
kubectl get pods -n missing-table-dev

# 3. Access the application
open https://dev.missingtable.com
```

### Monitor Async Task Processing

```bash
# Check Celery workers
kubectl get pods -n missing-table-dev | grep celery-worker

# View worker logs (real-time)
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker -f

# View backend logs
kubectl logs -n missing-table-dev deployment/missing-table-backend -f

# Access RabbitMQ Management UI
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672
# Open http://localhost:15672 (admin/admin123)

# Check Redis
kubectl port-forward -n missing-table-dev svc/messaging-redis 6379:6379

# Check Match-Scraper CronJob
kubectl get cronjob match-scraper -n missing-table-dev
kubectl get jobs -n missing-table-dev -l app=match-scraper
```

### Test Async API

```bash
# Health check (no auth)
curl https://dev.missingtable.com/health

# Submit match (requires service account token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://dev.missingtable.com/api/matches/submit \
     -d '{
       "home_team": "IFA",
       "away_team": "NEFC",
       "match_date": "2025-10-15T14:00:00Z",
       "season": "2025-26",
       "age_group": "U14",
       "division": "Northeast",
       "match_status": "scheduled",
       "match_type": "League",
       "external_match_id": "test-123"
     }'

# Check task status (use task_id from above)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://dev.missingtable.com/api/matches/task/TASK_ID
```

### Common Troubleshooting

1. **Celery Workers Not Processing**:
   - Check workers are running: `kubectl get pods -n missing-table-dev | grep celery`
   - View worker logs: `kubectl logs -n missing-table-dev deployment/missing-table-celery-worker`
   - Check RabbitMQ queue depth in management UI

2. **Task Stuck in PENDING**:
   - Verify RabbitMQ is accessible: `kubectl get svc -n missing-table-dev messaging-rabbitmq`
   - Check Redis connectivity: `kubectl get svc -n missing-table-dev messaging-redis`
   - View worker logs for connection errors

3. **Authentication Issues**:
   - Generate new service account token: `cd backend && uv run python create_service_account_token.py`
   - Verify token format: `Authorization: Bearer TOKEN`

4. **Database Connection**:
   - Backend logs should show Supabase connection
   - Check `helm/missing-table/values-dev.yaml` has correct DATABASE_URL

## Useful Commands

### View Logs
```bash
# Backend logs (last 100 lines)
kubectl logs -n missing-table-dev deployment/missing-table-backend --tail=100

# Celery worker logs (real-time)
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker -f

# Frontend logs (follow in real-time)
kubectl logs -n missing-table-dev deployment/missing-table-frontend -f

# All pods in namespace
kubectl logs -n missing-table-dev --all-containers=true --selector app=missing-table

# Messaging infrastructure
kubectl logs -n missing-table-dev statefulset/messaging-rabbitmq
kubectl logs -n missing-table-dev statefulset/messaging-redis

# Match-Scraper logs
kubectl logs -n missing-table-dev -l app=match-scraper --tail=100
```

### Rebuild & Deploy
```bash
# IMPORTANT: Always use build-and-push.sh for GKE images (handles platform correctly)

# Rebuild backend image (includes celery_app.py)
./build-and-push.sh backend dev

# Rebuild frontend image
./build-and-push.sh frontend dev

# Rebuild all services (including match-scraper)
./build-and-push.sh all dev

# Restart deployments to pick up new images
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-celery-worker -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev

# For match-scraper: CronJob will use new image on next run
# Or manually trigger a test job:
kubectl create job --from=cronjob/match-scraper test-$(date +%s) -n missing-table-dev

# Watch rollout status
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-celery-worker -n missing-table-dev
```

### Debug Container
```bash
# Exec into backend pod
kubectl exec -it -n missing-table-dev deployment/missing-table-backend -- /bin/sh

# Exec into celery worker pod
kubectl exec -it -n missing-table-dev deployment/missing-table-celery-worker -- /bin/sh

# Check environment variables
kubectl exec -n missing-table-dev deployment/missing-table-backend -- env | grep DATABASE

# Test RabbitMQ connectivity from worker pod
kubectl exec -n missing-table-dev deployment/missing-table-celery-worker -- \
  wget -O- http://messaging-rabbitmq.missing-table-dev.svc.cluster.local:15672
```

### Scale Workers
```bash
# Scale Celery workers for higher load
kubectl scale deployment/missing-table-celery-worker -n missing-table-dev --replicas=4

# Scale down during low activity
kubectl scale deployment/missing-table-celery-worker -n missing-table-dev --replicas=2

# Check current replica count
kubectl get deployment/missing-table-celery-worker -n missing-table-dev
```

## Cost Tracking

Current monthly estimate: **~$60-70**
- **GKE Autopilot**: ~$30/month (7 pods: backend, frontend, 2 celery workers, rabbitmq, redis, + periodic match-scraper jobs)
- **Ingress & SSL**: ~$10/month (managed certificates, load balancer)
- **Persistent Storage**: ~$5/month (RabbitMQ 2Gi + Redis 1Gi)
- **Supabase**: Free tier (cloud dev database)
- **Cloud DNS**: ~$0.50/month

**Cost Optimization Tips**:
- Scale down Celery workers during off-hours: `kubectl scale deployment/missing-table-celery-worker --replicas=1`
- Match-scraper runs only 4 times/day (minimal cost)
- Monitor RabbitMQ queue depth - scale workers based on demand
- StatefulSets use persistent volumes (data survives pod restarts)

## Documentation

### Primary Guides
- **[Architecture Overview](./03-architecture/README.md)** - System design and async architecture
- **[Backend Structure](./03-architecture/backend-structure.md)** - Celery, DAO patterns, async processing
- **[Match-Scraper Integration](./08-integrations/match-scraper.md)** - Async API usage guide
- **[GKE Deployment](./GKE_DEPLOYMENT.md)** - Infrastructure setup

### Related Documentation
- **[HTTPS & Domain Setup](./GKE_HTTPS_DOMAIN_SETUP.md)** - SSL certificates, custom domain
- **[Secret Management](./SECRET_MANAGEMENT.md)** - Secrets handling in GKE

## Architecture Summary

```
External Request
     ↓
Google Cloud Load Balancer (HTTPS)
     ↓
GKE Ingress → Backend Pod → Supabase (Cloud)
                  ↓
              RabbitMQ (Queue)
                  ↓
           Celery Workers (2+) → Redis (Results)
```

**Key Features**:
- ✅ Backend-centered authentication (resolves k8s networking)
- ✅ Async match submission via RabbitMQ/Celery
- ✅ Automatic entity resolution (team names → IDs)
- ✅ Horizontally scalable workers
- ✅ HTTPS with auto-renewing certificates
- ✅ Custom domain (dev.missingtable.com)

## Notes

- **Platform**: AMD64 images built with `build-and-push.sh` (required for GKE)
- **Secrets**: Managed via Helm values (gitignored, never committed)
- **Scaling**: Celery workers can scale to 10+ replicas if needed
- **Monitoring**: RabbitMQ UI available via port-forward (port 15672)
- **Deduplication**: Uses `external_match_id` to prevent duplicate matches
- **Retries**: Celery automatically retries failed tasks

## Quick Scale Commands

```bash
# During high load (many match submissions)
kubectl scale deployment/missing-table-celery-worker -n missing-table-dev --replicas=5

# During normal operation
kubectl scale deployment/missing-table-celery-worker -n missing-table-dev --replicas=2

# During maintenance/off-hours (save costs)
kubectl scale deployment/missing-table-celery-worker -n missing-table-dev --replicas=1

# Check current state
kubectl get all -n missing-table-dev
```

---

**Status**: All systems operational. Async architecture deployed and tested. ✅
