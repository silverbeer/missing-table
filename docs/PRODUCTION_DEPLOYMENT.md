# Production Deployment Guide

Complete guide for deploying Missing Table to production at `missingtable.com`.

## 📋 Prerequisites

- [x] Production database set up and populated (Supabase)
- [x] Static IP reserved in GCP: **35.190.120.93**
- [ ] DNS configured in Namecheap
- [ ] GitHub secrets configured
- [ ] GKE cluster ready

## 🌐 Infrastructure

### Static IP Addresses

| Environment | IP Address | Type | Status |
|------------|------------|------|--------|
| Dev | 34.8.149.240 | Global | IN_USE |
| **Prod** | **35.190.120.93** | Global | RESERVED |

### Domains

| Domain | Points To | Purpose |
|--------|-----------|---------|
| `missingtable.com` | 35.190.120.93 | Production |
| `www.missingtable.com` | 35.190.120.93 | Production (www) |
| `dev.missingtable.com` | 34.8.149.240 | Development |

## 🔐 GitHub Secrets Required

Add these secrets to your GitHub repository at:
`https://github.com/YOUR_ORG/missing-table/settings/secrets/actions`

### GCP Authentication
```
GCP_PROJECT_ID=missing-table
GCP_SA_KEY=<contents of service account JSON key>
```

### Production Database (Supabase)
```
PROD_DATABASE_URL=postgresql://postgres:1zRi0qU0g7EsRCNQ@db.iueycteoamjbygwhnovz.supabase.co:5432/postgres
PROD_SUPABASE_URL=https://iueycteoamjbygwhnovz.supabase.co
PROD_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1ZXljdGVvYW1qYnlnd2hub3Z6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA1NTE4NTEsImV4cCI6MjA3NjEyNzg1MX0.eU1AlRroV3TZAOPqsYd26qq_PqcrD81o89xXhOJGPM4
PROD_SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1ZXljdGVvYW1qYnlnd2hub3Z6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDU1MTg1MSwiZXhwIjoyMDc2MTI3ODUxfQ.ELHFVsjYdtyZIbVwckS0DcLHNCd3QRthc-R0BcZgNBY
PROD_SUPABASE_JWT_SECRET=YbLYG7JATrKDtitKs8Gm0U/00k1Qo0jXP8zXGVQApaNKR5punYZ4xhQDeReYUEIbthtNAUgrDl3s6QhI+wFsMw==
```

### Production Security
```
PROD_SERVICE_ACCOUNT_SECRET=UgQRfAk1oK5hA/x+lHF0qskDTmGBj3FEPdW9OitNVB0=
```

### RabbitMQ (if using match-scraper)
```
PROD_RABBITMQ_USERNAME=your-rabbitmq-username
PROD_RABBITMQ_PASSWORD=your-rabbitmq-password
PROD_RABBITMQ_HOST=messaging-rabbitmq.missing-table-prod.svc.cluster.local
```

## 📡 DNS Configuration

### Namecheap Setup

1. Go to: https://ap.www.namecheap.com/domains/domaincontrolpanel/missingtable.com/advancedns

2. Add these **A Records**:

   | Type | Host | Value | TTL |
   |------|------|-------|-----|
   | A Record | @ | 35.190.120.93 | Automatic |
   | A Record | www | 35.190.120.93 | Automatic |
   | A Record | dev | 34.8.149.240 | Automatic |

3. **Remove** any conflicting records (CNAME for @ or www)

4. **Verify DNS propagation** (takes 5-30 minutes):
   ```bash
   dig missingtable.com +short
   dig www.missingtable.com +short
   # Both should return: 35.190.120.93
   ```

## 🚀 Deployment Workflow

### Automatic Deployment

The production deployment is triggered automatically when changes are merged to `main`:

```yaml
# .github/workflows/deploy-production.yml
on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger option
```

### Manual Deployment

Trigger manually via GitHub Actions:

1. Go to: `https://github.com/YOUR_ORG/missing-table/actions`
2. Select "Deploy to Production"
3. Click "Run workflow"
4. Select branch: `main`
5. Click "Run workflow"

### Deployment Steps (Automated)

1. **Build Docker images** with version tags
2. **Push to GCP Artifact Registry**
3. **Deploy to GKE** using Helm
4. **Configure Ingress** with SSL/TLS
5. **Health checks** to verify deployment
6. **Rollback** automatically if health checks fail

