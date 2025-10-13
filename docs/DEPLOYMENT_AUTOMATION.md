# Deployment Automation Guide

**Last Updated**: 2025-10-13

This document describes all the automation available for deploying the missing-table application and match-scraper integration.

## Overview

The missing-table project has multiple deployment methods:

1. **Manual deployment** - Shell scripts for local/manual deployments
2. **GitHub Actions** - Automated CI/CD pipelines
3. **Helm** - Kubernetes package manager for cloud deployments

## Deployment Scripts

### Missing-Table Services

#### `build-and-push.sh`
**Purpose**: Build and push Docker images for backend/frontend/match-scraper

```bash
# Build backend for dev (AMD64, push to registry)
./build-and-push.sh backend dev

# Build frontend for production (AMD64, push to registry)
./build-and-push.sh frontend prod

# Build match-scraper for dev (AMD64, push to registry)
./build-and-push.sh match-scraper dev

# Build backend for local (current platform, no push)
./build-and-push.sh backend local

# Build all services for dev (backend + frontend + match-scraper)
./build-and-push.sh all dev
```

**Features:**
- Platform-aware builds (ARM64 for Mac, AMD64 for GKE)
- Automatic push to Google Artifact Registry for cloud environments
- Build argument injection (e.g., VUE_APP_API_URL for frontend)
- **NEW:** Builds match-scraper from external repository
- Post-build deployment instructions (different for match-scraper CronJob)

**When to use:**
- Building images before Helm deployment
- Testing local Docker builds
- Manual cloud deployments
- **NEW:** Building match-scraper without switching directories

**Note:** match-scraper is built from `/Users/silverbeer/gitrepos/match-scraper`

---

#### `helm/deploy-helm.sh`
**Purpose**: Deploy missing-table to Kubernetes using Helm

```bash
cd helm && ./deploy-helm.sh
```

**What it does:**
- Installs/upgrades Helm chart
- Creates namespace if needed
- Deploys backend, frontend, and all dependencies
- Configures secrets from values-dev.yaml

**When to use:**
- Deploying to GKE after building images
- Updating configuration (scaling, resources, env vars)
- Rolling back deployments

---

### Match-Scraper Deployment

#### `scripts/deploy-match-scraper.sh`
**Purpose**: Complete deployment of match-scraper CronJob with RabbitMQ integration

```bash
# Full deployment (build + push + deploy)
./scripts/deploy-match-scraper.sh

# Deploy and create test job
./scripts/deploy-match-scraper.sh --test

# Skip build, just deploy (use existing image)
./scripts/deploy-match-scraper.sh --skip-build
```

**What it does:**
1. Checks prerequisites (docker, kubectl, helm)
2. Builds match-scraper Docker image (if not skipped)
3. Pushes image to Google Artifact Registry
4. Updates Helm secrets with RabbitMQ configuration
5. Deploys CronJob to Kubernetes
6. Optionally creates and monitors a test job

**When to use:**
- First-time deployment of match-scraper
- Updating match-scraper code
- Testing RabbitMQ integration
- Manual deployments without CI/CD

**Prerequisites:**
- Docker installed and authenticated with gcloud
- kubectl configured for GKE cluster
- helm installed
- values-dev.yaml with RabbitMQ configuration

---

## GitHub Actions Workflows

### Missing-Table Repository

#### `.github/workflows/security-scan.yml`
**Triggers:**
- Push to any branch
- Pull requests

**Purpose:** Security scanning with Trivy

**What it does:**
- Scans for vulnerabilities in dependencies
- Checks for exposed secrets
- Reports findings in PR comments

---

### Match-Scraper Repository

#### `.github/workflows/gke-deploy.yml`
**Triggers:**
- Push to `main` branch (paths: `src/**`, `k8s/**`, `Dockerfile.gke`, `pyproject.toml`, `uv.lock`)
- Manual workflow dispatch

**Purpose:** Automated deployment to GKE

**What it does:**
1. **Test job**: Runs linting and unit tests
2. **Build job**: Builds Docker image and pushes to GCR
3. **Deploy job**: Deploys CronJob to GKE

**Manual dispatch options:**
- `skip_tests`: Skip test run before deployment
- Uses GCR (not Artifact Registry) - **Note:** Should be updated to use Artifact Registry

