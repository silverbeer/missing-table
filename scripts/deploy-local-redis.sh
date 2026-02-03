#!/bin/bash
##############################################################################
# Deploy Redis to Local K3s (Rancher Desktop)
##############################################################################
# Deploys Redis for local development caching.
#
# Usage:
#   ./scripts/deploy-local-redis.sh          # Deploy Redis
#   ./scripts/deploy-local-redis.sh --delete # Remove Redis deployment
#
# Prerequisites:
#   - Rancher Desktop running with Kubernetes enabled
#   - kubectl configured with rancher-desktop context
#   - helm installed
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="missing-table"
RELEASE_NAME="missing-table"
K8S_CONTEXT="rancher-desktop"

# Parse arguments
DELETE_MODE=false
for arg in "$@"; do
    case $arg in
        --delete)
            DELETE_MODE=true
            ;;
        --help|-h)
            echo "Usage: $0 [--delete]"
            echo ""
            echo "Options:"
            echo "  --delete    Remove Redis deployment from k3s"
            echo "  --help      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Local Redis Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Check prerequisites
##############################################################################
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl not found. Please install kubectl.${NC}"
    exit 1
fi

if ! command -v helm &> /dev/null; then
    echo -e "${RED}helm not found. Please install helm: brew install helm${NC}"
    exit 1
fi

# Check if rancher-desktop context exists
if ! kubectl config get-contexts "$K8S_CONTEXT" &> /dev/null; then
    echo -e "${RED}Context '$K8S_CONTEXT' not found.${NC}"
    echo -e "${YELLOW}Is Rancher Desktop running with Kubernetes enabled?${NC}"
    exit 1
fi

# Check if cluster is accessible
if ! kubectl --context="$K8S_CONTEXT" cluster-info &> /dev/null; then
    echo -e "${RED}Cannot connect to cluster. Is Rancher Desktop running?${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

##############################################################################
# Delete mode
##############################################################################
if [ "$DELETE_MODE" = true ]; then
    echo -e "${YELLOW}Removing Redis deployment...${NC}"

    # Uninstall helm release
    if helm --kube-context="$K8S_CONTEXT" list -n "$NAMESPACE" | grep -q "$RELEASE_NAME"; then
        helm --kube-context="$K8S_CONTEXT" uninstall "$RELEASE_NAME" -n "$NAMESPACE"
        echo -e "${GREEN}Helm release uninstalled${NC}"
    else
        echo -e "${YELLOW}Helm release not found, skipping${NC}"
    fi

    # Delete PVC (optional - keeps data if not deleted)
    read -p "Delete persistent volume claim (loses cached data)? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl --context="$K8S_CONTEXT" delete pvc -n "$NAMESPACE" -l app.kubernetes.io/component=redis --ignore-not-found
        echo -e "${GREEN}PVC deleted${NC}"
    fi

    echo -e "${GREEN}Redis deployment removed${NC}"
    exit 0
fi

##############################################################################
# Deploy Redis
##############################################################################
echo -e "${BLUE}Deploying Redis to local K3s...${NC}"

# Create namespace if it doesn't exist
kubectl --context="$K8S_CONTEXT" create namespace "$NAMESPACE" --dry-run=client -o yaml | \
    kubectl --context="$K8S_CONTEXT" apply -f -

# Deploy using helm
# Only enable Redis, disable other components
helm --kube-context="$K8S_CONTEXT" upgrade --install "$RELEASE_NAME" "$PROJECT_ROOT/helm/missing-table" \
    --namespace "$NAMESPACE" \
    --set redis.enabled=true \
    --set redis.persistence.storageClass=local-path \
    --set backend.replicaCount=0 \
    --set frontend.replicaCount=0 \
    --set celeryWorker.enabled=false \
    --wait \
    --timeout 2m

echo -e "${GREEN}Helm deployment complete${NC}"
echo ""

##############################################################################
# Wait for Redis to be ready
##############################################################################
echo -e "${YELLOW}Waiting for Redis pod to be ready...${NC}"

kubectl --context="$K8S_CONTEXT" wait --for=condition=ready pod \
    -l app.kubernetes.io/component=redis \
    -n "$NAMESPACE" \
    --timeout=120s

echo -e "${GREEN}Redis pod is ready${NC}"
echo ""

##############################################################################
# Verify deployment
##############################################################################
echo -e "${BLUE}Verifying Redis deployment...${NC}"

# Test Redis connection
if kubectl --context="$K8S_CONTEXT" exec -n "$NAMESPACE" svc/missing-table-redis -- redis-cli PING | grep -q "PONG"; then
    echo -e "${GREEN}Redis is responding to PING${NC}"
else
    echo -e "${RED}Redis is not responding${NC}"
    exit 1
fi

echo ""

##############################################################################
# Summary
##############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Redis Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Redis is running in:${NC}"
echo "  Namespace: $NAMESPACE"
echo "  Service:   missing-table-redis"
echo "  Port:      6379"
echo ""
echo -e "${BLUE}To access Redis from your local machine:${NC}"
echo "  kubectl port-forward -n $NAMESPACE svc/missing-table-redis 6379:6379"
echo ""
echo -e "${BLUE}Or use the service script which handles port-forward automatically:${NC}"
echo "  ./missing-table.sh start"
echo ""
echo -e "${BLUE}Useful Redis commands:${NC}"
echo "  # Test connection"
echo "  kubectl exec -n $NAMESPACE svc/missing-table-redis -- redis-cli PING"
echo ""
echo "  # Flush all cache"
echo "  kubectl exec -n $NAMESPACE svc/missing-table-redis -- redis-cli FLUSHALL"
echo ""
echo "  # Check cached keys"
echo "  kubectl exec -n $NAMESPACE svc/missing-table-redis -- redis-cli KEYS '*'"
echo ""
