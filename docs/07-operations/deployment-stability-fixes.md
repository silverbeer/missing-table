# Deployment Stability Fixes

**Date**: 2025-10-28
**Status**: ✅ RESOLVED

## Executive Summary

Dev environment deployments were experiencing severe instability with timeouts, failed deployments, and connection resets. Root cause identified and fixed.

## Problems Identified

### 1. Celery Workers Always Deployed (CRITICAL)
**Symptom**: Celery worker pods in CrashLoopBackOff, Helm upgrades timing out
**Root Cause**: `helm/missing-table/templates/celery-worker.yaml` had NO conditional check for `.Values.celeryWorker.enabled`

```yaml
# Before (BROKEN)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: missing-table-celery-worker
  # ... always deployed!
```

**Impact**:
- Celery workers deployed even when `enabled: false`
- Workers crashed (couldn't reach RabbitMQ on local K3s)
- Helm waited for crashing pods to be ready → timeout
- Every deployment took 10+ minutes or failed
- Manual scaling to 0 required after each deployment

**Fix**: `helm/missing-table/templates/celery-worker.yaml:1`
```yaml
{{- if .Values.celeryWorker.enabled }}
apiVersion: apps/v1
# ... deployment spec
{{- end }}
```

**Result**:
- ✅ No celery deployment when `enabled: false`
- ✅ Deployments complete in 1-2 minutes
- ✅ Clean pod status: backend + frontend only

### 2. Frontend Using Wrong API URL
**Symptom**: 403 Forbidden errors on all API calls
**Root Cause**: Frontend configured for local development

```yaml
# Before (BROKEN)
frontend:
  env:
    nodeEnv: "development"  # Should be "production"
    apiUrl: "http://missing-table-backend:8000"  # Internal K8s service
```

**Impact**:
- Browsers can't access internal Kubernetes service names
- All `/api/*` calls failed with 403
- Site appeared to load but no data

**Fix**: `helm/missing-table/values-dev.yaml`
```yaml
frontend:
  env:
    nodeEnv: "production"  # Use pre-built Vue app
    apiUrl: "https://dev.missingtable.com"  # Public Ingress URL
```

**Result**:
- ✅ API calls route through Ingress
- ✅ Backend properly receives authenticated requests

### 3. Missing Ingress Configuration
**Symptom**: ERR_CONNECTION_RESET, site completely unreachable
**Root Cause**: Ingress configuration accidentally removed during values-dev.yaml update

**Impact**:
- No load balancer
- No public IP address
- No route from dev.missingtable.com → pods

**Fix**: Added to `helm/missing-table/values-dev.yaml`
```yaml
ingress:
  enabled: true
  hosts:
    - dev.missingtable.com
  staticIpName: missing-table-dev-ip
```

**Result**:
- ✅ GCP Ingress created (34.8.149.240)
- ✅ HTTPS with managed certificates
- ✅ HTTP → HTTPS redirect

## Tools Created

### 1. scripts/fix-dev-values.sh
Automatically updates `values-dev.yaml` with correct GKE configuration:
- Sets `frontend.env.nodeEnv: "production"`
- Sets `frontend.env.apiUrl: "https://dev.missingtable.com"`
- Sets `celeryWorker.enabled: false`
- Adds Ingress configuration if missing
- Creates timestamped backups

**Usage**:
```bash
./scripts/fix-dev-values.sh
helm upgrade missing-table ./helm/missing-table -n missing-table-dev \
  --values ./helm/missing-table/values-dev.yaml --wait
```

## Timeline of Issues

| Date | Issue | Impact | Resolution |
|------|-------|--------|------------|
| Oct 24-27 | Celery workers crashing | Deployment timeouts | Manual scaling to 0 |
| Oct 28 00:46 | Helm lock (rev 7) | CI/CD deployment failed | Deleted stuck secret |
| Oct 28 01:22 | Successful deployment | Temporary fix | Rev 7 deployed |
| Oct 28 08:18 | Frontend config wrong | 403 errors | Updated values-dev.yaml |
| Oct 28 08:50 | Missing Ingress | Connection reset | Re-added Ingress config |
| Oct 28 10:25 | **ROOT CAUSE FIX** | All stable ✅ | Added celeryWorker.enabled check |

## Verification

### Before Fixes
```bash
$ kubectl get pods -n missing-table-dev
NAME                                           READY   STATUS
missing-table-backend-769b967654-krq4m         1/1     Running
missing-table-celery-worker-6dc5956fb7-c48zv   0/1     CrashLoopBackOff  # ❌
missing-table-celery-worker-6dc5956fb7-gqhz6   0/1     CrashLoopBackOff  # ❌
missing-table-frontend-654c8bd7f8-n2n5q        1/1     Running

$ helm history missing-table -n missing-table-dev
7    pending-upgrade    # ❌ Stuck
```

### After Fixes
```bash
$ kubectl get pods -n missing-table-dev
NAME                                      READY   STATUS
missing-table-backend-66d46f8887-jlhct    1/1     Running  # ✅
missing-table-frontend-5cf96db5d4-ggbmt   1/1     Running  # ✅
# No celery workers! ✅

$ helm history missing-table -n missing-table-dev
11   deployed           # ✅ Clean deployment
```

## Prevention Measures

### 1. Template Best Practices
All optional components should have conditional checks:
```yaml
{{- if .Values.component.enabled }}
# component definition
{{- end }}
```

### 2. Configuration Validation
Created `scripts/fix-dev-values.sh` to ensure correct GKE configuration

### 3. values-dev.yaml.example
Updated example file to match actual GKE requirements:
- `celeryWorker.enabled: false` documented
- Frontend production configuration documented
- Ingress configuration documented

### 4. Documentation
- [GKE HTTPS & Domain Setup Guide](../docs/GKE_HTTPS_DOMAIN_SETUP.md)
- [Secret Management Guide](../docs/SECRET_MANAGEMENT.md)
- [CLAUDE.md:703-705](../../CLAUDE.md) - Celery runs on local K3s only

## Current State

### Dev Environment (GKE)
- **URL**: https://dev.missingtable.com
- **Status**: ✅ Stable
- **Pods**: Backend + Frontend only
- **Deployment Time**: 1-2 minutes
- **Last Successful Deployment**: Rev 11 (2025-10-28 10:25:40)

### Components Status
| Component | GKE Dev | Local K3s | Notes |
|-----------|---------|-----------|-------|
| Backend | ✅ Running | ✅ Running | FastAPI application |
| Frontend | ✅ Running | ✅ Running | Vue 3 SPA |
| Celery Worker | ❌ Disabled | ✅ Running | Async match processing |
| RabbitMQ | ❌ Not deployed | ✅ Running | Message broker |
| Redis | ❌ Not deployed | ✅ Running | Result backend |

## Lessons Learned

1. **Always add conditionals for optional components** in Helm templates
2. **Test template rendering** before deployment: `helm template ...`
3. **Environment-specific configuration** must match deployment target
4. **Ingress is critical** - should never be accidentally removed
5. **Crashing pods prevent Helm from completing** - fix or disable them

## Related Files

### Modified
- `helm/missing-table/templates/celery-worker.yaml` - Added conditional check
- `helm/missing-table/values-dev.yaml` - Fixed frontend + Ingress config

### Created
- `scripts/fix-dev-values.sh` - Configuration fixer script
- `docs/07-operations/deployment-stability-fixes.md` - This document

### Referenced
- `CLAUDE.md` - Project documentation
- `helm/missing-table/values-dev.yaml.example` - Configuration template

## Remaining Work

- [ ] Update GitHub Actions workflow with proper timeout handling
- [ ] Add pre-deployment validation to CI/CD
- [ ] Create deployment health checks script
- [ ] Add monitoring/alerting for pod CrashLoopBackOff

---

**Issue Reported By**: User
**Fixed By**: Claude Code
**Status**: ✅ RESOLVED
**Impact**: Dev deployments now stable and reliable
