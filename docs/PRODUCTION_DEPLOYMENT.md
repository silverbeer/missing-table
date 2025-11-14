# Production Deployment Guide - DEPRECATED

**⚠️ This document is DEPRECATED as of 2025-11-14**

## Infrastructure Consolidation Complete

The separate production environment has been **consolidated into `missing-table-dev`** to reduce costs from $283/month to $40/month (86% reduction).

## Current Production Setup

**All domains now point to the unified `missing-table-dev` namespace:**

- ✅ https://dev.missingtable.com
- ✅ https://missingtable.com
- ✅ https://www.missingtable.com

**Infrastructure:**
- **Namespace**: `missing-table-dev` (single consolidated environment)
- **GKE Cluster**: `missing-table-dev`
- **Database**: Dev Supabase database (ppgxasqgqbnauvxozmjw.supabase.co)
- **SSL**: Let's Encrypt via cert-manager
- **Ingress**: nginx ingress controller
- **IP Address**: 34.173.92.110 (nginx ingress)

## Updated Documentation

For current deployment procedures, see:

- **[Deployment Guide](./05-deployment/README.md)** - Overview of deployment process
- **[Production Runbook](./05-deployment/production-runbook.md)** - Operational procedures
- **[GKE Deployment](./05-deployment/gke-deployment.md)** - GKE-specific deployment details
- **[CLAUDE.md](../CLAUDE.md)** - Quick reference for common commands

## Deployment Workflow

**Automatic deployment** via GitHub Actions:
- Push to **any branch** → deploys to `missing-table-dev`
- Serves all three domains from single environment
- Zero downtime deployments with automatic rollback

## Quick Commands

```bash
# Check deployment status
kubectl get pods -n missing-table-dev
kubectl get ingress -n missing-table-dev
kubectl get certificate -n missing-table-dev

# View logs
kubectl logs -l app.kubernetes.io/component=backend -n missing-table-dev
kubectl logs -l app.kubernetes.io/component=frontend -n missing-table-dev

# Test endpoints
curl https://dev.missingtable.com/api/health
curl https://missingtable.com/api/health
curl https://www.missingtable.com/api/health
```

## What Changed

**Deleted:**
- ❌ `missing-table-prod` GKE cluster
- ❌ `missing-table-prod` namespace
- ❌ Production Supabase database (iueycteoamjbygwhnovz)
- ❌ GCE ingress (35.190.120.93)
- ❌ Google-managed certificates
- ❌ Separate prod environment

**Consolidated:**
- ✅ Single `missing-table-dev` namespace
- ✅ Single GKE cluster
- ✅ nginx ingress controller
- ✅ Let's Encrypt SSL certificates (auto-renewing)
- ✅ All domains served from one environment

## Cost Savings

- **Before**: $283/month
- **After**: $40/month
- **Savings**: $243/month ($2,916/year) - 86% reduction

---

**Last Updated**: 2025-11-14
**Deprecation Reason**: Infrastructure consolidated to reduce costs
**Old Version**: Archived at `.archive/docs/PRODUCTION_DEPLOYMENT_DEPRECATED_20251114.md`
