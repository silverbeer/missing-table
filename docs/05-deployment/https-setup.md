# DEPRECATED — Historical Reference

> **GKE was shut down on 2025-12-07.** HTTPS/TLS is now managed by cert-manager + Let's Encrypt in the current cloud K8s cluster. See [Production Environment](../07-operations/CLOUD_K8S_PRODUCTION.md) for current setup.
>
> This document is preserved for historical reference only.

---

# GKE HTTPS & Custom Domain Setup Guide (Historical)

**Project:** Missing Table
**Environment:** Development (dev.missingtable.com — no longer exists)
**Date Completed:** October 3, 2025
**Time to Complete:** ~90 minutes

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Step-by-Step Setup](#step-by-step-setup)
- [Troubleshooting](#troubleshooting)
- [Verification](#verification)
- [Cost Analysis](#cost-analysis)
- [Production Setup](#production-setup)
- [Maintenance](#maintenance)

---

## Overview

This guide documents the complete process of setting up HTTPS with a custom domain for a GKE application using:
- **Google Cloud DNS** for domain management
- **GCP Ingress** for load balancing
- **Google-managed SSL certificates** for HTTPS
- **Custom domain** (dev.missingtable.com)

### What This Achieves

- ✅ HTTPS enabled with auto-renewing SSL certificates
- ✅ Custom domain instead of IP addresses
- ✅ Single load balancer for frontend + backend (cost savings)
- ✅ HTTP/2 support
- ✅ Professional dev/prod separation

### Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Frontend URL** | http://34.133.125.204:8080 | https://dev.missingtable.com |
| **Backend URL** | http://34.135.217.253:8000 | https://dev.missingtable.com/api |
| **Load Balancers** | 2 (Network LBs) | 1 (Application LB) |
| **SSL** | None | Google-managed, auto-renewing |
| **Protocol** | HTTP/1.1 | HTTP/2 |
| **Monthly Cost** | ~$36 | ~$25-30 |

---

## Prerequisites

### Required Access

- [x] GCP Project: `missing-table`
- [x] GKE Cluster: `missing-table-dev-cluster` in `us-central1`
- [x] Kubernetes namespace: `missing-table-dev`
- [x] Domain purchased: `missingtable.com` (from Namecheap)
- [x] `gcloud` CLI authenticated
- [x] `kubectl` configured for the cluster

### Required Permissions

- Compute Admin (for static IPs, load balancers)
- DNS Administrator (for Cloud DNS)
- Kubernetes Engine Admin (for ingress)

### Existing Deployment

Before starting, you should have:
- Frontend service (type: LoadBalancer)
- Backend service (type: ClusterIP + LoadBalancer)
- Both services running and healthy

---

## Architecture

### Network Flow

```
User Browser
    ↓ HTTPS
dev.missingtable.com (34.8.149.240)
    ↓
Google Cloud Load Balancer
    ↓
GKE Ingress Controller
    ├─→ /api/* → Backend Service (ClusterIP:8000)
    ├─→ /health → Backend Service (ClusterIP:8000)
    └─→ /* → Frontend Service (ClusterIP:8080)
```

### DNS Hierarchy

```
missingtable.com (Namecheap)
    ↓ NS records point to →
Google Cloud DNS (authoritative)
    ↓ A record →
dev.missingtable.com → 34.8.149.240 (static IP)
```

### SSL Certificate Flow

```
GKE ManagedCertificate Resource
    ↓ requests
Google Certificate Manager
    ↓ validates (HTTP-01 challenge)
Let's Encrypt (via Google)
    ↓ issues
SSL Certificate (auto-attached to Load Balancer)
    ↓ auto-renews before
Expiry Date (90 days)
```

---

## Step-by-Step Setup

### Step 1: Reserve Static Global IP

**Why:** GCP load balancers need a stable IP address for DNS.

```bash
# Reserve a global static IP address
gcloud compute addresses create missing-table-dev-ip \
  --global \
  --project=missing-table

# Get the IP address
gcloud compute addresses describe missing-table-dev-ip \
  --global \
  --project=missing-table \
  --format="get(address)"
```

**Output:**
```
34.8.149.240
```

**Record this IP - you'll need it for DNS!**

---

### Step 2: Create Cloud DNS Zone

**Why:** Google Cloud DNS provides fast, reliable DNS with automatic integration to GCP services.

```bash
# Create a managed DNS zone
gcloud dns managed-zones create missingtable-zone \
  --dns-name=missingtable.com. \
  --description="DNS zone for missingtable.com" \
  --project=missing-table

# Get the nameservers
gcloud dns managed-zones describe missingtable-zone \
  --project=missing-table \
  --format="get(nameServers)"
```

**Output (your nameservers - SAVE THESE):**
```
ns-cloud-d1.googledomains.com.
ns-cloud-d2.googledomains.com.
ns-cloud-d3.googledomains.com.
ns-cloud-d4.googledomains.com.
```

---

### Step 3: Add DNS A Record

**Why:** Points your subdomain to the static IP.

```bash
# Create A record for dev subdomain
gcloud dns record-sets create dev.missingtable.com. \
  --zone=missingtable-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=34.8.149.240 \
  --project=missing-table
```

**Output:**
```
NAME                   TYPE  TTL  DATA
dev.missingtable.com.  A     300  34.8.149.240
```

---

### Step 4: Update Namecheap Nameservers

**Why:** Transfer DNS authority from Namecheap to Google Cloud DNS.

**Manual Steps:**

1. Log in to [Namecheap](https://www.namecheap.com)
2. Go to Domain List → Click "Manage" next to `missingtable.com`
3. Find the "Nameservers" section
4. Select "Custom DNS"
5. Enter the 4 Google nameservers (from Step 2):
   ```
   ns-cloud-d1.googledomains.com
   ns-cloud-d2.googledomains.com
   ns-cloud-d3.googledomains.com
   ns-cloud-d4.googledomains.com
   ```
6. Click "Save"

**Propagation Time:** 5 minutes to 48 hours (typically 30-60 minutes)

**Verify DNS propagation:**
```bash
# Check nameservers
dig NS missingtable.com +short

# Check A record
dig dev.missingtable.com +short

# Should return: 34.8.149.240
```

---

### Step 5: Create Kubernetes Ingress Resource

**Why:** Configures the GCP load balancer with routing rules and SSL.

Create file: `k8s/ingress-dev.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: missing-table-ingress
  namespace: missing-table-dev
  annotations:
    # Use GCP Global Load Balancer
    kubernetes.io/ingress.class: "gce"
    # Enable HTTPS redirect
    kubernetes.io/ingress.allow-http: "true"
    # Use Google-managed SSL certificate
    networking.gke.io/managed-certificates: "missing-table-dev-cert"
    # Use the reserved static IP
    kubernetes.io/ingress.global-static-ip-name: "missing-table-dev-ip"
spec:
  rules:
  - host: dev.missingtable.com
    http:
      paths:
      # Backend API routes (must come before catch-all)
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: missing-table-backend
            port:
              number: 8000
      - path: /health
        pathType: Prefix
        backend:
          service:
            name: missing-table-backend
            port:
              number: 8000
      # Frontend (catch-all - must be last)
      - path: /
        pathType: Prefix
        backend:
          service:
            name: missing-table-frontend
            port:
              number: 8080
---
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: missing-table-dev-cert
  namespace: missing-table-dev
spec:
  domains:
    - dev.missingtable.com
```

**Apply the Ingress:**
```bash
kubectl apply -f k8s/ingress-dev.yaml
```

**Output:**
```
ingress.networking.k8s.io/missing-table-ingress created
managedcertificate.networking.gke.io/missing-table-dev-cert created
```

---

### Step 6: Monitor Ingress & SSL Certificate

**Check Ingress status:**
```bash
# Watch for the IP address to be assigned
kubectl get ingress missing-table-ingress -n missing-table-dev

# Should show:
# NAME                    ADDRESS        PORTS   AGE
# missing-table-ingress   34.8.149.240   80      5m
```

**Check SSL certificate status:**
```bash
# Quick status
kubectl get managedcertificate missing-table-dev-cert -n missing-table-dev

# Detailed status
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev
```

**SSL Certificate States:**
1. `Provisioning` - Certificate is being issued (15-60 minutes)
2. `Active` - Certificate is ready and attached ✅

**Monitor progress:**
```bash
# Watch certificate status update
watch kubectl get managedcertificate -n missing-table-dev
```

---

### Step 7: Update Backend CORS Configuration

**Why:** Backend needs to accept requests from the new HTTPS domain.

Edit `helm/missing-table/values-dev.yaml`:

```yaml
backend:
  env:
    extra:
      CORS_ORIGINS: "http://34.133.125.204:8080,https://dev.missingtable.com"
```

**Apply the changes:**
```bash
cd helm
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

---

### Step 8: Update Frontend to Use New Domain

**Why:** Frontend was built with hardcoded LoadBalancer IP - needs to use the domain.

Edit `frontend/Dockerfile`:

```dockerfile
# Before:
ENV VUE_APP_API_URL=http://34.135.217.253:8000

# After:
ENV VUE_APP_API_URL=https://dev.missingtable.com
```

**Rebuild the frontend:**
```bash
# Build for linux/amd64 (GKE platform)
docker buildx build \
  --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/frontend:dev \
  -f frontend/Dockerfile \
  frontend \
  --load

# Push to registry
docker push us-central1-docker.pkg.dev/missing-table/missing-table/frontend:dev

# Restart deployment to pull new image
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev

# Wait for rollout
kubectl rollout status deployment/missing-table-frontend -n missing-table-dev
```

---

### Step 9: Verify Everything Works

**Test HTTP (should work while SSL provisions):**
```bash
curl -I http://dev.missingtable.com
# Should return: HTTP/1.1 200 OK
```

**Test API endpoint:**
```bash
curl http://dev.missingtable.com/api/seasons
# Should return: JSON array of seasons
```

**Test HTTPS (once SSL is Active):**
```bash
curl -I https://dev.missingtable.com
# Should return: HTTP/2 200
```

**Test in browser:**
1. Open https://dev.missingtable.com
2. Check for the lock icon 🔒
3. Click lock → View certificate
4. Should show: Issued by Google Trust Services
5. Valid until: ~3 months from now (auto-renews)

---

## Troubleshooting

### Common Issues We Encountered

#### 1. DNS Not Propagating

**Symptoms:** `dig dev.missingtable.com` returns nothing

**Solution:**
```bash
# Check if nameservers updated
dig NS missingtable.com +short

# Should show Google nameservers
# If not, wait longer or check Namecheap settings
```

#### 2. Ingress Stuck Without IP

**Symptoms:** `kubectl get ingress` shows no ADDRESS

**Possible causes:**
- Static IP not created
- Wrong static IP name in annotation
- GKE Ingress controller not running

**Solution:**
```bash
# Verify static IP exists
gcloud compute addresses describe missing-table-dev-ip --global

# Check Ingress events
kubectl describe ingress missing-table-ingress -n missing-table-dev

# Look for error messages in Events section
```

#### 3. SSL Certificate Stuck in "Provisioning"

**Symptoms:** Certificate status stays "Provisioning" for >60 minutes

**Possible causes:**
- DNS not pointing to the load balancer IP
- Firewall blocking HTTP (port 80) - needed for validation
- Domain validation failed

**Solution:**
```bash
# Verify DNS resolves correctly
dig dev.missingtable.com +short
# Should return: 34.8.149.240

# Check certificate details
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev

# Look for Domain Status - should be "Active" not "Failed"
```

**Note:** If status is `FailedNotVisible`, this is temporary and usually resolves itself. Wait 10-15 more minutes.

#### 4. 404 Errors on API Endpoints

**Symptoms:** Frontend loads but `/api/*` returns 404

**Cause:** Ingress path rules using wrong pathType

**Solution:** Use `pathType: Prefix` not `pathType: ImplementationSpecific`

```yaml
# Wrong:
- path: /api/*
  pathType: ImplementationSpecific

# Correct:
- path: /api
  pathType: Prefix
```

#### 5. Connection Reset Errors

**Symptoms:** `curl: (56) Recv failure: Connection reset by peer`

**Cause:** Load balancer still propagating configuration changes

**Solution:** Wait 2-5 minutes after Ingress changes. GCP load balancers take time to update.

#### 6. Mixed Content Warnings

**Symptoms:** Browser console shows "Mixed Content" errors

**Cause:** Frontend using `http://` to call backend on an HTTPS site

**Solution:** Update `frontend/Dockerfile` to use HTTPS API URL:
```dockerfile
ENV VUE_APP_API_URL=https://dev.missingtable.com
```

#### 7. Docker Platform Architecture Mismatch

**Symptoms:** `no match for platform in manifest: not found`

**Cause:** Building on Mac (ARM64) for GKE (AMD64)

**Solution:** Build with explicit platform:
```bash
docker buildx build --platform linux/amd64 ...
```

---

## Verification

### Complete Verification Checklist

Run these commands to verify everything is working:

```bash
# 1. DNS Resolution
echo "=== DNS CHECK ==="
dig dev.missingtable.com +short
# Expected: 34.8.149.240

# 2. Ingress Status
echo "=== INGRESS STATUS ==="
kubectl get ingress -n missing-table-dev
# Expected: ADDRESS column shows 34.8.149.240

# 3. SSL Certificate
echo "=== SSL CERTIFICATE ==="
kubectl get managedcertificate -n missing-table-dev
# Expected: STATUS shows "Active"

# 4. HTTP Response
echo "=== HTTP TEST ==="
curl -I http://dev.missingtable.com
# Expected: HTTP/1.1 200 OK

# 5. HTTPS Response
echo "=== HTTPS TEST ==="
curl -I https://dev.missingtable.com
# Expected: HTTP/2 200

# 6. API Endpoint
echo "=== API TEST ==="
curl https://dev.missingtable.com/api/seasons
# Expected: JSON array

# 7. Backend Health
echo "=== HEALTH CHECK ==="
curl https://dev.missingtable.com/health
# Expected: {"status":"healthy",...}

# 8. SSL Certificate Details
echo "=== CERTIFICATE INFO ==="
echo | openssl s_client -servername dev.missingtable.com \
  -connect dev.missingtable.com:443 2>/dev/null | \
  openssl x509 -noout -dates
# Expected: notAfter=<date ~90 days from now>

# 9. Load Balancer Backend Health
echo "=== BACKEND HEALTH ==="
gcloud compute backend-services list --global --project=missing-table
# Expected: Shows 2 backend services (frontend + backend)
```

### Browser Verification

1. **HTTPS Works:**
   - Open: https://dev.missingtable.com
   - Look for 🔒 in address bar
   - No security warnings

2. **HTTP Redirects (optional):**
   - Open: http://dev.missingtable.com
   - Should redirect to HTTPS (if configured)

3. **API Calls Work:**
   - Open browser DevTools (F12)
   - Go to Network tab
   - Navigate through the app
   - All requests should be to `https://dev.missingtable.com`
   - No CORS errors in console

4. **Certificate Details:**
   - Click 🔒 in address bar
   - Click "Certificate"
   - Verify:
     - Issued to: dev.missingtable.com
     - Issued by: GTS CA 1D4 (Google Trust Services)
     - Valid from/to dates

---

## Cost Analysis

### Before: 2 LoadBalancers

| Component | Type | Monthly Cost |
|-----------|------|--------------|
| Frontend LB | Network LB | ~$18 |
| Backend LB | Network LB | ~$18 |
| **Total** | | **~$36** |

### After: 1 Ingress (Application LB)

| Component | Type | Monthly Cost |
|-----------|------|--------------|
| Ingress LB | Application LB | ~$18 |
| LB Capacity | 1-2 LCUs | ~$7-12 |
| **Total** | | **~$25-30** |

**Monthly Savings:** ~$6-11

### Additional Costs (Same Before/After)

- **Static IP (Global):** FREE (while in use)
- **DNS Queries:** ~$0.40/million queries (minimal for dev)
- **SSL Certificate:** FREE (Google-managed)

### GCP Load Balancer Pricing Details

**Application Load Balancer (what we're using now):**
- Forwarding rule: $0.025/hour
- Capacity units (LCUs): $0.008/hour per LCU
  - New connections/sec
  - Active connections
  - Bandwidth
  - Rule evaluations

**For a small dev app:** Typically uses 1-2 LCUs

**Learn more:** https://cloud.google.com/vpc/network-pricing#lb

---

## Production Setup

### Future: Setting up Production

When ready to deploy production, repeat this process with:

**Different values:**
- Domain: `missingtable.com` and `www.missingtable.com`
- Namespace: `missing-table-prod`
- Static IP: `missing-table-prod-ip`
- Ingress: `missing-table-prod-ingress`
- Certificate: `missing-table-prod-cert`

**DNS Records to add:**
```bash
# Root domain
gcloud dns record-sets create missingtable.com. \
  --zone=missingtable-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=<PROD_STATIC_IP>

# WWW subdomain
gcloud dns record-sets create www.missingtable.com. \
  --zone=missingtable-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=<PROD_STATIC_IP>
```

**ManagedCertificate for prod:**
```yaml
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: missing-table-prod-cert
  namespace: missing-table-prod
spec:
  domains:
    - missingtable.com
    - www.missingtable.com
```

### Dev vs Prod Comparison

| Aspect | Dev | Prod |
|--------|-----|------|
| **Domain** | dev.missingtable.com | missingtable.com<br>www.missingtable.com |
| **Namespace** | missing-table-dev | missing-table-prod |
| **Database** | Cloud Dev | Cloud Prod |
| **Load Balancer** | Shared with prod cluster | Dedicated |
| **Monitoring** | Basic | Full alerting |
| **Backups** | Optional | Required |

---

## Maintenance

### SSL Certificate Renewal

**Good news:** Nothing to do! Google automatically renews certificates.

**How it works:**
- Certificate valid for 90 days
- Google renews 30 days before expiry
- Zero downtime renewal
- No manual intervention needed

**Monitor certificate expiry:**
```bash
# Check current certificate expiration
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev | grep "Expire Time"

# Or via OpenSSL
echo | openssl s_client -servername dev.missingtable.com \
  -connect dev.missingtable.com:443 2>/dev/null | \
  openssl x509 -noout -dates
```

### DNS Management

**Adding new subdomains:**
```bash
# Example: api.missingtable.com
gcloud dns record-sets create api.missingtable.com. \
  --zone=missingtable-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=34.8.149.240
```

**Updating existing records:**
```bash
# Delete old record
gcloud dns record-sets delete dev.missingtable.com. \
  --zone=missingtable-zone \
  --type=A

# Create new record
gcloud dns record-sets create dev.missingtable.com. \
  --zone=missingtable-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=<NEW_IP>
```

### Load Balancer Monitoring

**Check backend health:**
```bash
# List backend services
gcloud compute backend-services list --global --project=missing-table

# Check frontend health
gcloud compute backend-services get-health \
  <FRONTEND_BACKEND_SERVICE_NAME> \
  --global --project=missing-table

# Check backend health
gcloud compute backend-services get-health \
  <BACKEND_BACKEND_SERVICE_NAME> \
  --global --project=missing-table
```

**Monitor load balancer metrics:**
1. Go to GCP Console → Network Services → Load Balancing
2. Click on your load balancer
3. View metrics:
   - Request rate
   - Latency
   - Error rate
   - Backend health

### Updating Ingress Configuration

**When you change the Ingress:**
```bash
# Edit the file
vim k8s/ingress-dev.yaml

# Apply changes
kubectl apply -f k8s/ingress-dev.yaml

# Wait for update (5-10 minutes)
kubectl describe ingress missing-table-ingress -n missing-table-dev

# Watch for "Sync" events
```

**Important:** Load balancer updates take 5-10 minutes to propagate.

---

## Reference

### Useful Commands

```bash
# DNS
dig dev.missingtable.com +short                    # Check DNS
dig NS missingtable.com +short                     # Check nameservers
nslookup dev.missingtable.com 8.8.8.8             # Query specific DNS server

# Kubernetes
kubectl get ingress -n missing-table-dev           # List ingress
kubectl get managedcertificate -n missing-table-dev # List certificates
kubectl describe ingress <name> -n missing-table-dev # Ingress details
kubectl logs -f deployment/<name> -n missing-table-dev # View logs

# GCP
gcloud compute addresses list --global             # List static IPs
gcloud compute forwarding-rules list --global      # List LB rules
gcloud compute backend-services list --global      # List backends
gcloud dns record-sets list --zone=missingtable-zone # List DNS records

# Testing
curl -I https://dev.missingtable.com              # Test HTTPS
curl https://dev.missingtable.com/api/seasons     # Test API
curl https://dev.missingtable.com/health          # Test health
```

### Key Files

| File | Purpose |
|------|---------|
| `k8s/ingress-dev.yaml` | Ingress and SSL certificate config |
| `helm/missing-table/values-dev.yaml` | Helm configuration for dev |
| `frontend/Dockerfile` | Frontend build with API URL |
| `docs/GKE_HTTPS_DOMAIN_SETUP.md` | This documentation |

### GCP Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| Static IP | `missing-table-dev-ip` | Load balancer IP |
| DNS Zone | `missingtable-zone` | Domain management |
| DNS Record | `dev.missingtable.com` | A record to static IP |
| Ingress | `missing-table-ingress` | Load balancer config |
| ManagedCert | `missing-table-dev-cert` | SSL certificate |
| Backend Service | `k8s1-...-frontend-...` | Frontend backend |
| Backend Service | `k8s1-...-backend-...` | API backend |
| URL Map | `k8s2-um-...` | Routing rules |
| Target Proxy | `k8s2-tp-...` | HTTP handler |
| Target Proxy | `k8s2-ts-...` | HTTPS handler |
| Forwarding Rule | `k8s2-fr-...` | HTTP forwarding |
| Forwarding Rule | `k8s2-fs-...` | HTTPS forwarding |

### Cleanup (If Needed)

**To remove everything:**
```bash
# Delete Ingress (removes LB, certs, forwarding rules)
kubectl delete ingress missing-table-ingress -n missing-table-dev
kubectl delete managedcertificate missing-table-dev-cert -n missing-table-dev

# Delete static IP
gcloud compute addresses delete missing-table-dev-ip --global

# Delete DNS records (keep zone)
gcloud dns record-sets delete dev.missingtable.com. \
  --zone=missingtable-zone \
  --type=A

# Delete DNS zone (only if completely done)
gcloud dns managed-zones delete missingtable-zone
```

**Warning:** Only run cleanup if you're sure you want to remove the domain setup!

---

## Summary

### What We Achieved

✅ **HTTPS enabled** with auto-renewing certificates
✅ **Custom domain** setup (dev.missingtable.com)
✅ **Cost savings** (~$6-11/month)
✅ **Better architecture** (single load balancer)
✅ **HTTP/2** for improved performance
✅ **Professional setup** ready for production

### Time Investment

- **Initial setup:** ~60 minutes (hands-on)
- **SSL provisioning:** ~20 minutes (automated)
- **DNS propagation:** ~15 minutes (usually faster)
- **Total:** ~90 minutes

### Ongoing Maintenance

- **SSL renewal:** Automatic, zero effort
- **DNS changes:** 5 minutes per change
- **Ingress updates:** 10 minutes including propagation

### Next Steps

1. ✅ Monitor SSL certificate auto-renewal (first one in ~60 days)
2. 📋 Plan production deployment when ready
3. 🔍 Set up monitoring/alerting for the load balancer
4. 🚀 Enjoy your professional HTTPS setup!

---

**Document Version:** 1.0
**Last Updated:** October 3, 2025
**Maintained By:** Missing Table Team
