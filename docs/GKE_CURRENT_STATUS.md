# GKE Deployment - Current Status

**Branch**: `feature/gcp-deployment`
**Last Updated**: October 2, 2025
**Status**: ✅ Login Working, ⚠️ Data Loading Issues

## Quick Access

- **Frontend**: http://34.133.125.204:8080
- **Backend API**: http://34.135.217.253:8000
- **Namespace**: `missing-table-dev`
- **Region**: `us-central1`

## What's Working ✅

1. **Infrastructure**: GKE Autopilot cluster fully provisioned via Terraform
2. **Docker Images**: Building and pushing to Artifact Registry successfully
3. **Kubernetes**: All pods running (backend, frontend, redis)
4. **Authentication**: Login functionality working correctly
5. **Networking**: LoadBalancers provisioned with external IPs
6. **CORS**: Backend accepting requests from frontend origin

## Known Issues ⚠️

1. **Data Loading**: Some data loading issues reported after login
   - Login works, but subsequent data fetching may have problems
   - Need to debug on mini in the morning

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

## Next Steps for Tomorrow Morning 🌅

### Quick Start on Mini

```bash
# 1. Pull latest changes
cd /path/to/missing-table
git fetch origin
git checkout feature/gcp-deployment
git pull

# 2. Get cluster credentials
gcloud container clusters get-credentials gke-dev-cluster \
  --region=us-central1 \
  --project=missing-table

# 3. Check pod status
kubectl get pods -n missing-table-dev
kubectl get services -n missing-table-dev

# 4. Test the application
open http://34.133.125.204:8080
```

### Debugging Data Loading Issues

```bash
# Watch backend logs for errors
kubectl logs -n missing-table-dev deployment/missing-table-backend -f

# Watch frontend logs
kubectl logs -n missing-table-dev deployment/missing-table-frontend -f

# Check browser console
# Open http://34.133.125.204:8080
# Press F12 -> Console tab
# Login and check for JavaScript errors

# Test backend API directly
curl http://34.135.217.253:8000/health
curl http://34.135.217.253:8000/api/games  # or other endpoints
```

### Common Issues to Check

1. **Supabase Connection**:
   - Backend logs should show database connection
   - Check if `DATABASE_URL` is correct in values-dev.yaml

2. **Authentication Token**:
   - Login might work but token might not be passed in subsequent requests
   - Check browser Network tab -> Headers -> Authorization

3. **API Endpoints**:
   - Some endpoints might still have hardcoded URLs
   - Search codebase for remaining `localhost:8000`

4. **Environment Variables**:
   - Frontend might be missing some env vars
   - Check `frontend/.env.production` has all required vars

## Useful Commands

### View Logs
```bash
# Backend logs (last 100 lines)
kubectl logs -n missing-table-dev deployment/missing-table-backend --tail=100

# Frontend logs (follow in real-time)
kubectl logs -n missing-table-dev deployment/missing-table-frontend -f

# All pods
kubectl logs -n missing-table-dev --all-containers=true --selector app=missing-table
```

### Rebuild & Deploy
```bash
# Rebuild images
./scripts/build-and-push.sh --tag latest

# Restart deployments
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev

# Watch rollout status
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
```

### Debug Container
```bash
# Exec into frontend pod
kubectl exec -it -n missing-table-dev deployment/missing-table-frontend -- /bin/sh

# Check environment variables
kubectl exec -n missing-table-dev deployment/missing-table-frontend -- env | grep VUE

# Test backend connectivity from frontend pod
kubectl exec -n missing-table-dev deployment/missing-table-frontend -- wget -O- http://missing-table-backend:8000/health
```

### Search for Hardcoded URLs
```bash
# Search for any remaining localhost URLs in source
cd frontend/src
grep -r "localhost:8000" .
grep -r "http://localhost" .

# Check what's actually in the built frontend
kubectl exec -n missing-table-dev deployment/missing-table-frontend -- \
  grep -r "localhost" /app/dist/js/ 2>/dev/null | head -5
```

## Cost Tracking

Current monthly estimate: **~$55-60**
- GKE Autopilot: ~$22/month (3 small pods)
- LoadBalancers: 2 × $18/month = $36/month
- Supabase: Free tier (cloud dev database)

## Documentation

Full deployment guide: [`docs/GKE_DEPLOYMENT.md`](./GKE_DEPLOYMENT.md)

Covers:
- Complete infrastructure setup
- All troubleshooting steps
- Production deployment considerations
- Cost optimization strategies

## Notes

- Cluster has `deletion_protection = false` for easy teardown during dev
- Using `:latest` and `:prod` tags for images
- All environment secrets in Helm values (not checked into git)
- Frontend production build bakes in API URLs at build time
- CSP policy allows GKE backend URL for API calls

## When You're Done for the Day

```bash
# Optional: Scale down to save costs
kubectl scale deployment --all --replicas=0 -n missing-table-dev

# To bring back up
kubectl scale deployment --all --replicas=1 -n missing-table-dev
```

---

**Remember**: The data loading issues are the last remaining blocker. Everything else is working! 🎉
