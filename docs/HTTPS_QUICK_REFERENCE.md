# HTTPS & Domain Setup - Quick Reference

**Quick access to common commands and procedures.**

For full documentation, see: [GKE_HTTPS_DOMAIN_SETUP.md](./GKE_HTTPS_DOMAIN_SETUP.md)

---

## 🚀 Quick Start (New Environment)

```bash
# 1. Reserve static IP
gcloud compute addresses create <env>-ip --global --project=missing-table
IP=$(gcloud compute addresses describe <env>-ip --global --format="get(address)")

# 2. Add DNS record
gcloud dns record-sets create <subdomain>.missingtable.com. \
  --zone=missingtable-zone --type=A --ttl=300 --rrdatas=$IP

# 3. Apply Ingress
kubectl apply -f k8s/ingress-<env>.yaml

# 4. Wait for SSL (15-60 min)
watch kubectl get managedcertificate -n missing-table-<env>
```

---

## 🔍 Status Checks

```bash
# DNS Resolution
dig dev.missingtable.com +short

# Ingress Status
kubectl get ingress -n missing-table-dev

# SSL Certificate Status
kubectl get managedcertificate -n missing-table-dev
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev

# Load Balancer Health
gcloud compute backend-services list --global
gcloud compute backend-services get-health <SERVICE_NAME> --global

# Quick Test All
curl -I https://dev.missingtable.com
curl https://dev.missingtable.com/api/seasons
curl https://dev.missingtable.com/health
```

---

## 🔧 Common Operations

### Update DNS Record

```bash
# Delete old
gcloud dns record-sets delete <domain>. --zone=missingtable-zone --type=A

# Create new
gcloud dns record-sets create <domain>. --zone=missingtable-zone \
  --type=A --ttl=300 --rrdatas=<NEW_IP>
```

### Rebuild & Deploy Frontend

```bash
# 1. Update build configuration (if needed)
vim frontend/build.env  # Edit VUE_APP_API_URL or other settings

# 2. Build and push (using script - recommended)
./scripts/build-and-push.sh --env dev --frontend-only

# OR manual build:
cd frontend && source build.env
docker buildx build --platform linux/amd64 \
  --build-arg VUE_APP_API_URL="$VUE_APP_API_URL" \
  --build-arg VUE_APP_SUPABASE_URL="$VUE_APP_SUPABASE_URL" \
  --build-arg VUE_APP_SUPABASE_ANON_KEY="$VUE_APP_SUPABASE_ANON_KEY" \
  --build-arg VUE_APP_DISABLE_SECURITY="$VUE_APP_DISABLE_SECURITY" \
  -t us-central1-docker.pkg.dev/missing-table/missing-table/frontend:dev \
  -f Dockerfile . --load
docker push us-central1-docker.pkg.dev/missing-table/missing-table/frontend:dev

# 3. Restart
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
kubectl rollout status deployment/missing-table-frontend -n missing-table-dev
```

### Update Ingress

```bash
# 1. Edit
vim k8s/ingress-dev.yaml

# 2. Apply
kubectl apply -f k8s/ingress-dev.yaml

# 3. Wait 5-10 minutes for LB to update
kubectl describe ingress missing-table-ingress -n missing-table-dev
```

### Update Backend CORS

```bash
# 1. Edit values
vim helm/missing-table/values-dev.yaml

# 2. Upgrade
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

---

## 🐛 Troubleshooting

### SSL Certificate Stuck "Provisioning"

```bash
# Check DNS is correct
dig dev.missingtable.com +short  # Should return load balancer IP

# Check certificate details
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev

# Look for:
# - Domain Status: Should say "Provisioning" or "Active", not "Failed"
# - If "FailedNotVisible": Wait 15 more minutes, usually temporary
```

### "Failed to fetch" errors in frontend

**Problem:** Frontend using wrong API URL

**Solution:**
```bash
# Check what URL is compiled in
curl -s https://dev.missingtable.com/js/index.*.js | grep -o 'https://[^"]*'

# Should show: https://dev.missingtable.com
# If shows old IP: Rebuild frontend with correct VUE_APP_API_URL
```

### 404 on /api endpoints

**Problem:** Ingress path routing not working

**Fix:** Make sure `pathType: Prefix` (not `ImplementationSpecific`)

```yaml
paths:
- path: /api      # No trailing /*
  pathType: Prefix  # Must be Prefix
