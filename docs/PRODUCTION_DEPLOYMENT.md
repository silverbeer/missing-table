# Production Deployment Guide

Complete guide for deploying Missing Table to production at `missingtable.com`.

## 📋 Prerequisites Checklist

- [x] Production database set up and populated (Supabase)
- [x] Static IP reserved in GCP: **35.190.120.93**
- [x] Cloud DNS zone created: `missingtable-zone`
- [x] DNS nameservers configured in Namecheap
- [x] DNS records created in Cloud DNS
- [x] GitHub secrets configured
- [x] GKE production cluster created
- [ ] Production deployment completed
- [ ] SSL certificate provisioned

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

**CRITICAL**: DNS is managed in **Google Cloud DNS**, NOT Namecheap BasicDNS or AdvancedDNS!

### Architecture

```
Namecheap (Domain Registrar)
    ↓ (delegates via nameservers)
Google Cloud DNS (DNS Management)
    ↓ (hosts DNS records)
A Records point to GCP Load Balancers
```

### Step 1: Verify Cloud DNS Zone Exists

The Cloud DNS zone should already exist: `missingtable-zone`

```bash
# Check if zone exists
gcloud dns managed-zones describe missingtable-zone --project=missing-table

# Expected nameservers:
# - ns-cloud-d1.googledomains.com
# - ns-cloud-d2.googledomains.com
# - ns-cloud-d3.googledomains.com
# - ns-cloud-d4.googledomains.com
```

### Step 2: Configure Namecheap Nameservers

**⚠️ IMPORTANT**: Use **Custom DNS**, NOT BasicDNS or AdvancedDNS!

1. Go to: https://ap.www.namecheap.com/domains/domaincontrolpanel/missingtable.com/domain

2. Find the **NAMESERVERS** section

3. Select **"Custom DNS"** (NOT BasicDNS, NOT AdvancedDNS)

4. Enter these 4 nameservers:
   ```
   ns-cloud-d1.googledomains.com
   ns-cloud-d2.googledomains.com
   ns-cloud-d3.googledomains.com
   ns-cloud-d4.googledomains.com
   ```

5. Click **Save** (green checkmark)

### Step 3: Verify DNS Records in Cloud DNS

All DNS records are managed in Cloud DNS:

```bash
# List all DNS records
gcloud dns record-sets list --zone=missingtable-zone --project=missing-table

# Expected records:
# missingtable.com         A    35.190.120.93 (production)
# www.missingtable.com     A    35.190.120.93 (production)
# dev.missingtable.com     A    34.8.149.240  (development)
```

If production records are missing, create them:

```bash
# Add root domain A record
gcloud dns record-sets create missingtable.com. \
  --rrdatas=35.190.120.93 \
  --type=A \
  --ttl=300 \
  --zone=missingtable-zone \
  --project=missing-table

# Add www subdomain A record
gcloud dns record-sets create www.missingtable.com. \
  --rrdatas=35.190.120.93 \
  --type=A \
  --ttl=300 \
  --zone=missingtable-zone \
  --project=missing-table
```

### Step 4: Verify DNS Propagation

**DNS propagation takes 5-30 minutes after updating nameservers in Namecheap.**

```bash
# Check nameservers (should show Google Cloud DNS)
dig missingtable.com NS +short

# Check production records (query Google DNS directly)
dig @8.8.8.8 missingtable.com +short        # Should return: 35.190.120.93
dig @8.8.8.8 www.missingtable.com +short    # Should return: 35.190.120.93
dig @8.8.8.8 dev.missingtable.com +short    # Should return: 34.8.149.240
```

### DNS Troubleshooting

**Problem**: DNS not resolving locally but works with `@8.8.8.8`

**Cause**: Local DNS cache on your Mac

**Fix**: Flush DNS cache
```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

**Alternative**: Wait 5-15 minutes for cache to expire automatically

## 🏗️ GKE Production Cluster Setup

**IMPORTANT**: The production GKE cluster must be created before the first deployment.

### Check if Cluster Exists

```bash
gcloud container clusters list --project=missing-table --filter="name=missing-table-prod"
```

### Create Production Cluster (if needed)

If the cluster doesn't exist, create it:

```bash
gcloud container clusters create missing-table-prod \
  --project=missing-table \
  --region=us-central1 \
  --machine-type=e2-standard-2 \
  --disk-type=pd-standard \
  --disk-size=30 \
  --num-nodes=1 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=3 \
  --enable-autorepair \
  --enable-autoupgrade \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
  --no-enable-basic-auth \
  --enable-ip-alias \
  --network="projects/missing-table/global/networks/default" \
  --subnetwork="projects/missing-table/regions/us-central1/subnetworks/default" \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM
