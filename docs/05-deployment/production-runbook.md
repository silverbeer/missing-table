# Production Operations Runbook

**Last Updated:** 2025-10-15

This runbook provides operational procedures for managing the Missing Table production environment.

## Table of Contents

- [Environment Overview](#environment-overview)
- [Deployment Procedures](#deployment-procedures)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Troubleshooting](#troubleshooting)
- [Rollback Procedures](#rollback-procedures)
- [Database Operations](#database-operations)
- [Emergency Procedures](#emergency-procedures)
- [Regular Maintenance](#regular-maintenance)

---

## Environment Overview

### Production Environment

- **URL:** https://missingtable.com
- **GKE Cluster:** `missing-table-prod`
- **Namespace:** `missing-table-prod`
- **Region:** `us-central1`
- **Database:** Supabase (production project)

### Architecture

```
┌─────────────────────────────────────────────┐
│           Google Cloud Load Balancer         │
│      (SSL Termination, Domain Routing)       │
└───────────────────┬─────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼────────┐    ┌────────▼────────┐
│    Frontend    │    │     Backend     │
│   (Vue.js)     │    │    (FastAPI)    │
│   2 replicas   │    │   2 replicas    │
└────────────────┘    └────────┬────────┘
                               │
                      ┌────────┴────────┐
                      │                 │
            ┌─────────▼──────┐  ┌──────▼────────┐
            │  Celery Worker │  │   Supabase    │
            │   2 replicas   │  │  (Managed)    │
            └────────────────┘  └───────────────┘
```

### Components

- **Frontend:** 2 replicas, nginx serving static Vue.js build
- **Backend:** 2 replicas, FastAPI with uvicorn
- **Celery Worker:** 2 replicas, processing async tasks
- **Database:** Supabase PostgreSQL (managed service)
- **Message Queue:** RabbitMQ (shared with dev)
- **SSL:** Google-managed certificates (auto-renewing)

---

## Deployment Procedures

### Automated Deployment (Recommended)

Production deployments happen automatically when changes are merged to `main`:

1. **Merge PR to main** - Triggers deploy-prod workflow
2. **Automatic build** - Docker images built with version tags
3. **Automatic deployment** - Helm deploys to production
4. **Health checks** - Automated verification
5. **Automatic rollback** - If health checks fail

**Monitor deployment:**
```bash
# Watch GitHub Actions
# Go to: https://github.com/silverbeer/missing-table/actions

# Or watch from CLI
gh run watch
```

### Manual Deployment (Emergency Only)

For emergency deployments outside normal CI/CD:

```bash
# Interactive deployment (recommended)
./scripts/deploy-prod.sh

# Deploy specific version
./scripts/deploy-prod.sh --version v1.2.3

# Skip health checks (dangerous!)
./scripts/deploy-prod.sh --version v1.2.3 --skip-health-check
```

**⚠️ Manual deployments should be rare. Always prefer CI/CD.**

### Pre-Deployment Checklist

Before any production deployment:

- [ ] All tests passing in CI/CD
- [ ] Changes reviewed and approved
- [ ] Database migrations tested in dev
- [ ] Breaking changes communicated to team
- [ ] Rollback plan identified
- [ ] Monitoring dashboard ready
- [ ] Off-hours deployment scheduled (if major change)

### Post-Deployment Verification

After deployment completes:

```bash
# 1. Check health endpoints
curl https://missingtable.com/health
curl https://missingtable.com/api/version

# 2. Verify deployments
kubectl get deployments -n missing-table-prod

# 3. Check pod status
kubectl get pods -n missing-table-prod

# 4. Run comprehensive health check
./scripts/health-check.sh prod

# 5. Verify in browser
# Visit: https://missingtable.com
# Check: Version footer shows correct version
# Test: Login, view standings, add match
```

---

## Monitoring and Alerting

### Key Metrics to Monitor

**Application Health:**
```bash
# Check all pods are running
kubectl get pods -n missing-table-prod

# Check pod restarts (should be 0 or very low)
kubectl get pods -n missing-table-prod -o wide

# Check service endpoints
kubectl get endpoints -n missing-table-prod
```

**Resource Usage:**
```bash
# Check pod resource usage
kubectl top pods -n missing-table-prod

# Check node resource usage
kubectl top nodes
```

**Application Logs:**
```bash
# Backend logs
kubectl logs -f -l app.kubernetes.io/component=backend -n missing-table-prod

# Frontend logs
kubectl logs -f -l app.kubernetes.io/component=frontend -n missing-table-prod

# Celery worker logs
kubectl logs -f -l app.kubernetes.io/component=celery-worker -n missing-table-prod

# All errors in last hour
kubectl logs -l app.kubernetes.io/name=missing-table -n missing-table-prod --since=1h | grep -i error
```

### Health Check Commands

```bash
# Automated health check
./scripts/health-check.sh prod

# Manual checks
curl -i https://missingtable.com/health
curl -i https://missingtable.com/api/version
curl -i https://missingtable.com/api/standings
```

### Performance Monitoring

**GCP Console Monitoring:**
1. Go to: https://console.cloud.google.com/kubernetes
2. Select cluster: `missing-table-prod`
3. View workloads, services, and metrics

**Helm Release History:**
```bash
# View deployment history
helm history missing-table -n missing-table-prod

# View current release status
helm status missing-table -n missing-table-prod
```

---

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

**Symptoms:** Pods stuck in `Pending`, `CrashLoopBackOff`, or `Error` state

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -n missing-table-prod

# Describe pod for events
kubectl describe pod <pod-name> -n missing-table-prod

# Check pod logs
kubectl logs <pod-name> -n missing-table-prod

# Check previous logs if pod restarted
kubectl logs <pod-name> -n missing-table-prod --previous
```

**Common Causes:**
- **Image pull errors:** Check image exists in registry
- **Resource limits:** Check if cluster has capacity
- **Configuration errors:** Check env vars, secrets
- **Database connection:** Verify Supabase credentials

**Resolution:**
```bash
# Fix configuration and redeploy
helm upgrade missing-table ./helm/missing-table \
  -n missing-table-prod \
  --values ./helm/missing-table/values-prod.yaml

# Or rollback if issue is from recent deployment
helm rollback missing-table -n missing-table-prod
```

#### 2. Application Not Accessible

**Symptoms:** Users cannot access https://missingtable.com

**Diagnosis:**
```bash
# Check ingress
kubectl get ingress -n missing-table-prod
kubectl describe ingress missing-table-ingress -n missing-table-prod

# Check services
kubectl get services -n missing-table-prod

# Check backend is responding
kubectl port-forward svc/missing-table-backend 8000:8000 -n missing-table-prod
# Then: curl http://localhost:8000/health

# Check SSL certificate
kubectl get managedcertificate -n missing-table-prod
```

**Common Causes:**
- **SSL cert not ready:** Wait for Google to provision (can take 15 min)
- **DNS not pointing to load balancer:** Check DNS records
- **Backend pods down:** Check pod status
- **Ingress misconfigured:** Check ingress resource

#### 3. High Error Rate

**Symptoms:** Application returning errors, users reporting issues

**Diagnosis:**
```bash
# Check recent errors
kubectl logs -l app.kubernetes.io/name=missing-table -n missing-table-prod --since=10m | grep -i error

# Check database connectivity
kubectl exec -it <backend-pod> -n missing-table-prod -- python -c "
from dao.supabase_data_access import SupabaseDataAccess
dao = SupabaseDataAccess()
print('Database connection OK')
"

# Check Supabase status
# Visit: https://status.supabase.com/
```

**Resolution:**
- Database issues: Check Supabase dashboard, verify credentials
- Application bugs: Review recent changes, consider rollback
- Resource exhaustion: Check resource usage, scale up if needed

#### 4. Slow Performance

**Symptoms:** Application slow to respond, timeouts

**Diagnosis:**
```bash
# Check resource usage
kubectl top pods -n missing-table-prod

# Check pod count
kubectl get deployments -n missing-table-prod

# Check database performance in Supabase dashboard
# Visit: https://app.supabase.com/ → Your project → Logs
```

**Resolution:**
```bash
# Scale up replicas
kubectl scale deployment missing-table-backend --replicas=3 -n missing-table-prod
kubectl scale deployment missing-table-frontend --replicas=3 -n missing-table-prod

# Or update Helm values and redeploy with higher replica count
```

---

## Rollback Procedures

### Automatic Rollback

Deployments use Helm's `--atomic` flag, which automatically rolls back if:
- Deployment times out (15 minutes)
- Health checks fail
- Pods don't reach ready state

### Manual Rollback

If you need to manually rollback a deployment:

```bash
# 1. View deployment history
helm history missing-table -n missing-table-prod

# Output example:
# REVISION  UPDATED               STATUS      CHART                 DESCRIPTION
# 1         Mon Oct 15 10:00:00  superseded  missing-table-1.0.0  Install complete
# 2         Mon Oct 15 14:00:00  deployed    missing-table-1.1.0  Upgrade complete

# 2. Rollback to previous revision
helm rollback missing-table -n missing-table-prod

# Or rollback to specific revision
helm rollback missing-table 1 -n missing-table-prod

# 3. Verify rollback
kubectl rollout status deployment/missing-table-backend -n missing-table-prod
kubectl rollout status deployment/missing-table-frontend -n missing-table-prod

# 4. Run health checks
./scripts/health-check.sh prod
```

### Emergency Rollback (Image Tags)

If Helm rollback fails, you can manually set image tags:

```bash
# Rollback backend to specific version
kubectl set image deployment/missing-table-backend \
  backend=us-central1-docker.pkg.dev/missing-table/missing-table/backend:v1.0.0 \
  -n missing-table-prod

# Rollback frontend to specific version
kubectl set image deployment/missing-table-frontend \
  frontend=us-central1-docker.pkg.dev/missing-table/missing-table/frontend:v1.0.0 \
  -n missing-table-prod

# Wait for rollout
kubectl rollout status deployment/missing-table-backend -n missing-table-prod
kubectl rollout status deployment/missing-table-frontend -n missing-table-prod
```

---

## Database Operations

### Database Access

**⚠️ Production database operations require extreme caution.**

```bash
# Access database via Supabase dashboard
# Visit: https://app.supabase.com/ → Your Project → SQL Editor

# Or use Supabase CLI (read-only recommended)
# Configure: supabase link --project-ref YOUR_PROJECT_REF
# Query: supabase db remote --db-url <PROD_DATABASE_URL> psql
```

### Database Backups

**Automated Backups:**
- Supabase automatically backs up production database daily
- Backups retained for 7 days (free tier) or 30+ days (paid tier)
- Access backups: Supabase Dashboard → Database → Backups

**Manual Backups:**
```bash
# Create backup before major changes
# Visit Supabase Dashboard → Database → Backups → Manual Backup
```

### Database Migrations

**⚠️ Always test migrations in dev environment first!**

```bash
# 1. Test migration in dev
./switch-env.sh dev
npx supabase db push

# 2. Verify migration works
./scripts/health-check.sh dev

# 3. After deploying code to prod, migration runs automatically
# (Migrations are applied during Helm upgrade)

# 4. Verify migration in prod
./scripts/health-check.sh prod
```

---

## Emergency Procedures

### Complete Site Outage

If https://missingtable.com is completely down:

1. **Assess the situation:**
   ```bash
   # Check cluster is accessible
   kubectl cluster-info

   # Check pod status
   kubectl get pods -n missing-table-prod

   # Check ingress
   kubectl get ingress -n missing-table-prod
   ```

2. **Quick diagnosis:**
   ```bash
   # Run health check
   ./scripts/health-check.sh prod

   # Check recent events
   kubectl get events -n missing-table-prod --sort-by='.lastTimestamp'

   # Check Helm status
   helm status missing-table -n missing-table-prod
   ```

3. **Immediate actions:**
   ```bash
   # If recent deployment caused it, rollback
   helm rollback missing-table -n missing-table-prod

   # If pods are down, restart them
   kubectl rollout restart deployment/missing-table-backend -n missing-table-prod
   kubectl rollout restart deployment/missing-table-frontend -n missing-table-prod

   # If ingress is down, reapply
   kubectl apply -f k8s/ingress-prod.yaml
   ```

4. **Escalation:**
   - Check GCP status: https://status.cloud.google.com/
   - Check Supabase status: https://status.supabase.com/
   - Review GitHub Actions for failed deployments
   - Contact team for assistance

### Database Emergency

If database is unavailable or corrupted:

1. **Verify issue:**
   ```bash
   # Check Supabase status
   # Visit: https://status.supabase.com/

   # Check connection from pod
   kubectl exec -it <backend-pod> -n missing-table-prod -- \
     python -c "import psycopg2; print('Testing connection...')"
   ```

2. **Immediate actions:**
   - Check Supabase dashboard for incidents
   - Verify credentials are correct in secrets
   - Check if connection limit reached

3. **Recovery:**
   - If credentials changed: Update secrets and redeploy
   - If database corrupted: Restore from Supabase backup
   - If Supabase outage: Wait for service restoration (check status page)

### Security Incident

If you suspect a security breach:

1. **Immediate containment:**
   ```bash
   # Scale down to zero to stop traffic
   kubectl scale deployment missing-table-backend --replicas=0 -n missing-table-prod
   kubectl scale deployment missing-table-frontend --replicas=0 -n missing-table-prod
   ```

2. **Investigation:**
   - Review recent logs
   - Check database for unauthorized changes
   - Review recent deployments and changes

3. **Recovery:**
   - Rotate all secrets
   - Deploy from known good version
   - Restore database if compromised
   - Update security rules

---

## Regular Maintenance

### Daily Tasks

```bash
# Check application health
./scripts/health-check.sh prod

# Check for pod restarts
kubectl get pods -n missing-table-prod -o wide

# Review error logs
kubectl logs -l app.kubernetes.io/name=missing-table -n missing-table-prod --since=24h | grep -i error
```

### Weekly Tasks

```bash
# Review Helm release history
helm history missing-table -n missing-table-prod

# Check resource usage trends
kubectl top pods -n missing-table-prod
kubectl top nodes

# Review GCP billing
# Visit: https://console.cloud.google.com/billing

# Check SSL certificate expiry
kubectl get managedcertificate -n missing-table-prod
```

### Monthly Tasks

- Review and clean up old Docker images in Artifact Registry
- Review Helm release history, document significant changes
- Review access logs and usage patterns
- Update dependencies and security patches
- Review and update runbook based on incidents

### Version Updates

```bash
# 1. Update VERSION file
./scripts/version-bump.sh minor  # or major/patch

# 2. Commit version change
git add VERSION
git commit -m "chore: bump version to $(cat VERSION)"

# 3. Push to trigger deployment
git push origin main

# 4. Monitor deployment
gh run watch

# 5. Verify deployment
./scripts/health-check.sh prod
```

---

## Contacts and Resources

### Important Links

- **Production Site:** https://missingtable.com
- **Dev Site:** https://dev.missingtable.com
- **GitHub Repository:** https://github.com/silverbeer/missing-table
- **GCP Console:** https://console.cloud.google.com/kubernetes
- **Supabase Dashboard:** https://app.supabase.com/

### Documentation

- [Deployment Overview](./README.md)
- [GKE Deployment Guide](./gke-deployment.md)
- [HTTPS Setup](./https-setup.md)
- [Architecture Documentation](../03-architecture/README.md)

### Status Pages

- **GCP Status:** https://status.cloud.google.com/
- **Supabase Status:** https://status.supabase.com/

---

**Remember:** Production changes should be deliberate, tested, and reversible. When in doubt, rollback and investigate offline.
