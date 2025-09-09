#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying Missing Table Application to Kubernetes (Rancher Desktop)"
echo "=================================================================="
echo "Project root: $PROJECT_ROOT"
echo "Script dir: $SCRIPT_DIR"

# Change to project root
cd "$PROJECT_ROOT"

# Build Docker images first (they need to be available locally for Kubernetes)
echo "📦 Building Docker images..."
docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/
docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/

echo "🏗️ Creating namespace and applying manifests..."

# Apply namespace first
kubectl apply -f k8s/namespace.yaml

# Apply Redis deployment
echo "📊 Deploying Redis..."
kubectl apply -f k8s/redis-deployment.yaml

# Apply backend deployment
echo "⚙️ Deploying Backend API..."
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service-lb.yaml

# Apply frontend deployment
echo "🌐 Deploying Frontend..."
kubectl apply -f k8s/frontend-deployment.yaml

echo "⏳ Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n missing-table
kubectl wait --for=condition=available --timeout=300s deployment/backend -n missing-table
kubectl wait --for=condition=available --timeout=300s deployment/frontend -n missing-table

echo "🎉 Deployment complete!"
echo ""
echo "📋 Getting service information..."
kubectl get services -n missing-table

echo ""
echo "🔗 Access your application:"
echo "Frontend: http://localhost:8080 (once LoadBalancer assigns external IP)"
echo "Backend API: http://localhost:8000 (once LoadBalancer assigns external IP)"
echo ""
echo "📊 Check deployment status:"
echo "kubectl get pods -n missing-table"
echo "kubectl get services -n missing-table"
echo ""
echo "🐛 View logs:"
echo "kubectl logs -f deployment/backend -n missing-table"
echo "kubectl logs -f deployment/frontend -n missing-table"