**Secrets required:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`

---

#### `.github/workflows/test-and-publish.yml`
**Triggers:**
- Push to any branch
- Pull requests

**Purpose:** Run tests and publish coverage reports

**What it does:**
1. Runs linting (ruff)
2. Runs type checking (mypy)
3. Runs unit tests with coverage
4. Generates HTML/JSON coverage reports
5. Publishes test results to GitHub Pages
6. Creates dynamic badges for README

**Features:**
- Keeps last 5 test runs per branch
- Diff coverage for PRs
- Automated badge generation

---

### Missing-Table Repository (New!)

#### `.github/workflows/deploy-match-scraper.yml`
**Triggers:**
- Push to `main` branch (paths: `k8s/match-scraper-cronjob.yaml`, `helm/missing-table/templates/secrets.yaml`)
- Manual workflow dispatch

**Purpose:** Deploy match-scraper from missing-table repo

**What it does:**
1. **Build job**: Checks out match-scraper repo, builds Docker image, pushes to Artifact Registry
2. **Deploy job**: Updates Helm secrets, deploys CronJob, optionally creates test job

**Manual dispatch options:**
- `run_test_job`: Create and run a test job after deployment (default: true)
- `skip_build`: Skip Docker build, use existing image (default: false)

**Secrets required:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_JWT_SECRET`
- `SERVICE_ACCOUNT_SECRET`
- `RABBITMQ_USERNAME`
- `RABBITMQ_PASSWORD`

**Why in missing-table repo?**
- Coordinates with Helm deployment (secrets management)
- Single source of truth for infrastructure
- Easier to manage secrets (all in one place)

---

## Deployment Workflows

### First-Time Deployment

#### Missing-Table Backend/Frontend
```bash
# 1. Build images
./build-and-push.sh all dev

# 2. Deploy with Helm
cd helm && ./deploy-helm.sh

# 3. Verify deployment
kubectl get pods -n missing-table-dev
kubectl logs -f deployment/missing-table-backend -n missing-table-dev
```

#### Match-Scraper
```bash
# Complete deployment with test
./scripts/deploy-match-scraper.sh --test

# Monitor test job (follow logs)
# Check RabbitMQ queue
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672
# Open http://localhost:15672 (admin/admin123)

# Check Celery workers
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker --tail=50 -f
```

---

### Updating Code

#### Backend/Frontend Changes
**Option 1: GitHub Actions (Recommended)**
```bash
# Push to main branch
git push origin main

# Workflow automatically:
# 1. Builds new images
# 2. Runs tests
# 3. Deploys to GKE (if configured)
```

**Option 2: Manual Deployment**
```bash
# 1. Build and push new image
./build-and-push.sh backend dev  # or frontend

# 2. Restart deployment (pulls new image)
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
```

#### Match-Scraper Changes
**Option 1: GitHub Actions (Recommended)**
```bash
# In match-scraper repo
git push origin main

# gke-deploy.yml workflow automatically:
# 1. Builds new image
# 2. Pushes to GCR
# 3. Deploys CronJob to GKE
```

**Option 2: Manual Deployment from missing-table**
```bash
# From missing-table repo
./scripts/deploy-match-scraper.sh --test
```

**Option 3: Manual Deployment from match-scraper**
```bash
# In match-scraper repo
# 1. Build image
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest \
  .

# 2. Push to registry
docker push us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest

# 3. From missing-table repo, deploy CronJob
kubectl apply -f k8s/match-scraper-cronjob.yaml

# 4. Force pod restart
kubectl delete pods -n missing-table-dev -l app=match-scraper
```

---

### Configuration-Only Changes

#### Helm Values Updates
```bash
# Edit values
vim helm/missing-table/values-dev.yaml

# Re-deploy (won't rebuild images)
cd helm && ./deploy-helm.sh
```

#### CronJob Schedule/Config Updates
```bash
# Edit CronJob manifest
vim k8s/match-scraper-cronjob.yaml

# Apply changes
kubectl apply -f k8s/match-scraper-cronjob.yaml
```

---

## CI/CD Best Practices

### When to Use Scripts vs GitHub Actions

**Use Scripts When:**
- Testing deployments locally
- Debugging deployment issues
- First-time setup
- Working without internet/CI access
- Need fine-grained control

**Use GitHub Actions When:**
- Automated deployments on code changes
- Team collaboration (consistent deployments)
- Production deployments
- Need audit trail
- Want automated testing before deploy

### Deployment Safety

**Pre-deployment checks:**
```bash
# 1. Check kubectl context
kubectl config current-context
# Should be: gke_missing-table_us-central1_missing-table-dev

# 2. Check current deployments
kubectl get deployments -n missing-table-dev

# 3. Check RabbitMQ is healthy
kubectl get pods -n missing-table-dev | grep rabbitmq

# 4. Backup database (if schema changes)
./scripts/db_tools.sh backup
```

**Post-deployment verification:**
```bash
# 1. Check pod status
kubectl get pods -n missing-table-dev

# 2. Check logs for errors
kubectl logs -f deployment/missing-table-backend -n missing-table-dev --tail=50

# 3. Test health endpoint
curl https://dev.missingtable.com/api/health

# 4. For match-scraper: Check RabbitMQ queue
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672
# Open http://localhost:15672
```

