# Docker Build Guide

## Quick Start

```bash
# Build and deploy backend to dev
./build-and-push.sh backend dev
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev

# Build and deploy frontend to prod
./build-and-push.sh frontend prod
kubectl rollout restart deployment/missing-table-frontend -n missing-table-prod

# Build all services for dev
./build-and-push.sh all dev
```

## Why We Need This Script

### The Platform Problem

**Issue**: Docker images must match the CPU architecture of where they'll run.

- **Mac (Apple Silicon)**: ARM64 architecture
- **GKE (Google Cloud)**: AMD64/x86_64 architecture
- **Incompatible**: ARM64 images cannot run on AMD64 clusters

**Symptom**: When you deploy an ARM64 image to GKE, you get:
```
Error: ImagePullBackOff
failed to pull and unpack image: no match for platform in manifest: not found
```

### The Solution

The `build-and-push.sh` script automatically handles platform-specific builds:

- **Cloud builds**: Always uses `linux/amd64` (GKE requirement)
- **Local builds**: Uses your current platform
- **Smart pushing**: Only pushes cloud builds to registry

## Script Usage

### Syntax

```bash
./build-and-push.sh <service> <environment>
```

**Services:**
- `backend` - Backend API service
- `frontend` - Frontend Vue.js service
- `all` - Build both services

**Environments:**
- `local` - Local development (current platform, no push)
- `dev` - Development environment (AMD64, push to registry)
- `prod` - Production environment (AMD64, push to registry)

### Examples

#### Development Workflow

```bash
# Make changes to backend code
vim backend/app.py

# Build and push to dev
./build-and-push.sh backend dev

# Deploy to GKE dev environment
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-backend -n missing-table-dev

# Watch logs
kubectl logs -f -l app.kubernetes.io/component=backend -n missing-table-dev
```

#### Production Release

```bash
# Build both services for production
./build-and-push.sh all prod

# Deploy to GKE production
kubectl rollout restart deployment/missing-table-backend -n missing-table-prod
kubectl rollout restart deployment/missing-table-frontend -n missing-table-prod

# Verify deployment
kubectl get pods -n missing-table-prod
```

#### Local Development

```bash
# Build for local testing (no push to registry)
./build-and-push.sh backend local

# Use with docker-compose
docker-compose up
```

## What the Script Does

### Cloud Builds (dev/prod)

1. Uses `docker buildx build` with `--platform linux/amd64`
2. Tags image with environment name (e.g., `:dev`, `:prod`)
3. Pushes to Artifact Registry: `us-central1-docker.pkg.dev/missing-table/missing-table`
4. Shows deployment commands

```bash
# Equivalent to:
docker buildx build \
  --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev \
  -f backend/Dockerfile backend/ \
  --push
```

### Local Builds

1. Uses standard `docker build`
2. Builds for current platform (ARM64 or AMD64)
3. Does NOT push to registry
4. Tags with `:local`

```bash
# Equivalent to:
docker build \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:local \
  -f backend/Dockerfile backend/
```

## Troubleshooting

### "docker buildx: command not found"

**Solution**: Enable Docker Buildx (included in Docker Desktop)

```bash
# Check if buildx is available
docker buildx version

# If not, enable experimental features in Docker Desktop
# Settings > Features in development > Enable experimental features
```

### "error: multiple platforms feature is currently not supported"

**Solution**: Create a buildx builder

```bash
docker buildx create --name mybuilder --use
docker buildx inspect --bootstrap
```

### "unauthorized: authentication required"

**Solution**: Authenticate with Google Cloud

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Image exists but pod still fails to pull

**Solution**: Check image exists and delete old pod

```bash
# Verify image exists
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/missing-table/missing-table/backend \
  --filter="tags:dev"

# Delete old pod to force new pull
kubectl delete pod -n missing-table-dev -l app.kubernetes.io/component=backend
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build and push
        run: ./build-and-push.sh all prod
```

## Manual Builds (Advanced)

If you need to build manually without the script:

### For GKE (AMD64)

```bash
docker buildx build \
  --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev \
  -f backend/Dockerfile backend/ \
  --push
```

### For Local (Current Platform)

```bash
docker build \
  -t missing-table-backend:local \
  -f backend/Dockerfile backend/
```

### Multi-Platform Build

```bash
# Build for both platforms (useful for testing)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:multi \
  -f backend/Dockerfile backend/ \
  --push
```

## Best Practices

1. **Always use the script for cloud deploys**: Prevents platform mismatch errors
2. **Tag with environment**: Use `:dev`, `:prod`, `:staging` tags for clarity
3. **Test locally first**: Use `local` builds before pushing to cloud
4. **Version your images**: Consider adding git commit SHA to tags for tracking
5. **Clean up old images**: Regularly remove unused images from Artifact Registry

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project overview and development commands
- [GKE HTTPS & Domain Setup](./GKE_HTTPS_DOMAIN_SETUP.md) - GKE deployment guide
- [Secret Management](./SECRET_MANAGEMENT.md) - Managing secrets in Kubernetes
