#!/bin/bash

# Build script for Missing Table Docker images
# This script builds both backend and frontend Docker images with latest code
# and tags them for use in Kubernetes

set -e  # Exit on any error

# Get the directory where this script is located and change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🚀 Building Missing Table Docker Images"
echo "======================================"
echo "Script directory: $SCRIPT_DIR"

# Change to project root
cd "$SCRIPT_DIR"

# Get current timestamp for unique tagging
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
echo "Timestamp: $TIMESTAMP"
echo "Working directory: $(pwd)"

# Verify files exist
echo ""
echo "🔍 Verifying Dockerfile locations..."
if [[ ! -f "backend/Dockerfile.dev" ]]; then
    echo "❌ backend/Dockerfile.dev not found"
    exit 1
fi
if [[ ! -f "frontend/Dockerfile.dev" ]]; then
    echo "❌ frontend/Dockerfile.dev not found"
    exit 1
fi
echo "✅ Dockerfiles found"

# Build backend image
echo ""
echo "📦 Building backend image..."
echo "Command: nerdctl --namespace k8s.io build --no-cache -t missing-table-backend:latest -f backend/Dockerfile.dev backend/"
nerdctl --namespace k8s.io build --no-cache -t missing-table-backend:latest -f backend/Dockerfile.dev backend/

# Tag with timestamp for versioning
nerdctl --namespace k8s.io tag missing-table-backend:latest missing-table-backend:$TIMESTAMP

# Build frontend image  
echo ""
echo "📦 Building frontend image..."
echo "Command: nerdctl --namespace k8s.io build --no-cache -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/"
nerdctl --namespace k8s.io build --no-cache -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/

# Tag with timestamp for versioning
nerdctl --namespace k8s.io tag missing-table-frontend:latest missing-table-frontend:$TIMESTAMP

echo ""
echo "🔍 Verifying images..."
nerdctl --namespace k8s.io images | grep missing-table

echo ""
echo "✅ Build complete!"
echo ""
echo "📋 Available images:"
echo "- missing-table-backend:latest"
echo "- missing-table-backend:$TIMESTAMP"
echo "- missing-table-frontend:latest" 
echo "- missing-table-frontend:$TIMESTAMP"
echo ""
echo "🚀 To deploy the new images to Kubernetes:"
echo "kubectl rollout restart deployment/missing-table-backend -n missing-table"
echo "kubectl rollout restart deployment/missing-table-frontend -n missing-table"
echo ""
echo "🔄 Or redeploy with Helm:"
echo "./helm/deploy-helm.sh"