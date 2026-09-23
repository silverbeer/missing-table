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
DEPLOYMENT="missing-table-celery-worker-prod"
IMAGE_REPO="missing-table-worker"

# Tag by commit, not :latest (SB-860).
#
# The workers used to deploy from `missing-table-worker:latest` with
# imagePullPolicy: Never. A mutable tag plus no registry meant the running
# pods and the tag could drift apart silently: on 2026-08-27 the pods were on
# an image ten months newer than what `:latest` pointed at, so any restart —
# reboot, eviction, OOM kill — would have quietly downgraded ingest by ten
# months without failing or alerting.
#
# A commit-shaped tag makes the running code visible in `kubectl get deploy -o
# wide`, and makes a restart re-pull the same bits by construction.
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
    # An image built from uncommitted work is not reproducible from the repo.
    # Say so in the tag rather than letting it pass for the commit.
    IMAGE_TAG="${GIT_SHA}-dirty"
else
    IMAGE_TAG="${GIT_SHA}"
fi
IMAGE_NAME="${IMAGE_REPO}:${IMAGE_TAG}"

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
    log_info "Building Docker image ${IMAGE_NAME}..."
    echo ""

    cd "$REPO_ROOT"

    # GIT_SHA is baked in so the running worker can say which commit it is —
    # answering "is the fix live?" without grepping the container filesystem.
    if docker build -f backend/Dockerfile \
            --build-arg GIT_SHA="$IMAGE_TAG" \
            -t "$IMAGE_NAME" backend/; then
        log_success "Docker image built: $IMAGE_NAME"

        local size
        size="$(docker image inspect "$IMAGE_NAME" --format '{{.Size}}' 2>/dev/null || echo 0)"
        if [ "$size" -gt 2000000000 ]; then
            log_warning "Image is $((size / 1000000))MB — expected ~850MB."
            log_warning "Check backend/.dockerignore is excluding .venv (SB-860)."
        fi
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

    # One worker, one queue (SB-854). There was a second deployment,
    # `missing-table-celery-worker-local`, which consumed `matches` and wrote
    # to the same CLOUD Supabase as this one. Nothing published to `matches`,
    # so it processed zero tasks while its name implied a local-database
    # safety net that never existed. It was retired rather than renamed.
    local deployments=()
    for d in missing-table-celery-worker-prod; do
        if kubectl get deployment -n "$NAMESPACE" "$d" &>/dev/null; then
            deployments+=("$d")
        fi
    done

    if [ ${#deployments[@]} -eq 0 ]; then
        log_error "No worker deployment found in namespace '$NAMESPACE'"
        echo ""
        echo "Expected:"
        echo "  missing-table-celery-worker-prod    (kubectl apply -f deployment-prod.yaml)"
        return 1
    fi

    # This worker consumes matches.prod and writes to the CLOUD Supabase.
    # Restarting it is a production action; say so rather than let it look
    # like a local dev loop.
    for d in "${deployments[@]}"; do
        log_warning "$d consumes matches.prod against the CLOUD Supabase — restarting PRODUCTION ingest"
    done
    echo ""

    local failed=0
    for d in "${deployments[@]}"; do
        # `set image` rather than `rollout restart`: it pins the deployment to
        # the tag just built, so the running commit is recorded in the spec
        # and a later restart cannot pick up something else. A restart alone
        # would re-resolve a mutable tag, which is the drift this fixes.
        if kubectl set image "deployment/$d" \
                "celery-worker=${IMAGE_NAME}" -n "$NAMESPACE"; then
            log_success "$d pinned to $IMAGE_NAME"

            if kubectl rollout status "deployment/$d" -n "$NAMESPACE" --timeout=120s 2>/dev/null; then
                log_success "$d rollout complete"
            else
                log_warning "$d rollout is taking longer than expected (this is normal)"
                log_info "Check status with: kubectl get pods -n $NAMESPACE -l app=missing-table-worker"
            fi
        else
            log_error "Failed to update $d"
            failed=1
        fi
        echo ""
    done

    return $failed
}

check_drift() {
    # Two merged worker PRs once sat undeployed for a day with nothing to say
    # so (SB-860). The deployed tag now carries the commit, so the comparison
    # is a string compare.
    local deployed
    deployed="$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-worker")].image}' 2>/dev/null)"

    if [ -z "$deployed" ]; then
        log_warning "Worker deployment not found; cannot check drift"
        return 0
    fi

    local deployed_tag="${deployed##*:}"
    log_info "Deployed: $deployed"

    if [ "$deployed_tag" = "latest" ]; then
        log_warning "Worker still deploys from the mutable :latest tag."
        log_warning "Run this script to pin it to a commit (SB-860)."
        return 1
    fi

    case "$deployed_tag" in
        *-dirty)
            log_warning "Worker runs an image built from uncommitted changes ($deployed_tag)."
            return 1
            ;;
    esac

    local head
    head="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
    if [ "$deployed_tag" != "$head" ]; then
        log_warning "Worker is on $deployed_tag; HEAD is $head."
        if git -C "$REPO_ROOT" merge-base --is-ancestor "$deployed_tag" HEAD 2>/dev/null; then
            local behind
            behind="$(git -C "$REPO_ROOT" rev-list --count "${deployed_tag}..HEAD" 2>/dev/null || echo '?')"
            log_warning "It is $behind commit(s) behind. Run this script to deploy HEAD."
        fi
        return 1
    fi

    log_success "Worker is running HEAD ($head)"
    return 0
}

show_status() {
    echo ""
    log_info "Worker Status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    kubectl get pods -n "$NAMESPACE" -l app=missing-table-worker
    echo ""

    log_info "Deployed image:"
    kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-worker")].image}{"\n"}' 2>/dev/null
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
        --check)
            # Guarded by `if` so `set -e` does not abort on a drift result of 1
            # before the exit code is chosen here.
            if check_drift; then exit 0; else exit 1; fi
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  (none)         - Build image, import, and restart deployment (default)"
            echo "  --build-only   - Only build and import image"
            echo "  --deploy-only  - Only restart deployment"
            echo "  --check        - Report whether the deployed worker matches HEAD"
            echo "  --help, -h     - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Full rebuild and deploy"
            echo "  $0 --build-only     # Just rebuild image"
            echo "  $0 --deploy-only    # Just restart workers"
            echo "  $0 --check          # Is the running worker on HEAD?"
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

            log_success "All done! Worker is running $IMAGE_NAME"
            ;;
    esac

    echo ""
}

main "$@"
