# DEPRECATED — Historical Reference

> **GKE was shut down on 2025-12-07.** Missing Table production moved to DOKS (Dec 2025) and then LKE (Feb 2026). See [Production Environment](../07-operations/CLOUD_K8S_PRODUCTION.md) for current deployment docs.
>
> This document is preserved for historical reference only. Do not follow these instructions.

---

# GKE Deployment Guide (Historical)

This guide covered deploying the Missing Table application to Google Kubernetes Engine (GKE) Autopilot.

## Architecture

- **GKE Autopilot**: Pay-per-pod pricing (~$22/month for dev environment)
- **Google Artifact Registry**: Container image storage
- **Terraform**: Infrastructure as Code for cluster provisioning
- **Helm**: Application deployment and configuration management
- **Supabase Cloud**: Cloud-hosted database (dev and prod environments)

## Prerequisites

1. **GCP Account**: With billing enabled
2. **Local Tools**:
   ```bash
   # Install required tools
   brew install google-cloud-sdk terraform helm kubectl

   # Install GKE auth plugin (required for kubectl)
   gcloud components install gke-gcloud-auth-plugin

   # Authenticate with GCP
   gcloud auth login
   gcloud config set project missing-table
   ```

3. **Enable Required APIs**:
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable compute.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   ```

## Infrastructure Setup

### 1. Create Artifact Registry

```bash
gcloud artifacts repositories create missing-table \
  --repository-format=docker \
  --location=us-central1 \
  --description="Missing Table application images"

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 2. Provision GKE Cluster with Terraform

The infrastructure is organized as follows:
```
terraform/gke/
├── modules/
│   ├── network/        # VPC and subnet configuration
│   └── cluster/        # GKE Autopilot cluster
└── environments/
    ├── dev/           # Development environment
    └── prod/          # Production environment (placeholder)
```

**Deploy Dev Environment**:
```bash
cd terraform/gke/environments/dev

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Apply infrastructure
terraform apply
```

**Key Infrastructure Components**:
- VPC network with secondary IP ranges for pods and services
- GKE Autopilot cluster with Workload Identity enabled
- Automatic node provisioning and scaling
- `deletion_protection = false` for easier teardown during development

### 3. Configure kubectl

```bash
# Get cluster credentials
gcloud container clusters get-credentials missing-table-dev \
  --region=us-central1 \
  --project=missing-table

# Verify connection
kubectl cluster-info
```

## Application Deployment

### 1. Build and Push Docker Images

The application uses environment-specific Docker images with proper configuration baked in at build time.

**Important Files**:
- `frontend/.env.production` - Production environment variables (GKE backend URL)
- `backend/.dockerignore` - Excludes `.env` files from images
- `frontend/Dockerfile` - Production build with `npm run build`
- `scripts/build-and-push.sh` - Automated build and push script

**Build Images**:
```bash
# Build and push both backend and frontend
./scripts/build-and-push.sh --tag prod

# Or build individually
./scripts/build-and-push.sh --backend-only --tag prod
./scripts/build-and-push.sh --frontend-only --tag prod
```

**Platform Note**: Always build with `--platform linux/amd64` for GKE compatibility (handled automatically by the script).

### 2. Deploy with Helm

```bash
# Create namespace
kubectl create namespace missing-table-dev

# Deploy application
helm upgrade --install missing-table ./helm/missing-table \
  --namespace missing-table-dev \
  --values ./helm/missing-table/values-dev.yaml

# Check deployment status
kubectl get pods -n missing-table-dev
kubectl get services -n missing-table-dev
```

**Key Configuration** (`helm/missing-table/values-dev.yaml`):
- Backend image: `us-central1-docker.pkg.dev/missing-table/missing-table/backend:latest`
- Frontend image: `us-central1-docker.pkg.dev/missing-table/missing-table/frontend:prod`
- Backend LoadBalancer: External access for API
- Frontend LoadBalancer: External access for web UI
- Redis: Single replica with persistent storage
- Database: Supabase Cloud (configured via environment variables)

### 3. Get External IPs

