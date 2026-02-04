# Production Environment

## Overview

Missing Table production runs on **Linode Kubernetes Engine (LKE)**, managed via GitOps with ArgoCD.

**Migration history**: GKE (shutdown 2025-12-07) → DOKS (December 2025) → LKE (February 2026)

---

## Architecture

```
GitHub (main branch)
    ↓
CI Workflow (.github/workflows/ci.yml)
    ↓ builds images, pushes to GHCR
    ↓ updates helm/missing-table/values-prod.yaml
    ↓
ArgoCD (watches values-prod.yaml)
    ↓ syncs to cluster
    ↓
LKE Cluster
    ├── missing-table namespace
    │   ├── backend (FastAPI)
    │   ├── frontend (Vue/Nginx)
    │   └── redis (caching)
    ├── ingress-nginx
    ├── cert-manager (Let's Encrypt)
    └── external-secrets (AWS Secrets Manager)
```

---

## Infrastructure Repositories

| Repository | Purpose |
|------------|---------|
| **missing-table** (this repo) | Application code, Helm charts, CI/CD |
| **[missingtable-platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap)** | Terraform IaC, ArgoCD config, LKE provisioning |

---

## Key Configuration Files

| File | Purpose |
|------|---------|
| `helm/missing-table/values-prod.yaml` | Production Helm values (updated by CI) |
| `.github/workflows/ci.yml` | CI pipeline that builds and updates tags |

---

## Domains & Ingress

| Domain | Purpose |
|--------|---------|
| `missingtable.com` | Production frontend |
| `www.missingtable.com` | Redirect to main domain |
| `api.missingtable.com` | Production API |

- **Ingress Controller**: nginx
- **TLS**: Let's Encrypt via cert-manager
- **Force SSL**: Enabled

---

## Secrets Management

Secrets are managed via **External Secrets Operator** pulling from **AWS Secrets Manager**.

Secrets include:
- Supabase credentials (URL, anon key, service role key)
- GHCR image pull credentials

**Never commit secrets to git.**

---

## Deployment

### Automatic (GitOps)

1. Merge PR to `main`
2. CI builds images, pushes to GHCR
3. CI updates `values-prod.yaml` with new image tags
4. ArgoCD detects changes and syncs to LKE

### Manual (Emergency only)

```bash
# Check current state
kubectl get pods -n missing-table
kubectl get ingress -n missing-table

# Force ArgoCD sync (if needed)
# Access ArgoCD UI or use argocd CLI
```

---

## Monitoring & Debugging

### Check Pod Status
```bash
kubectl get pods -n missing-table
kubectl describe pod <pod-name> -n missing-table
kubectl logs <pod-name> -n missing-table
```

### Check Ingress
```bash
kubectl get ingress -n missing-table
kubectl describe ingress -n missing-table
```

### Check Certificates
```bash
kubectl get certificates -n missing-table
kubectl describe certificate missing-table-tls -n missing-table
```

### Health Endpoints
```bash
curl https://api.missingtable.com/health
curl https://missingtable.com/
```

---

## Version Information

Current version info is stored in `values-prod.yaml`:

```yaml
version: "X.Y.Z"     # Semantic version
buildId: "NNN"       # Build number
commitSha: "abc123"  # Git commit
buildDate: "..."     # Build timestamp
```

---

## Redis Caching

Redis is deployed alongside the application for caching:

```yaml
redis:
  enabled: true
backend:
  env:
    extra:
      CACHE_ENABLED: "true"
```

---

## Troubleshooting

### Site Not Loading
1. Check DNS resolution: `dig missingtable.com`
2. Check ingress: `kubectl get ingress -n missing-table`
3. Check pods: `kubectl get pods -n missing-table`
4. Check ArgoCD sync status

### API Errors
1. Check backend logs: `kubectl logs -l app=backend -n missing-table`
2. Check Supabase connectivity
3. Verify secrets are populated: `kubectl get secrets -n missing-table`

### Certificate Issues
1. Check cert-manager logs
2. Verify certificate status: `kubectl describe certificate -n missing-table`
3. Check Let's Encrypt rate limits

---

## Related Documentation

- [Deployment Guide](../05-deployment/README.md)
- [Secret Management](../SECRET_MANAGEMENT.md)
- [GKE Shutdown (Historical)](./GKE_SHUTDOWN_2025-12-07.md)
