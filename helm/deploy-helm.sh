#!/bin/bash

# Exit on any error, undefined variables, or pipe failures
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Cleanup function
cleanup() {
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}🚨 Deployment failed! Check the errors above.${NC}"
        echo -e "${BLUE}🔍 Troubleshooting tips:${NC}"
        echo "   1. Check if Kubernetes cluster is running: kubectl cluster-info"
        echo "   2. Check if Docker is running: docker version"
        echo "   3. Check if Supabase is running: supabase status"
        echo "   4. Check build dependencies in backend/: ls backend/uv.lock"
    fi
}
trap cleanup EXIT

echo "🚀 Deploying Missing Table Application using Helm"
echo "=================================================="
echo "Project root: $PROJECT_ROOT"
echo "Script dir: $SCRIPT_DIR"

# Change to project root
cd "$PROJECT_ROOT"

# Prerequisite checks
echo ""
info "🔍 PREREQUISITE CHECKS"
echo "======================"

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    error "Docker is not running. Please start Docker and try again."
fi
success "Docker is running"

# Check if Kubernetes cluster is available
if ! kubectl cluster-info >/dev/null 2>&1; then
    error "Kubernetes cluster is not accessible. Please start Rancher Desktop/k3s and ensure Kubernetes is enabled."
fi
success "Kubernetes cluster is accessible"

# Check if Helm is installed
if ! command -v helm >/dev/null 2>&1; then
    error "Helm is not installed. Please install Helm: brew install helm"
fi
success "Helm is available"

# Check if Supabase is running (optional but recommended)
if command -v supabase >/dev/null 2>&1; then
    if supabase status >/dev/null 2>&1; then
        success "Supabase is running locally"
    else
        warning "Supabase is not running. Start with: supabase start"
        warning "Database connections may fail without local Supabase"
    fi
else
    warning "Supabase CLI not found. Database connections may fail."
fi

# Check if required files exist
if [[ ! -f "backend/Dockerfile.dev" ]]; then
    error "Backend Dockerfile not found: backend/Dockerfile.dev"
fi

if [[ ! -f "frontend/Dockerfile.dev" ]]; then
    error "Frontend Dockerfile not found: frontend/Dockerfile.dev"
fi

if [[ ! -f "backend/uv.lock" ]]; then
    warning "uv.lock not found. Generating it now..."
    cd backend && uv lock || error "Failed to generate uv.lock"
    cd ..
    success "Generated uv.lock file"
fi

if [[ ! -f "helm/missing-table/values-dev.yaml" ]]; then
    error "Helm values file not found: helm/missing-table/values-dev.yaml"
fi

success "All prerequisite checks passed"

# Build Docker images first (they need to be available locally for Kubernetes)
echo ""
echo "🚀 BUILDING CONTAINER IMAGES"
echo "============================"
echo "Building fresh Docker images with latest code changes..."
echo ""

echo "📦 Building BACKEND container..."
echo "   Command: docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/"
if ! docker build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/; then
    error "Failed to build backend container. Check Docker logs above."
fi
success "Backend container built successfully"

echo ""
echo "📦 Building FRONTEND container..." 
echo "   Command: docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/"
if ! docker build -t missing-table-frontend:latest -f frontend/Dockerfile.dev frontend/; then
    error "Failed to build frontend container. Check Docker logs above."
fi
success "Frontend container built successfully"

echo ""
echo "🔍 Verifying container images are available..."

# Check backend image exists
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^missing-table-backend:latest$"; then
    error "Backend image 'missing-table-backend:latest' not found after build. Available images:\n$(docker images | grep missing-table || echo 'No missing-table images found')"
fi

# Check frontend image exists  
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^missing-table-frontend:latest$"; then
    error "Frontend image 'missing-table-frontend:latest' not found after build. Available images:\n$(docker images | grep missing-table || echo 'No missing-table images found')"
fi

echo "Built images:"
docker images | grep missing-table | head -2
success "All container images verified"

echo ""
echo "🚀 DEPLOYING TO KUBERNETES"
echo "=========================="
echo "Using Helm to deploy containers to Kubernetes cluster..."
echo ""

