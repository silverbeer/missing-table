# GKE Cluster Shutdown - 2025-12-07

## Summary

The GKE Autopilot cluster `missing-table-dev` was deleted on 2025-12-07 to save costs.

## What Was Deleted

| Resource | Details |
|----------|---------|
| **GKE Cluster** | `missing-table-dev` in `us-central1` |
| **Namespaces** | cert-manager, ingress-nginx, missing-table-dev, match-scraper, monitoring |
| **Deployments** | missing-table-backend, missing-table-frontend |
| **Ingress** | nginx ingress at `34.173.92.110` |
| **Certificates** | 2 Let's Encrypt certificates (dev-missingtable-tls, missing-table-tls) |
| **Helm Release** | `missing-table` revision 135 |

## What Was NOT Deleted (Still Exists)

| Resource | Details | Monthly Cost |
|----------|---------|--------------|
| **Supabase Database** | Cloud-hosted, separate service | Varies |
| **Cloud DNS Zone** | `missingtable-zone` with A records | ~$0.20/month |
| **GCP Project** | `missing-table` | $0 |

**Note:** Artifact Registry repository was also deleted on 2025-12-07 to save an additional ~$1.75/month. Docker images will need to be rebuilt when restarting.

## DNS Records (Pointing to Deleted IP)

These DNS records still exist but point to the now-deleted load balancer IP `34.173.92.110`:

```
missingtable.com.      A    34.173.92.110
dev.missingtable.com.  A    34.173.92.110
www.missingtable.com.  A    34.173.92.110
```

The domains will NOT resolve until a new cluster is created and DNS is updated.

## Estimated Monthly Savings

| Before | After | Savings |
|--------|-------|---------|
| ~$40/month | ~$0.20/month | ~$40/month |

## How to Restart

When ready to bring the cluster back online:

### 1. Recreate Artifact Registry

```bash
gcloud artifacts repositories create missing-table \
  --repository-format=docker \
  --location=us-central1 \
  --project=missing-table \
  --description="Missing Table application images"
```

### 2. Create New GKE Autopilot Cluster

```bash
gcloud container clusters create-auto missing-table-dev \
  --region us-central1 \
  --project missing-table
```

### 4. Get Cluster Credentials

```bash
gcloud container clusters get-credentials missing-table-dev \
  --region us-central1 \
  --project missing-table
```

### 5. Install Nginx Ingress Controller

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer
```

### 6. Install Cert-Manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true
```

### 7. Get New Load Balancer IP

```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### 8. Update DNS Records

```bash
NEW_IP="<new-load-balancer-ip>"

# Update A records to new IP
gcloud dns record-sets update missingtable.com. \
  --type=A --ttl=300 --rrdatas="$NEW_IP" \
  --zone=missingtable-zone --project=missing-table

gcloud dns record-sets update dev.missingtable.com. \
  --type=A --ttl=300 --rrdatas="$NEW_IP" \
  --zone=missingtable-zone --project=missing-table

gcloud dns record-sets update www.missingtable.com. \
  --type=A --ttl=300 --rrdatas="$NEW_IP" \
  --zone=missingtable-zone --project=missing-table
```

### 9. Build and Push Docker Images

```bash
# Build and push backend
./build-and-push.sh backend dev

# Build and push frontend
./build-and-push.sh frontend dev
```

### 10. Deploy Application

```bash
# Create namespace
kubectl create namespace missing-table-dev

# Deploy with Helm (ensure values-dev.yaml has secrets)
cd helm
helm upgrade --install missing-table ./missing-table \
  --namespace missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

### 11. Verify Deployment

```bash
# Check pods
kubectl get pods -n missing-table-dev

# Check ingress
kubectl get ingress -n missing-table-dev

# Check certificates
kubectl get certificates -n missing-table-dev

# Test endpoints
curl -I https://dev.missingtable.com/health
curl -I https://missingtable.com/health
```

## Local Development Still Works

Local development with `./missing-table.sh` continues to work:

```bash
# Start local development
./switch-env.sh local
cd supabase-local && npx supabase start
./missing-table.sh dev

# Or use cloud Supabase for dev data
./switch-env.sh dev
./missing-table.sh dev
```

## Related Documentation

- [Deployment Guide](../05-deployment/README.md)
- [Nginx Ingress Architecture](../05-deployment/nginx-ingress-architecture.md)
- [Production Runbook](../05-deployment/production-runbook.md)
