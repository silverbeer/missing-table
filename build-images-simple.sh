#!/bin/bash

# Simple build script for Missing Table Docker images
# Run this from the project root directory

set -e

echo "🚀 Building Missing Table Docker Images"
echo "======================================"
echo "Working from: $(pwd)"

# Verify we're in the right directory
if [[ ! -f "backend/Dockerfile.dev" ]] || [[ ! -f "frontend/Dockerfile.dev" ]]; then
    echo "❌ Please run this script from the project root directory"
    echo "Current directory: $(pwd)"
    echo "Expected files: backend/Dockerfile.dev, frontend/Dockerfile.dev"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
echo "Timestamp: $TIMESTAMP"

# Build backend
echo ""
echo "📦 Building backend image..."
if nerdctl --namespace k8s.io build --no-cache -t missing-table-backend:latest -f backend/Dockerfile.dev backend/; then
    nerdctl --namespace k8s.io tag missing-table-backend:latest missing-table-backend:$TIMESTAMP
    echo "✅ Backend image built successfully"
else
    echo "❌ Backend image build failed"
    exit 1
fi

# Build frontend  
echo ""
echo "📦 Building frontend image..."
if nerdctl --namespace k8s.io build --no-cache -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/; then
    nerdctl --namespace k8s.io tag missing-table-frontend:latest missing-table-frontend:$TIMESTAMP
    echo "✅ Frontend image built successfully"
else
    echo "❌ Frontend image build failed"
    exit 1
fi

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
echo "🚀 To deploy to Kubernetes:"
echo "kubectl rollout restart deployment/missing-table-backend -n missing-table"
echo "kubectl rollout restart deployment/missing-table-frontend -n missing-table"