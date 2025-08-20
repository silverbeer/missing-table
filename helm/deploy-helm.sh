#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying Missing Table Application using Helm"
echo "=================================================="
echo "Project root: $PROJECT_ROOT"
echo "Script dir: $SCRIPT_DIR"

# Change to project root
cd "$PROJECT_ROOT"

# Build Docker images first (they need to be available locally for Kubernetes)
echo ""
echo "🚀 BUILDING CONTAINER IMAGES"
echo "============================"
echo "Building fresh Docker images with latest code changes..."
echo ""

echo "📦 Building BACKEND container..."
echo "   Command: docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/"
docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/

echo ""
echo "📦 Building FRONTEND container..." 
echo "   Command: docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/"
docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/

echo ""
echo "🔍 Verifying container images are available..."
docker images | grep missing-table

echo ""
echo "🚀 DEPLOYING TO KUBERNETES"
echo "=========================="
echo "Using Helm to deploy containers to Kubernetes cluster..."
echo ""

# Check if release already exists
if helm list -n missing-table | grep -q "missing-table"; then
    echo "📈 Upgrading existing Helm release..."
    helm upgrade missing-table ./helm/missing-table \
        --namespace missing-table \
        --values ./helm/missing-table/values-dev.yaml \
        --wait \
        --timeout 300s
else
    echo "🆕 Installing new Helm release..."
    helm install missing-table ./helm/missing-table \
        --namespace missing-table \
        --create-namespace \
        --values ./helm/missing-table/values-dev.yaml \
        --wait \
        --timeout 300s
fi

echo "🎉 Deployment complete!"
echo ""
echo "📋 Getting service information..."
kubectl get services -n missing-table

echo ""
echo "📊 Getting pod information..."
kubectl get pods -n missing-table

echo ""
echo "🔗 Access your application:"
echo "Frontend: http://localhost:8080 (once LoadBalancer assigns external IP)"
echo "Backend API: http://localhost:8000 (once LoadBalancer assigns external IP)"

echo ""
echo "📊 Useful commands:"
echo "helm status missing-table -n missing-table"
echo "helm history missing-table -n missing-table"
echo "kubectl get all -n missing-table"
echo "kubectl logs -f deployment/missing-table-backend -n missing-table"
echo "kubectl logs -f deployment/missing-table-frontend -n missing-table"