```bash
kubectl get services -n missing-table-dev

# Example output:
# missing-table-backend    LoadBalancer   10.x.x.x    34.135.217.253   8000:xxxxx/TCP
# missing-table-frontend   LoadBalancer   10.x.x.x    34.133.125.204   8080:xxxxx/TCP
```

Frontend URL: http://34.133.125.204:8080
Backend API: http://34.135.217.253:8000

## Critical Configuration Issues & Solutions

### Issue 1: Environment Variables in Docker Images

**Problem**: Docker images were including `.env.local` files that pointed to localhost.

**Solution**: Added to `backend/.dockerignore`:
```
.env
.env.*
!.env.example
```

Environment variables are now injected via Kubernetes manifests, not baked into images.

### Issue 2: Frontend API URL Configuration

**Problem**: Vue.js environment variables are compiled at build time, not runtime. Frontend was built with `localhost:8000` in the JavaScript bundle.

**Solution**:
1. Created `frontend/.env.production` with GKE backend URL:
   ```
   VUE_APP_API_URL=http://34.135.217.253:8000
   VUE_APP_SUPABASE_URL=https://ppgxasqgqbnauvxozmjw.supabase.co
   VUE_APP_SUPABASE_ANON_KEY=<key>
   VUE_APP_DISABLE_SECURITY=true
   ```

2. Updated `frontend/src/stores/auth.js` to use environment variable:
   ```javascript
   const API_URL = process.env.VUE_APP_API_URL || 'http://localhost:8000';
   ```
   Replaced all 8 hardcoded `http://localhost:8000` URLs with `${API_URL}`.

### Issue 3: Content Security Policy (CSP)

**Problem**: CSP policy had hardcoded `localhost:8000` in `connect-src` directive, blocking API calls.

**Solution**: Updated `frontend/src/plugins/security.js`:
```javascript
getCSPPolicy() {
  const apiUrl = process.env.VUE_APP_API_URL || 'http://localhost:8000';
  const policy = [
    // ...
    `connect-src 'self' ${apiUrl} https://api.github.com ws: wss:`,
    // ...
  ].join('; ');
  return policy;
}
```

### Issue 4: CORS Configuration

**Problem**: Backend CORS policy didn't include frontend LoadBalancer IP.

**Solution**:
1. Added CORS_ORIGINS environment variable support in `backend/app.py`:
   ```python
   def get_cors_origins():
       extra_origins_str = os.getenv('CORS_ORIGINS', '')
       extra_origins = [origin.strip() for origin in extra_origins_str.split(',') if origin.strip()]
       # ... merge with default origins
   ```

2. Set in `helm/missing-table/values-dev.yaml`:
   ```yaml
   backend:
     env:
       extra:
         CORS_ORIGINS: "http://34.133.125.204:8080"
   ```

### Issue 5: Docker Platform Mismatch

**Problem**: Building on Mac (ARM64) created images incompatible with GKE (AMD64).

**Solution**: Added `--platform linux/amd64` to all docker build commands in `scripts/build-and-push.sh`.

## Deployment Workflow

### Standard Deployment

```bash
# 1. Make code changes

# 2. Build and push images
./scripts/build-and-push.sh --tag latest

# 3. Restart deployments to pull new images
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev

# 4. Monitor rollout
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-frontend -n missing-table-dev

# 5. Check logs if needed
kubectl logs -n missing-table-dev deployment/missing-table-backend --tail=50
kubectl logs -n missing-table-dev deployment/missing-table-frontend --tail=50
```

### Configuration Changes

```bash
# 1. Edit values file
vim helm/missing-table/values-dev.yaml

# 2. Apply changes
helm upgrade --install missing-table ./helm/missing-table \
  --namespace missing-table-dev \
  --values ./helm/missing-table/values-dev.yaml