# Check for orphaned namespace (namespace exists but no Helm release)
if kubectl get namespace missing-table >/dev/null 2>&1 && ! helm list -n missing-table | grep -q "missing-table"; then
    warning "🗑️  Found orphaned namespace 'missing-table' (no Helm release). Deleting it first..."
    kubectl delete namespace missing-table || warning "Could not delete namespace, continuing anyway..."
    # Wait for namespace to be fully deleted
    while kubectl get namespace missing-table >/dev/null 2>&1; do
        echo "   Waiting for namespace deletion..."
        sleep 2
    done
    success "Orphaned namespace cleaned up"
fi

# Check if release already exists and its status
if helm list -n missing-table | grep -q "missing-table"; then
    RELEASE_STATUS=$(helm list -n missing-table | grep missing-table | awk '{print $8}')
    
    if [[ "$RELEASE_STATUS" == "failed" ]]; then
        warning "🔄 Found failed Helm release (status: $RELEASE_STATUS). Uninstalling first..."
        if ! helm uninstall missing-table -n missing-table; then
            error "Failed to uninstall failed release"
        fi
        
        # Also delete the namespace to avoid ownership metadata issues
        warning "🗑️  Deleting namespace to avoid ownership metadata conflicts..."
        if kubectl get namespace missing-table >/dev/null 2>&1; then
            kubectl delete namespace missing-table || warning "Could not delete namespace, continuing anyway..."
            # Wait for namespace to be fully deleted
            while kubectl get namespace missing-table >/dev/null 2>&1; do
                echo "   Waiting for namespace deletion..."
                sleep 2
            done
        fi
        success "Failed release and namespace cleaned up"
        
        info "🆕 Installing fresh Helm release..."
        if ! helm install missing-table ./helm/missing-table \
            --namespace missing-table \
            --create-namespace \
            --values ./helm/missing-table/values-dev.yaml \
            --wait \
            --timeout 300s; then
            error "Helm installation failed. Check the error messages above."
        fi
        success "Helm release installed successfully"
    else
        info "📈 Upgrading existing Helm release (status: $RELEASE_STATUS)..."
        if ! helm upgrade missing-table ./helm/missing-table \
            --namespace missing-table \
            --values ./helm/missing-table/values-dev.yaml \
            --wait \
            --timeout 300s; then
            error "Helm upgrade failed. Check the error messages above."
        fi
        success "Helm release upgraded successfully"
    fi
else
    info "🆕 Creating namespace with proper Helm labels..."
    # Create namespace manually with proper Helm ownership labels
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: missing-table
  labels:
    name: missing-table
    app.kubernetes.io/managed-by: Helm
  annotations:
    meta.helm.sh/release-name: missing-table
    meta.helm.sh/release-namespace: missing-table
EOF
    
    info "🆕 Installing new Helm release..."
    if ! helm install missing-table ./helm/missing-table \
        --namespace missing-table \
        --values ./helm/missing-table/values-dev.yaml \
        --wait \
        --timeout 300s; then
        error "Helm installation failed. Check the error messages above."
    fi
    success "Helm release installed successfully"
fi

echo ""
info "🔍 VERIFYING DEPLOYMENT"
echo "======================"

# Wait a moment for services to be ready
sleep 5

# Check services
echo ""
info "📋 Checking service information..."
if ! kubectl get services -n missing-table; then
    error "Failed to get service information"
fi

# Check pods
echo ""
info "📊 Checking pod status..."
if ! kubectl get pods -n missing-table; then
    error "Failed to get pod information"
fi

# Check if pods are running
echo ""
info "⚙️ Checking pod health..."
FAILED_PODS=$(kubectl get pods -n missing-table --no-headers | grep -v Running | grep -v Completed || true)
if [[ -n "$FAILED_PODS" ]]; then
    warning "Some pods are not in Running state:"
    echo "$FAILED_PODS"
    warning "Check logs with: kubectl logs -f deployment/missing-table-backend -n missing-table"
    warning "Check logs with: kubectl logs -f deployment/missing-table-frontend -n missing-table"
else
    success "All pods are running successfully"
fi

success "🎉 Deployment completed successfully!"

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