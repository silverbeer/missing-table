# Build Process Updates - Match-Scraper Integration

**Date**: 2025-10-13
**Status**: ✅ Complete

## Summary

Updated `build-and-push.sh` to support building the match-scraper Docker image alongside backend and frontend services. This standardizes the build process across all missing-table services.

---

## What Changed

### `build-and-push.sh` Updates

#### 1. **Added match-scraper as a Supported Service**
```bash
# Before
SUPPORTED_SERVICES=("backend" "frontend" "all")

# After
SUPPORTED_SERVICES=("backend" "frontend" "match-scraper" "all")
```

#### 2. **New Configuration Variable**
```bash
MATCH_SCRAPER_REPO="/Users/silverbeer/gitrepos/match-scraper"
```

Points to the external match-scraper repository location.

#### 3. **New Function: `build_match_scraper()`**
Handles building match-scraper from the external repository:

**Key features:**
- Validates match-scraper repo exists
- Changes to match-scraper directory
- Builds Docker image (local or AMD64)
- Returns to original directory
- Always tags as `latest` for cloud builds

**Error handling:**
- Checks if repository exists before building
- Provides helpful error message with clone command if missing
- Saves/restores current directory to avoid confusion

#### 4. **Updated `build_service()` Function**
Now routes match-scraper builds to the specialized function:

```bash
if [ "$service" = "match-scraper" ]; then
    build_match_scraper "$env" "$tag"
    return
fi
```

#### 5. **Enhanced Help Text**
- Added match-scraper to services list
- Added example: `./build-and-push.sh match-scraper dev`
- Added note about external repo location

#### 6. **Updated "all" Target**
When building all services, now includes match-scraper:
```bash
build_service "backend" "$ENVIRONMENT"
build_service "frontend" "$ENVIRONMENT"
build_service "match-scraper" "$ENVIRONMENT"
```

#### 7. **Match-Scraper Specific Next Steps**
Shows CronJob-specific deployment instructions instead of Deployment instructions:

```bash
Match-Scraper Deployment:
  1. Deploy CronJob:
     kubectl apply -f k8s/match-scraper-cronjob.yaml

  2. Create test job:
     kubectl create job --from=cronjob/match-scraper test-$(date +%s) ...

  3. View logs:
     kubectl logs -f -l app=match-scraper ...

  4. Check RabbitMQ queue:
     kubectl port-forward ... svc/messaging-rabbitmq 15672:15672
```

---

## Usage Examples

### Build match-scraper only
```bash
# For local testing (current platform, no push)
./build-and-push.sh match-scraper local

# For dev deployment (AMD64, push to registry)
./build-and-push.sh match-scraper dev

# For production (AMD64, push to registry)
./build-and-push.sh match-scraper prod
```

### Build all services
```bash
# Builds: backend, frontend, match-scraper
./build-and-push.sh all dev
```

### Build only backend/frontend (unchanged)
```bash
./build-and-push.sh backend dev
./build-and-push.sh frontend prod
```

---

## How It Works

### For Backend/Frontend (unchanged)
1. Uses local directories (`backend/`, `frontend/`)
2. Builds from local Dockerfiles
3. Pushes to registry if env is not "local"

### For Match-Scraper (new)
1. **Validates** match-scraper repo exists at configured path
2. **Saves** current directory
3. **Changes** to match-scraper directory
4. **Builds** Docker image from match-scraper's Dockerfile
5. **Pushes** to registry if env is not "local" (always tags as `latest`)
6. **Returns** to original directory

### Build Flow Diagram
```
./build-and-push.sh match-scraper dev
    ↓
Validate service & environment
    ↓
build_service("match-scraper", "dev")
    ↓
build_match_scraper("dev", "dev")
    ↓
Check repo exists → cd to repo → build → push → cd back
    ↓
Print success & next steps
```

---

## Error Handling

### Match-Scraper Repo Not Found
If the match-scraper repository doesn't exist:

