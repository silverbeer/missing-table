# Missing Table - Kubernetes Deployment for Rancher Desktop

This directory contains Kubernetes manifests to deploy the Missing Table application in Rancher Desktop's local Kubernetes cluster.

## Prerequisites

1. **Rancher Desktop** installed with Kubernetes enabled
2. **kubectl** configured to talk to your Rancher Desktop cluster
3. **Supabase** running locally (via `npx supabase start`)

## Quick Start

### 1. Deploy the Application

```bash
# Run from anywhere - the script will find the correct paths
./k8s/deploy.sh
```

Or if you're in the k8s directory:
```bash
cd k8s
./deploy.sh
```

This script will:
- Build the Docker images locally
- Create the `missing-table` namespace
- Deploy Redis, Backend, and Frontend
- Set up LoadBalancer services for external access

### 2. Check Deployment Status

```bash
# Check all pods
kubectl get pods -n missing-table

# Check services and their external IPs
kubectl get services -n missing-table

# Check detailed pod information
kubectl describe pods -n missing-table
```

### 3. Access the Application

Once deployed, the LoadBalancer services will expose:
- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000

### 4. View Logs

```bash
# Backend logs
kubectl logs -f deployment/backend -n missing-table

# Frontend logs
kubectl logs -f deployment/frontend -n missing-table

# Redis logs
kubectl logs -f deployment/redis -n missing-table
```

## Architecture

The Kubernetes deployment includes:

- **Namespace**: `missing-table` with resource quotas and limits
- **Redis**: Single replica with persistent storage (1Gi PVC)
- **Backend**: FastAPI application (simple version without security modules)
- **Frontend**: Vue.js application
- **Services**: LoadBalancer services for external access
- **Persistent Storage**: Redis data persistence

## Configuration

### Environment Variables

**Backend**:
- `DATABASE_URL`: Points to external Supabase PostgreSQL
- `REDIS_URL`: Points to Redis service within cluster
- `DISABLE_LOGFIRE`: Disabled for local development

**Frontend**:
- `VUE_APP_SUPABASE_URL`: Points to local Supabase instance
- `VUE_APP_API_URL`: Points to backend service

### Resource Limits

Each component has defined resource requests and limits:
- **Redis**: 100m CPU / 128Mi RAM (request), 500m CPU / 512Mi RAM (limit)
- **Backend**: 200m CPU / 256Mi RAM (request), 1000m CPU / 1Gi RAM (limit)  
- **Frontend**: 100m CPU / 128Mi RAM (request), 500m CPU / 512Mi RAM (limit)

## Troubleshooting

### Images Not Found
If you get "ImagePullBackOff" errors, the Docker images need to be built locally:
```bash
docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/
docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/
```

### Services Not Accessible
Check if LoadBalancer services have external IPs assigned:
```bash
kubectl get services -n missing-table
```

In Rancher Desktop, LoadBalancer services typically get localhost IPs automatically.

### Database Connection Issues
Ensure Supabase is running:
```bash
npx supabase status
```

### Pod Crashes
Check pod logs for detailed error information:
```bash
kubectl describe pod <pod-name> -n missing-table
kubectl logs <pod-name> -n missing-table
```

## Cleanup

To remove the entire deployment:

```bash
./cleanup.sh
```

This will delete all resources in the `missing-table` namespace.

## Advanced Operations

### Scaling

Scale deployments up or down:
```bash
kubectl scale deployment backend --replicas=2 -n missing-table
kubectl scale deployment frontend --replicas=3 -n missing-table
```

### Port Forwarding

Forward ports directly to pods for debugging:
```bash
kubectl port-forward deployment/backend 8000:8000 -n missing-table
kubectl port-forward deployment/frontend 8080:8080 -n missing-table
```

### Exec into Pods

Get shell access to running pods:
```bash
kubectl exec -it deployment/backend -n missing-table -- /bin/bash
kubectl exec -it deployment/redis -n missing-table -- /bin/sh
```

## Files Overview

- `namespace.yaml` - Namespace with resource quotas and limits
- `redis-deployment.yaml` - Redis cache deployment and service
- `backend-deployment.yaml` - Backend API deployment and internal service
- `backend-service-lb.yaml` - Backend LoadBalancer for external access
- `frontend-deployment.yaml` - Frontend web app deployment and LoadBalancer service
- `deploy.sh` - Automated deployment script
- `cleanup.sh` - Cleanup script
- `README.md` - This documentation