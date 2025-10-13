# Deployment Cleanup - October 13, 2025

## Summary

Consolidated all services into a single namespace (`missing-table-dev`) for better management and removed obsolete resources.

## What Was Cleaned Up

### ✅ Deleted Namespaces
1. **`messaging` namespace** - Old messaging platform deployment
   - Had: RabbitMQ + Redis deployments
   - Replaced by: Helm-managed resources in `missing-table-dev`

2. **`match-scraper` namespace** - Old match-scraper deployment  
   - Had: `mls-scraper-cronjob` (daily at 6am UTC, no RabbitMQ)
   - Replaced by: New `match-scraper` CronJob in `missing-table-dev` (every 6 hours, with RabbitMQ)

### ✅ Deprecated Files
- `k8s/messaging-stack.yaml` - Replaced with deprecation notice
  - Now using: `helm/messaging-platform/` Helm chart

## Current Clean State

### Single Namespace: `missing-table-dev`

**Running Services:**
- Backend (1 pod)
- Frontend (1 pod)
- Celery Workers (2 pods)
- RabbitMQ (1 StatefulSet with persistent storage)
- Redis (1 StatefulSet with persistent storage)
- Match-Scraper CronJob (schedule: every 6 hours)

**Benefits of Consolidation:**
- ✅ Simpler RBAC management
- ✅ No cross-namespace networking needed
- ✅ Easier to monitor and troubleshoot
- ✅ Consistent Helm-based deployment
- ✅ All secrets in one place

## Deployment Method

Everything is now deployed via Helm:

```bash
# Deploy main application (backend, frontend, celery, secrets)
helm upgrade --install missing-table ./helm/missing-table \
  -n missing-table-dev --values ./helm/missing-table/values-dev.yaml

# Deploy messaging platform (RabbitMQ, Redis)  
helm upgrade --install messaging-platform ./helm/messaging-platform \
  -n missing-table-dev --values ./helm/messaging-platform/values-dev.yaml

# Deploy match-scraper CronJob
kubectl apply -f k8s/match-scraper-cronjob.yaml
```

## CronJob Schedule

**Match-Scraper:**
- Schedule: `0 */6 * * *` (every 6 hours)
- Run times: 00:00, 06:00, 12:00, 18:00 UTC
- Features: RabbitMQ integration, headless browser scraping
- Namespace: `missing-table-dev`

## Next Steps

None needed - everything is clean and consolidated! 🎉

---

**Date:** 2025-10-13  
**By:** Claude Code assisted deployment