## 🏥 Health Checks

After deployment, the workflow verifies:

- ✅ Backend API responding at `/api/health`
- ✅ Frontend serving at `/`
- ✅ Database connectivity
- ✅ Pods running and ready
- ✅ Ingress configured correctly

## 🔍 Verification Commands

```bash
# Check GKE deployment status
kubectl get pods -n missing-table-prod
kubectl get ingress -n missing-table-prod
kubectl get services -n missing-table-prod

# Check SSL certificate status
kubectl describe managedcertificate -n missing-table-prod

# View logs
kubectl logs -n missing-table-prod -l app=backend --tail=100
kubectl logs -n missing-table-prod -l app=frontend --tail=100

# Test endpoints
curl https://missingtable.com/api/health
curl https://missingtable.com/
```

## 🔄 Rollback Procedure

### Automatic Rollback

The workflow includes automatic rollback via Helm's `--atomic` flag:
- If deployment fails, automatically reverts to previous version
- Triggered by failed health checks or pod startup failures

### Manual Rollback

```bash
# List deployment history
helm history missing-table -n missing-table-prod

# Rollback to previous version
helm rollback missing-table -n missing-table-prod

# Rollback to specific revision
helm rollback missing-table 5 -n missing-table-prod
```

## 🎯 User Access

### Login Credentials

Production users restored from dev:

| Email | Password | Role |
|-------|----------|------|
| tom@missingtable.local | TempPassword123! | Admin |
| tdrake13@gmail.com | TempPassword123! | Admin |
| match-scraper@service.missingtable.com | TempPassword123! | Service Account |

**⚠️ Important**: Users should change passwords after first login.

### Creating New Admin Users

```bash
# After user signs up via UI
cd backend
APP_ENV=prod uv run python make_user_admin.py --email user@example.com
```

## 📊 Monitoring

### Logs

```bash
# Real-time logs
kubectl logs -f -n missing-table-prod -l app=backend
kubectl logs -f -n missing-table-prod -l app=frontend

# Search logs
kubectl logs -n missing-table-prod -l app=backend | grep ERROR
```

### Metrics

```bash
# Pod resource usage
kubectl top pods -n missing-table-prod

# Node usage
kubectl top nodes
```

### Endpoints

- **API Health**: https://missingtable.com/api/health
- **API Version**: https://missingtable.com/api/version
- **Frontend**: https://missingtable.com/

## 🐛 Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n missing-table-prod

# Describe pod for events
kubectl describe pod <pod-name> -n missing-table-prod

# Check logs
kubectl logs <pod-name> -n missing-table-prod
```

### SSL Certificate Issues

```bash
# Check certificate status
kubectl describe managedcertificate -n missing-table-prod

# SSL takes 10-20 minutes to provision after DNS is configured
# Status should show: Status: Active
```

### 502 Bad Gateway

Usually indicates pods aren't ready:

```bash
# Check pod health
kubectl get pods -n missing-table-prod

# Check service endpoints
kubectl get endpoints -n missing-table-prod

# Restart deployment
kubectl rollout restart deployment/missing-table-backend -n missing-table-prod
```

### Database Connection Issues

```bash
# Test from backend pod
kubectl exec -it <backend-pod> -n missing-table-prod -- \
  python -c "from supabase import create_client; import os; client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY')); print(client.table('teams').select('count').execute())"
```

## 📝 Post-Deployment Checklist

- [ ] DNS resolves correctly (`dig missingtable.com`)
- [ ] HTTPS is working (no certificate errors)
- [ ] Can log in with admin account
- [ ] Backend API responds (`/api/health`)
- [ ] Frontend loads correctly
- [ ] Database queries work (view teams/matches)
- [ ] Users notified to change passwords
- [ ] Monitoring/alerts configured

## 🔗 Related Documentation

- [Development Workflow](./02-development/README.md)
- [Secret Management](./SECRET_MANAGEMENT.md)
- [GKE HTTPS Setup](./GKE_HTTPS_DOMAIN_SETUP.md)
- [Database Restore](../scripts/db_tools.sh)

---

**Last Updated**: 2025-10-16
**Maintained By**: Dev Team