```

### Connection reset errors

**Problem:** Load balancer still updating

**Solution:** Wait 2-5 minutes after Ingress changes

---

## 📊 Monitoring

### SSL Certificate Expiry

```bash
# Check expiry date
kubectl describe managedcertificate missing-table-dev-cert -n missing-table-dev | grep "Expire Time"

# Via OpenSSL
echo | openssl s_client -servername dev.missingtable.com \
  -connect dev.missingtable.com:443 2>/dev/null | \
  openssl x509 -noout -dates
```

### Load Balancer Metrics

1. Go to: https://console.cloud.google.com/net-services/loadbalancing/list/loadBalancers
2. Click on your load balancer
3. View: Request rate, Latency, Error rate, Backend health

### Application Logs

```bash
# Frontend
kubectl logs -f deployment/missing-table-frontend -n missing-table-dev

# Backend
kubectl logs -f deployment/missing-table-backend -n missing-table-dev

# Ingress controller
kubectl logs -f deployment/ingress-gce -n kube-system
```

---

## 📁 Key Files

```
missing-table/
├── k8s/
│   └── ingress-dev.yaml          # Ingress + SSL config
├── helm/missing-table/
│   ├── values-dev.yaml            # Backend secrets (gitignored)
│   └── values-dev.yaml.example   # Template
├── frontend/
│   ├── Dockerfile                 # Frontend build config (no hardcoded values)
│   ├── build.env                  # Frontend build vars (gitignored)
│   └── build.env.example          # Template
├── scripts/
│   └── build-and-push.sh         # Automated build script
└── docs/
    ├── GKE_HTTPS_DOMAIN_SETUP.md # Full documentation
    ├── HTTPS_QUICK_REFERENCE.md  # This file
    └── SECRET_MANAGEMENT.md      # Secret management guide
```

---

## 🔗 URLs & Resources

### Dev Environment

- **Frontend:** https://dev.missingtable.com
- **Backend API:** https://dev.missingtable.com/api
- **Health Check:** https://dev.missingtable.com/health

### GCP Console Links

- **Load Balancers:** https://console.cloud.google.com/net-services/loadbalancing
- **Cloud DNS:** https://console.cloud.google.com/net-services/dns/zones
- **Static IPs:** https://console.cloud.google.com/networking/addresses
- **GKE Cluster:** https://console.cloud.google.com/kubernetes/clusters

### External Links

- **Domain (Namecheap):** https://ap.www.namecheap.com/domains/list
- **SSL Cert Check:** https://www.sslshopper.com/ssl-checker.html

---

## 💰 Cost Summary

| Component | Monthly Cost |
|-----------|--------------|
| Application Load Balancer | ~$18 |
| LB Capacity (1-2 LCUs) | ~$7-12 |
| Static IP (in use) | FREE |
| Cloud DNS queries | ~$0.40/million |
| SSL Certificate | FREE |
| **Total** | **~$25-30/mo** |

**Previous cost (2 Network LBs):** ~$36/mo
**Savings:** ~$6-11/mo

---

## 🎯 Production Checklist

When setting up production:

- [ ] Create new static IP: `missing-table-prod-ip`
- [ ] Add DNS records for:
  - [ ] `missingtable.com`
  - [ ] `www.missingtable.com`
- [ ] Create namespace: `missing-table-prod`
- [ ] Create ingress: `k8s/ingress-prod.yaml`
- [ ] Update certificate domains:
  ```yaml
  domains:
    - missingtable.com
    - www.missingtable.com
  ```
- [ ] Update frontend Dockerfile with prod API URL
- [ ] Update backend CORS for prod domain
- [ ] Set up monitoring/alerting
- [ ] Configure backups
- [ ] Test everything!

---

## 📞 Getting Help

**If something breaks:**

1. Check status: `kubectl get ingress,managedcertificate -n missing-table-dev`
2. Check events: `kubectl describe ingress missing-table-ingress -n missing-table-dev`
3. Check logs: `kubectl logs -f deployment/<name> -n missing-table-dev`
4. Review full docs: [GKE_HTTPS_DOMAIN_SETUP.md](./GKE_HTTPS_DOMAIN_SETUP.md)

**Common wait times:**
- DNS propagation: 5-60 minutes
- SSL certificate: 15-60 minutes
- Load balancer updates: 5-10 minutes

---

**Last Updated:** October 3, 2025
