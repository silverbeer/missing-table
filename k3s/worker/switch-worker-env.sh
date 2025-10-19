#!/bin/bash
# Switch Celery worker environment between dev and prod
#
# This script makes it easy to point your local k3s Celery workers
# at either the dev or prod Supabase database.
#
# Usage:
#   ./switch-worker-env.sh dev     # Switch to dev Supabase
#   ./switch-worker-env.sh prod    # Switch to prod Supabase
#   ./switch-worker-env.sh status  # Show current environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="match-scraper"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check kubectl context
check_context() {
    local current_context=$(kubectl config current-context 2>/dev/null || echo "none")
    if [ "$current_context" != "rancher-desktop" ]; then
        log_warning "Current context is '$current_context'"
        log_info "Switching to rancher-desktop context..."
        kubectl config use-context rancher-desktop || {
            log_error "Failed to switch context. Is rancher-desktop running?"
            exit 1
        }
    fi
}

# Get current environment
get_current_env() {
    local configmap_exists=$(kubectl get configmap -n "$NAMESPACE" missing-table-worker-config 2>/dev/null | wc -l)
    if [ "$configmap_exists" -eq 0 ]; then
        echo "none"
        return
    fi

    local env_label=$(kubectl get configmap -n "$NAMESPACE" missing-table-worker-config -o jsonpath='{.metadata.labels.environment}' 2>/dev/null || echo "unknown")
    echo "$env_label"
}

# Show status
show_status() {
    local current_env=$(get_current_env)

    echo ""
    log_info "Celery Worker Environment Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ "$current_env" = "none" ]; then
        log_warning "No workers deployed"
        echo ""
        echo "To deploy workers, run:"
        echo "  ./switch-worker-env.sh dev"
        echo ""
        return
    fi

    echo "Current Environment: ${BLUE}$current_env${NC}"
    echo ""

    # Get Supabase URL
    local supabase_url=$(kubectl get configmap -n "$NAMESPACE" missing-table-worker-config -o jsonpath='{.data.SUPABASE_URL}' 2>/dev/null || echo "N/A")
    echo "Supabase URL: $supabase_url"
    echo ""

    # Get worker pods
    log_info "Worker Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=missing-table-worker -o wide 2>/dev/null || echo "  No pods found"
    echo ""

    # Get RabbitMQ queue info
    log_info "RabbitMQ Queues:"
    kubectl exec -n "$NAMESPACE" rabbitmq-0 -- rabbitmqctl list_queues name messages consumers 2>/dev/null || echo "  Unable to query RabbitMQ"
    echo ""
}

# Deploy environment
deploy_env() {
    local env=$1

    log_info "Switching to $env environment..."
    echo ""

    # Check if manifests exist
    local configmap_file="$SCRIPT_DIR/configmap-${env}.yaml"
    local secret_file="$SCRIPT_DIR/secret-${env}.yaml"

    if [ ! -f "$configmap_file" ]; then
        log_error "ConfigMap file not found: $configmap_file"

        if [ "$env" = "prod" ]; then
            log_warning "Production environment not set up yet."
            echo ""
            echo "To set up production:"
            echo "  1. cp k3s/worker/configmap-prod.yaml.template k3s/worker/configmap-prod.yaml"
            echo "  2. cp k3s/worker/secret-prod.yaml.template k3s/worker/secret-prod.yaml"
            echo "  3. Edit both files with your production Supabase credentials"
            echo "  4. Run: ./switch-worker-env.sh prod"
            echo ""
        fi
        exit 1
    fi

    if [ ! -f "$secret_file" ]; then
        log_error "Secret file not found: $secret_file"
        exit 1
    fi

    # Delete existing resources
    local current_env=$(get_current_env)
    if [ "$current_env" != "none" ]; then
        log_info "Removing current $current_env configuration..."
        kubectl delete configmap -n "$NAMESPACE" missing-table-worker-config --ignore-not-found=true
        kubectl delete secret -n "$NAMESPACE" missing-table-worker-secrets --ignore-not-found=true
    fi

    # Apply new configuration
    log_info "Applying $env configuration..."
    kubectl apply -f "$configmap_file"
    kubectl apply -f "$secret_file"

    log_success "Configuration applied"
    echo ""

    # Check if deployment exists
    local deployment_exists=$(kubectl get deployment -n "$NAMESPACE" missing-table-celery-worker 2>/dev/null | wc -l)

    if [ "$deployment_exists" -eq 0 ]; then
        # First time deployment
        log_info "Creating worker deployment..."
        kubectl apply -f "$SCRIPT_DIR/deployment.yaml"
        log_success "Deployment created"
        echo ""
        log_info "Waiting for pods to be ready..."
        kubectl wait --for=condition=ready pod -n "$NAMESPACE" -l app=missing-table-worker --timeout=120s || true
    else
        # Restart existing deployment
        log_info "Restarting worker deployment..."
        kubectl rollout restart deployment/missing-table-celery-worker -n "$NAMESPACE"
        log_success "Deployment restarted"
        echo ""
        log_info "Waiting for rollout to complete..."
        kubectl rollout status deployment/missing-table-celery-worker -n "$NAMESPACE" --timeout=120s || true
    fi

    echo ""
    log_success "Successfully switched to $env environment!"
    echo ""

    # Show current status
    show_status

    # Show logs hint
    echo "To view worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app=missing-table-worker -f"
    echo ""
}

# Main script
main() {
    local command=${1:-help}

    case "$command" in
        dev)
            check_context
            deploy_env "dev"
            ;;
        prod)
            check_context
            deploy_env "prod"
            ;;
        status)
            check_context
            show_status
            ;;
        help|--help|-h)
            echo "Usage: $0 {dev|prod|status}"
            echo ""
            echo "Commands:"
            echo "  dev     - Switch workers to dev Supabase database"
            echo "  prod    - Switch workers to prod Supabase database"
            echo "  status  - Show current environment and worker status"
            echo ""
            echo "Examples:"
            echo "  $0 dev      # Switch to dev"
            echo "  $0 prod     # Switch to prod"
            echo "  $0 status   # Check current status"
            echo ""
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            echo "Usage: $0 {dev|prod|status}"
            echo "Run '$0 help' for more information"
            exit 1
            ;;
    esac
}

main "$@"
