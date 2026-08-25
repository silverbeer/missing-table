#!/bin/bash
# Rebuild worker image and deploy to k3s
#
# This script:
# 1. Builds the Docker image from backend code
# 2. Imports it into Rancher Desktop's containerd
# 3. Restarts the deployment in k3s
#
# Usage:
#   ./rebuild-and-deploy.sh           # Rebuild and restart
#   ./rebuild-and-deploy.sh --build-only  # Only build image
#   ./rebuild-and-deploy.sh --deploy-only # Only restart deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NAMESPACE="match-scraper"
IMAGE_NAME="missing-table-worker:latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

build_image() {
    log_info "Building Docker image..."
    echo ""

    cd "$REPO_ROOT"

    if docker build -f backend/Dockerfile -t "$IMAGE_NAME" backend/; then
        log_success "Docker image built successfully"
        return 0
    else
        log_error "Failed to build Docker image"
        return 1
    fi
}

import_image() {
    log_info "Importing image to Rancher Desktop..."
    echo ""

    if docker save "$IMAGE_NAME" | nerdctl --namespace k8s.io load; then
        log_success "Image imported to Rancher Desktop"
        return 0
    else
        log_error "Failed to import image"
        return 1
    fi
}

restart_deployment() {
    log_info "Restarting worker deployment..."
    echo ""

    # Check kubectl context
    local current_context=$(kubectl config current-context 2>/dev/null || echo "none")
    if [ "$current_context" != "rancher-desktop" ]; then
        log_warning "Current context is '$current_context'"
        log_info "Switching to rancher-desktop context..."
        kubectl config use-context rancher-desktop || {
            log_error "Failed to switch context"
            return 1
        }
    fi

    # Both workers run from this one image, so a rebuild that restarts only
    # one leaves the other running last week's code. This used to name
    # `missing-table-celery-worker`, which has not existed since the split —
    # the script built and imported, then failed here, and the worker kept
    # serving whatever it was last built with.
    local deployments=()
    for d in missing-table-celery-worker-local missing-table-celery-worker-prod; do
        if kubectl get deployment -n "$NAMESPACE" "$d" &>/dev/null; then
            deployments+=("$d")
        fi
    done

    if [ ${#deployments[@]} -eq 0 ]; then
        log_error "No worker deployments found in namespace '$NAMESPACE'"
        echo ""
        echo "Expected one or both of:"
        echo "  missing-table-celery-worker-local   (kubectl apply -f deployment.yaml)"
        echo "  missing-table-celery-worker-prod    (kubectl apply -f deployment-prod.yaml)"
        return 1
    fi

    # -prod consumes matches.prod and writes to the CLOUD Supabase. Restarting
    # it is a production action; say so rather than let it look like a local
    # dev loop.
    for d in "${deployments[@]}"; do
        if [ "$d" = "missing-table-celery-worker-prod" ]; then
            log_warning "$d consumes matches.prod against the CLOUD Supabase — restarting PRODUCTION ingest"
        else
            log_info "$d (local queue)"
        fi
    done
    echo ""

    local failed=0
    for d in "${deployments[@]}"; do
        if kubectl rollout restart "deployment/$d" -n "$NAMESPACE"; then
            log_success "$d restarted"

            if kubectl rollout status "deployment/$d" -n "$NAMESPACE" --timeout=60s 2>/dev/null; then
                log_success "$d rollout complete"
            else
                log_warning "$d rollout is taking longer than expected (this is normal)"
                log_info "Check status with: kubectl get pods -n $NAMESPACE -l app=missing-table-worker"
            fi
        else
            log_error "Failed to restart $d"
            failed=1
        fi
        echo ""
    done

    return $failed
}

show_status() {
    echo ""
    log_info "Worker Status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    kubectl get pods -n "$NAMESPACE" -l app=missing-table-worker
    echo ""

    log_info "To view logs:"
    echo "  kubectl logs -n $NAMESPACE -l app=missing-table-worker -f"
    echo ""
}

main() {
    local mode="${1:-full}"

    echo ""
    log_info "Worker Rebuild & Deploy Script"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    case "$mode" in
        --build-only)
            build_image || exit 1
            import_image || exit 1
            log_success "Build complete! Image ready in Rancher Desktop"
            ;;
        --deploy-only)
            restart_deployment || exit 1
            show_status
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  (none)         - Build image, import, and restart deployment (default)"
            echo "  --build-only   - Only build and import image"
            echo "  --deploy-only  - Only restart deployment"
            echo "  --help, -h     - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Full rebuild and deploy"
            echo "  $0 --build-only     # Just rebuild image"
            echo "  $0 --deploy-only    # Just restart workers"
            echo ""
            ;;
        *)
            # Full workflow
            build_image || exit 1
            echo ""
            import_image || exit 1
            echo ""
            restart_deployment || exit 1
            show_status

            log_success "All done! Workers are running with updated code"
            ;;
    esac

    echo ""
}

main "$@"