```
ERROR: Match-scraper repository not found at: /Users/silverbeer/gitrepos/match-scraper
INFO: Please clone the repository first:
  git clone https://github.com/silverbeer/match-scraper.git /Users/silverbeer/gitrepos/match-scraper
```

### Invalid Service
```bash
./build-and-push.sh invalid-service dev
# ERROR: Invalid service: invalid-service
```

### Docker Not Available
Standard Docker error handling (script exits on error with `set -e`)

---

## Benefits

### 1. **Consistency**
All services built using the same standardized script with consistent:
- Command syntax
- Platform handling
- Registry configuration
- Error messages

### 2. **Convenience**
No need to:
- Remember match-scraper repo location
- Manually cd to different directories
- Switch between different build commands
- Remember different registry paths

### 3. **Safety**
- Validates repo exists before building
- Returns to original directory (won't leave you stranded)
- Clear error messages with solutions
- Won't accidentally build wrong architecture

### 4. **Build All**
Can now build entire stack with one command:
```bash
./build-and-push.sh all dev
```

### 5. **Documentation**
- Service-specific next steps
- Clear examples in help text
- Obvious location of external repo

---

## Comparison: Before vs After

### Before (without match-scraper support)
```bash
# Build backend/frontend
./build-and-push.sh backend dev
./build-and-push.sh frontend dev

# Build match-scraper (manual process)
cd /Users/silverbeer/gitrepos/match-scraper
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest \
  .
docker push us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper:latest
cd /Users/silverbeer/gitrepos/missing-table
```

### After (with match-scraper support)
```bash
# Build all services in one command
./build-and-push.sh all dev

# Or build just match-scraper
./build-and-push.sh match-scraper dev
```

**Lines of commands:**
- Before: 7 commands (with cd navigation)
- After: 1 command

---

## Integration with Deployment Scripts

### Works seamlessly with `deploy-match-scraper.sh`

The deployment script (`scripts/deploy-match-scraper.sh`) has an option to skip the build:

```bash
# Build with build-and-push.sh, then deploy
./build-and-push.sh match-scraper dev
./scripts/deploy-match-scraper.sh --skip-build

# Or let deploy-match-scraper.sh handle the build
./scripts/deploy-match-scraper.sh
```

**Recommendation:** Use `build-and-push.sh` when:
- Building multiple services together
- Just building (not deploying yet)
- Testing local builds

Use `deploy-match-scraper.sh` when:
- Deploying (optionally builds first)
- Need full deployment workflow
- Want to run test jobs

---

## Testing

### Verify the changes work:

```bash
# 1. Check help text
./build-and-push.sh

# 2. Test local build (won't push)
./build-and-push.sh match-scraper local

# 3. Verify image was built
docker images | grep match-scraper

# 4. Test cloud build (will push)
./build-and-push.sh match-scraper dev

# 5. Verify image in registry
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/missing-table/missing-table/match-scraper
```

---

## Future Enhancements

### Potential improvements:
1. **Auto-detect match-scraper repo location** (search common paths)
2. **Support building from different branches** (add `--branch` flag)
3. **Parallel builds** (build all services simultaneously)
4. **Build progress bars** (show detailed build progress)
5. **Build caching** (use Docker buildx cache)
6. **Image size reporting** (show final image size)
7. **Security scanning** (integrate Trivy scan after build)

---

## Related Documentation

- [Deployment Automation Guide](./DEPLOYMENT_AUTOMATION.md) - Complete deployment guide
- [Match-Scraper Deployment](./MATCH_SCRAPER_DEPLOYMENT.md) - Operational guide
- [RabbitMQ Integration Summary](./RABBITMQ_INTEGRATION_SUMMARY.md) - Architecture overview

---

## Migration Notes

### If you have existing scripts/workflows:

**Replace this pattern:**
```bash
cd /path/to/match-scraper
docker build --platform linux/amd64 -t ... .
docker push ...
cd -
```

**With this:**
```bash
./build-and-push.sh match-scraper dev
```

**GitHub Actions:** Consider updating workflows to use this script instead of inline docker commands.

---

**Last Updated**: 2025-10-13
**Script Version**: 2.0 (with match-scraper support)