---

## Rollback Procedures

### Backend/Frontend Rollback
```bash
# List recent revisions
kubectl rollout history deployment/missing-table-backend -n missing-table-dev

# Rollback to previous version
kubectl rollout undo deployment/missing-table-backend -n missing-table-dev

# Rollback to specific revision
kubectl rollout undo deployment/missing-table-backend -n missing-table-dev --to-revision=3

# Verify rollback
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
```

### Match-Scraper Rollback
```bash
# Suspend CronJob (stop scheduled runs)
kubectl patch cronjob match-scraper -n missing-table-dev -p '{"spec":{"suspend":true}}'

# Delete problematic jobs
kubectl delete jobs -n missing-table-dev -l app=match-scraper

# If needed, deploy previous CronJob manifest
git checkout <previous-commit> k8s/match-scraper-cronjob.yaml
kubectl apply -f k8s/match-scraper-cronjob.yaml

# Resume CronJob
kubectl patch cronjob match-scraper -n missing-table-dev -p '{"spec":{"suspend":false}}'
```

---

## Secrets Management

**Never commit secrets to git!**

### Local Development
```bash
# Copy example file
cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml

# Edit with real secrets
vim helm/missing-table/values-dev.yaml
```

### GitHub Actions
Secrets are stored in GitHub repository settings:
- Settings → Secrets and variables → Actions → Repository secrets

**Required secrets:**
- GCP authentication (`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`)
- Database credentials (`DATABASE_URL`)
- Supabase credentials (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`)
- Application secrets (`SERVICE_ACCOUNT_SECRET`)
- RabbitMQ credentials (`RABBITMQ_USERNAME`, `RABBITMQ_PASSWORD`)

---

## Troubleshooting

### Build Failures

**Docker build fails with "no match for platform"**
```bash
# Ensure you're building for correct platform
./build-and-push.sh backend dev  # This handles platform automatically
```

**"permission denied" errors**
```bash
# Make scripts executable
chmod +x ./build-and-push.sh
chmod +x ./scripts/deploy-match-scraper.sh
chmod +x ./helm/deploy-helm.sh
```

### Deployment Failures

**"secret not found" errors**
```bash
# Verify secret exists
kubectl get secret missing-table-secrets -n missing-table-dev

# Re-deploy secrets
cd helm && ./deploy-helm.sh
```

**Pod stuck in "ImagePullBackOff"**
```bash
# Check image exists in registry
gcloud artifacts docker images list us-central1-docker.pkg.dev/missing-table/missing-table

# Verify image tag in deployment
kubectl describe pod <pod-name> -n missing-table-dev
```

**CronJob not creating jobs**
```bash
# Check CronJob schedule
kubectl get cronjob match-scraper -n missing-table-dev

# Check CronJob is not suspended
kubectl get cronjob match-scraper -n missing-table-dev -o jsonpath='{.spec.suspend}'
# Should output: false

# Check CronJob events
kubectl describe cronjob match-scraper -n missing-table-dev
```

---

## Quick Reference

### Essential Commands
```bash
# Build and deploy everything
./build-and-push.sh all dev
cd helm && ./deploy-helm.sh
./scripts/deploy-match-scraper.sh --test

# Check deployment status
kubectl get all -n missing-table-dev

# View logs
kubectl logs -f deployment/missing-table-backend -n missing-table-dev
kubectl logs -f deployment/missing-table-celery-worker -n missing-table-dev

# Access RabbitMQ UI
kubectl port-forward -n missing-table-dev svc/messaging-rabbitmq 15672:15672

# Manual test of match-scraper
kubectl create job --from=cronjob/match-scraper test-$(date +%s) -n missing-table-dev
```

### File Locations
- Shell scripts: `/scripts/`, `/helm/`, root directory
- GitHub Actions: `/.github/workflows/`
- Helm charts: `/helm/missing-table/`
- Kubernetes manifests: `/k8s/`
- Documentation: `/docs/`

---

## Related Documentation

- [Match-Scraper Deployment Guide](./MATCH_SCRAPER_DEPLOYMENT.md) - Detailed operational guide
- [RabbitMQ Integration Summary](./RABBITMQ_INTEGRATION_SUMMARY.md) - Architecture and implementation
- [GKE HTTPS & Domain Setup](./GKE_HTTPS_DOMAIN_SETUP.md) - SSL and custom domain configuration
- [Secret Management](./SECRET_MANAGEMENT.md) - How secrets are handled

---

**Last Updated**: 2025-10-13