# 3. Verify changes
kubectl get pods -n missing-table-dev -w
```

## Resource Requirements

### GKE Autopilot Minimum Requirements

Frontend:
- CPU: 250m (increased from 100m for Autopilot)
- Memory: 256Mi (increased from 128Mi for Autopilot)

Backend:
- CPU: 250m
- Memory: 512Mi

Redis:
- CPU: 250m
- Memory: 256Mi
- Storage: 1Gi PersistentVolumeClaim

### Cost Estimation

**Dev Environment** (~$22/month):
- GKE Autopilot: Pay per pod resource usage
- LoadBalancers: 2 × $18/month = $36/month
- **Total**: ~$55-60/month

**Optimization Options**:
- Use Ingress controller instead of LoadBalancers (saves $36/month)
- Scale down to zero during non-business hours
- Use preemptible nodes for non-critical workloads

## Monitoring & Debugging

### View Logs

```bash
# All pods in namespace
kubectl logs -n missing-table-dev --selector app=missing-table-backend --tail=100

# Follow logs in real-time
kubectl logs -n missing-table-dev deployment/missing-table-frontend -f

# Previous container logs (if pod crashed)
kubectl logs -n missing-table-dev <pod-name> --previous
```

### Check Pod Status

```bash
kubectl get pods -n missing-table-dev
kubectl describe pod -n missing-table-dev <pod-name>
```

### Exec into Container

```bash
kubectl exec -it -n missing-table-dev deployment/missing-table-frontend -- /bin/sh
```

### Check Service Configuration

```bash
kubectl get services -n missing-table-dev
kubectl describe service missing-table-backend -n missing-table-dev
```

## Troubleshooting

### Pod CrashLoopBackOff

```bash
# Check logs
kubectl logs -n missing-table-dev <pod-name> --previous

# Check events
kubectl describe pod -n missing-table-dev <pod-name>

# Common causes:
# - Environment variables not set correctly
# - Image pull errors (check registry authentication)
# - Application startup failures (check logs)
```

### Image Pull Errors

```bash
# Verify image exists
gcloud artifacts docker images list us-central1-docker.pkg.dev/missing-table/missing-table

# Re-authenticate Docker
gcloud auth configure-docker us-central1-docker.pkg.dev

# Check image pull policy (should be Always for :latest)
```

### LoadBalancer Not Getting External IP

```bash
# Check service status
kubectl describe service missing-table-backend -n missing-table-dev

# Wait up to 5 minutes for GCP to provision
kubectl get services -n missing-table-dev -w

# Check GCP console for Load Balancer creation status
```

### Network/DNS Issues

```bash
# Test internal DNS
kubectl run -it --rm debug --image=busybox --restart=Never -n missing-table-dev -- nslookup missing-table-backend

# Test external connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n missing-table-dev -- curl http://google.com
```

## Cleanup

### Delete Application

```bash
helm uninstall missing-table -n missing-table-dev
kubectl delete namespace missing-table-dev
```

### Destroy Infrastructure

```bash
cd terraform/gke/environments/dev
terraform destroy
```

### Delete Artifact Registry Images

```bash
gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/missing-table/missing-table/backend:latest

gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/missing-table/missing-table/frontend:prod
```

## Next Steps

### Production Deployment

1. Create `terraform/gke/environments/prod/` configuration
2. Create `helm/missing-table/values-prod.yaml` with production settings
3. Set up proper SSL/TLS certificates (Let's Encrypt or GCP Managed Certificates)
4. Configure Ingress with Cloud Armor for DDoS protection
5. Set up monitoring (Cloud Monitoring, Logging)
6. Configure backup and disaster recovery
7. Implement CI/CD pipeline (GitHub Actions, Cloud Build)

### Security Hardening

1. Enable Workload Identity for pod-level IAM
2. Use Secret Manager for sensitive configuration
3. Enable Binary Authorization for image verification
4. Configure Network Policies for pod-to-pod communication
5. Set up VPC Service Controls
6. Enable audit logging

### Cost Optimization

1. Use GKE Ingress instead of LoadBalancers
2. Configure Horizontal Pod Autoscaling (HPA)
3. Set resource limits to prevent overspending
4. Use committed use discounts for predictable workloads
5. Enable GKE Autopilot cluster autoscaling

## References

- [GKE Autopilot Documentation](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Helm Documentation](https://helm.sh/docs/)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
