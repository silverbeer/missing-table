#!/bin/bash

# Build and Push Docker Images for Missing Table
# Handles multi-platform builds for both local (ARM64/AMD64) and cloud (AMD64) deployments
# Usage:
#   ./build-and-push.sh backend dev          # Build backend for dev (AMD64, push to registry)
#   ./build-and-push.sh frontend prod        # Build frontend for prod (AMD64, push to registry)
#   ./build-and-push.sh backend local        # Build backend for local (current platform)
#   ./build-and-push.sh all dev              # Build all services for dev

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="us-central1-docker.pkg.dev/missing-table/missing-table"
SUPPORTED_SERVICES=("backend" "frontend" "all")
SUPPORTED_ENVIRONMENTS=("local" "dev" "prod")

# Helper functions
print_usage() {
    echo "Usage: $0 <service> <environment>"
    echo ""
    echo "Services:"
    echo "  backend   - Build backend service"
    echo "  frontend  - Build frontend service"
    echo "  all       - Build all services"
    echo ""
    echo "Environments:"
    echo "  local     - Build for local development (current platform, no push)"
    echo "  dev       - Build for dev environment (AMD64, push to registry)"
    echo "  prod      - Build for production (AMD64, push to registry)"
    echo ""
    echo "Examples:"
    echo "  $0 backend dev"
    echo "  $0 frontend prod"
    echo "  $0 all dev"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

print_info() {
    echo -e "${YELLOW}INFO: $1${NC}"
}

# Validate arguments
if [ $# -ne 2 ]; then
    print_error "Invalid number of arguments"
    print_usage
    exit 1
fi

SERVICE=$1
ENVIRONMENT=$2

# Validate service
if [[ ! " ${SUPPORTED_SERVICES[@]} " =~ " ${SERVICE} " ]]; then
    print_error "Invalid service: $SERVICE"
    print_usage
    exit 1
fi

# Validate environment
if [[ ! " ${SUPPORTED_ENVIRONMENTS[@]} " =~ " ${ENVIRONMENT} " ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    print_usage
    exit 1
fi

# Build function
build_service() {
    local service=$1
    local env=$2
    local dockerfile="${service}/Dockerfile"
    local context="${service}/"
    local tag="${env}"

    print_info "Building ${service} for ${env} environment..."

    # Determine platform and push strategy
    if [ "$env" = "local" ]; then
        # Local build - use current platform, no push
        PLATFORM=$(docker info --format '{{.Architecture}}')
        print_info "Building for local platform: ${PLATFORM}"

        docker build \
            -t "${REGISTRY}/${service}:${tag}" \
            -f "${dockerfile}" \
            "${context}"

        print_success "Built ${service}:${tag} for local use"

    else
        # Cloud build - always use AMD64 (GKE requirement), push to registry
        print_info "Building for AMD64 (GKE requirement) and pushing to registry..."

        # CRITICAL: GKE clusters run on AMD64 architecture
        # Always build for linux/amd64 when deploying to cloud

        # Add build arguments for frontend
        if [ "$service" = "frontend" ]; then
            # Set API URL based on environment
            if [ "$env" = "dev" ]; then
                API_URL="https://dev.missingtable.com"
            elif [ "$env" = "prod" ]; then
                API_URL="https://missingtable.com"
            else
                API_URL="http://localhost:8000"
            fi

            print_info "Setting VUE_APP_API_URL=${API_URL}"

            docker buildx build \
                --platform linux/amd64 \
                --build-arg VUE_APP_API_URL="${API_URL}" \
                -t "${REGISTRY}/${service}:${tag}" \
                -f "${dockerfile}" \
                "${context}" \
                --push
        else
            docker buildx build \
                --platform linux/amd64 \
                -t "${REGISTRY}/${service}:${tag}" \
                -f "${dockerfile}" \
                "${context}" \
                --push
        fi

        print_success "Built and pushed ${service}:${tag} to ${REGISTRY}"
    fi
}

# Main execution
print_info "Starting build process..."
print_info "Service: ${SERVICE}"
print_info "Environment: ${ENVIRONMENT}"
echo ""

if [ "$SERVICE" = "all" ]; then
    # Build all services
    build_service "backend" "$ENVIRONMENT"
    echo ""
    build_service "frontend" "$ENVIRONMENT"
else
    # Build single service
    build_service "$SERVICE" "$ENVIRONMENT"
fi

echo ""
print_success "Build process completed!"

# Show next steps
if [ "$ENVIRONMENT" != "local" ]; then
    echo ""
    print_info "Next steps:"
    echo "  1. Deploy to Kubernetes:"
    echo "     kubectl rollout restart deployment/missing-table-${SERVICE} -n missing-table-${ENVIRONMENT}"
    echo ""
    echo "  2. Check deployment status:"
    echo "     kubectl rollout status deployment/missing-table-${SERVICE} -n missing-table-${ENVIRONMENT}"
    echo ""
    echo "  3. View logs:"
    echo "     kubectl logs -f -l app.kubernetes.io/component=${SERVICE} -n missing-table-${ENVIRONMENT}"
fi