```

**⏱️ Cluster creation takes 5-10 minutes.**

### Cluster Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| **Name** | `missing-table-prod` | Production cluster |
| **Region** | `us-central1` | Regional (high availability) |
| **Machine Type** | `e2-standard-2` | 2 vCPUs, 8GB RAM |
| **Disk Type** | `pd-standard` | Standard persistent disk (quota friendly) |
| **Disk Size** | `30GB` | Per node |
| **Initial Nodes** | `1` | Can autoscale to 3 |
| **Autoscaling** | Enabled | Min: 1, Max: 3 |
| **Auto-repair** | Enabled | Automatic node repair |
| **Auto-upgrade** | Enabled | Automatic Kubernetes version updates |

**Note**: We use `pd-standard` disks instead of SSDs to avoid GCP quota issues. This is sufficient for production workloads.

### Monitor Cluster Creation

```bash
# Check cluster status
gcloud container clusters list --project=missing-table --filter="name=missing-table-prod"

# Watch for STATUS to change from PROVISIONING to RUNNING
# When ready, you'll see: STATUS: RUNNING
```

### Get Cluster Credentials

Once the cluster is running, configure kubectl access:

```bash
gcloud container clusters get-credentials missing-table-prod \
  --region=us-central1 \
  --project=missing-table
```

### Create Production Namespace

```bash
kubectl create namespace missing-table-prod
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

### Deployment Fails: Cluster Not Found

**Error**: `ResponseError: code=404, message=Not found: projects/.../clusters/missing-table-prod`

**Cause**: Production GKE cluster doesn't exist

**Fix**: Create the production cluster (see [GKE Production Cluster Setup](#-gke-production-cluster-setup))

```bash
# Verify cluster exists
gcloud container clusters list --project=missing-table --filter="name=missing-table-prod"

# If missing, create it (takes 5-10 minutes)
# See "Create Production Cluster" section above
```

### DNS Not Resolving

**Error**: `dig missingtable.com +short` returns nothing

**Possible Causes**:

1. **Namecheap using BasicDNS/AdvancedDNS instead of Custom DNS**
   - Fix: Switch to Custom DNS with Google Cloud nameservers (see DNS Configuration section)

2. **DNS records missing in Cloud DNS**
   ```bash
   # Check if records exist
   gcloud dns record-sets list --zone=missingtable-zone --project=missing-table

   # If missing, create them (see DNS Configuration section)
   ```

3. **Local DNS cache**
   ```bash
   # Test with Google DNS directly
   dig @8.8.8.8 missingtable.com +short

   # If that works, flush local cache
   sudo dscacheutil -flushcache
   sudo killall -HUP mDNSResponder
   ```

### Quota Exceeded Errors

**Error**: `Insufficient regional quota to satisfy request: resource "SSD_TOTAL_GB"`

**Cause**: GCP project has limited SSD quota

**Fix**: Use standard persistent disks instead of SSDs (already configured in cluster creation command)

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

## 📝 Complete Deployment Checklist

### Pre-Deployment (Infrastructure Setup)

- [x] Production Supabase database created and populated
- [x] Static IP reserved in GCP (`35.190.120.93`)
- [x] Cloud DNS zone created (`missingtable-zone`)
- [x] Namecheap configured with Custom DNS nameservers
- [x] DNS A records created in Cloud DNS
- [x] GitHub secrets configured (all 9 production secrets)
- [x] GKE production cluster created (`missing-table-prod`)
- [x] Production namespace created (`missing-table-prod`)

### During Deployment

- [ ] GitHub Actions workflow completes successfully
- [ ] Docker images built and pushed to Artifact Registry
- [ ] Helm deployment completes without errors
- [ ] Pods start successfully and reach Running state
- [ ] Ingress created with correct IP and hostname
- [ ] ManagedCertificate resource created

### Post-Deployment Verification

- [ ] DNS resolves correctly (test with `dig @8.8.8.8 missingtable.com`)
- [ ] Backend pods are running (`kubectl get pods -n missing-table-prod`)
- [ ] Frontend pods are running
- [ ] Backend API responds (`curl https://missingtable.com/api/health`)
- [ ] Frontend loads (`curl https://missingtable.com/`)
- [ ] SSL certificate provisioned (10-20 min, check with `kubectl describe managedcertificate`)
- [ ] Can log in with admin account (tom@missingtable.local)
- [ ] Database queries work (view teams/matches in UI)
- [ ] All 587 records visible (26 teams, 315 matches)

### Post-Deployment Tasks

- [ ] Users notified to change passwords from TempPassword123!
- [ ] Monitoring/alerts configured (if applicable)
- [ ] Update documentation with any lessons learned
- [ ] Take backup of production database

## 🔗 Related Documentation

- [Development Workflow](./02-development/README.md)
- [Secret Management](./SECRET_MANAGEMENT.md)
- [GKE HTTPS Setup](./GKE_HTTPS_DOMAIN_SETUP.md)
- [Database Restore](../scripts/db_tools.sh)

---

**Last Updated**: 2025-10-16
**Maintained By**: Dev Team
