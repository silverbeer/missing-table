# Docker Platform Requirements for Missing Table

## CRITICAL: Platform Architecture Requirements

### The Problem
Docker images built on Mac (ARM64/Apple Silicon) are incompatible with GKE clusters (AMD64/x86_64).
This causes the error: `no match for platform in manifest: not found`

### The Solution
**ALWAYS use the `build-and-push.sh` script when building images for cloud deployment.**

## Build Script Usage

```bash
# For cloud deployment (GKE) - REQUIRED
./build-and-push.sh backend prod     # Prod environment (AMD64, push)
./build-and-push.sh frontend prod    # Prod environment (AMD64, push)
./build-and-push.sh all prod         # All services (AMD64, push)

# For local development only
./build-and-push.sh backend local    # Current platform, no push
```

## What the Script Does

1. **Cloud builds (prod)**:
   - Builds for `linux/amd64` platform (GKE requirement)
   - Pushes to Artifact Registry
   - Uses `docker buildx build --platform linux/amd64`

2. **Local builds**:
   - Builds for current platform
   - Does not push to registry
   - Uses standard `docker build`

## Manual Build Commands (NOT RECOMMENDED)

If you must build manually:

```bash
# ❌ WRONG - Will fail on GKE if built on Mac
docker build -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev backend/
docker push us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev

# ✅ CORRECT - Works on GKE
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/backend:dev \
  -f backend/Dockerfile backend/ --push
```

## Deployment After Build

```bash
# 1. Restart deployment to pull new image
kubectl rollout restart deployment/missing-table-backend -n missing-table-prod

# 2. Wait for rollout to complete
kubectl rollout status deployment/missing-table-backend -n missing-table-prod --timeout=180s

# 3. Check pod status
kubectl get pods -n missing-table-prod -l app.kubernetes.io/component=backend

# 4. View logs
kubectl logs -f -l app.kubernetes.io/component=backend -n missing-table-prod
```

## Environment-Specific Registries

- **Registry**: `us-central1-docker.pkg.dev/missing-table/missing-table`
- **Backend image**: `backend:{tag}`
- **Frontend image**: `frontend:{tag}`
- **Tags**: `local`, `dev`, `prod`, or custom tags

## Common Errors and Solutions

### Error: "no match for platform in manifest"
- **Cause**: Image built for ARM64 (Mac) but GKE needs AMD64
- **Solution**: Use `./build-and-push.sh backend dev` instead of manual docker build

### Error: "ImagePullBackOff"
- **Cause**: Image doesn't exist in registry or wrong tag
- **Solution**: Verify image exists: `gcloud artifacts docker images list us-central1-docker.pkg.dev/missing-table/missing-table/backend`

### Error: "Failed to pull image"
- **Cause**: Authentication or network issues
- **Solution**: Check GKE service account has Artifact Registry Reader role

## Claude Code Memory

When Claude is asked to build Docker images for cloud deployment:
1. **ALWAYS** use `./build-and-push.sh` script
2. **NEVER** use manual `docker build` commands for cloud
3. Remind the user about platform requirements if they suggest manual builds
