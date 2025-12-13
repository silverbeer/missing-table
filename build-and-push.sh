#!/bin/bash

# Build and Push Docker Images for Missing Table
# Handles multi-platform builds for both local (ARM64/AMD64) and cloud (AMD64) deployments
# Usage:
#   ./build-and-push.sh backend dev          # Build backend for dev (AMD64, push to registry)
#   ./build-and-push.sh frontend prod        # Build frontend for prod (AMD64, push to registry)
#   ./build-and-push.sh match-scraper dev    # Build match-scraper for dev (AMD64, push to registry)
#   ./build-and-push.sh backend local        # Build backend for local (current platform)
#   ./build-and-push.sh all dev              # Build all services for dev

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="us-central1-docker.pkg.dev/missing-table/missing-table"
MATCH_SCRAPER_REPO="/Users/silverbeer/gitrepos/match-scraper"
SUPPORTED_SERVICES=("backend" "frontend" "match-scraper" "all")
SUPPORTED_ENVIRONMENTS=("local" "dev" "prod")

# Version configuration
VERSION_FILE="VERSION"
APP_VERSION=""
BUILD_ID="${BUILD_ID:-}"  # Can be set by CI/CD or passed as env var
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Helper functions
print_usage() {
    echo "Usage: $0 <service> <environment>"
    echo ""
    echo "Services:"
    echo "  backend       - Build backend service (FastAPI)"
    echo "  frontend      - Build frontend service (Vue 3)"
    echo "  match-scraper - Build match-scraper service (from external repo)"
    echo "  all           - Build all services (backend + frontend + match-scraper)"
    echo ""
    echo "Environments:"
    echo "  local         - Build for local development (current platform, no push)"
    echo "  dev           - Build for dev environment (AMD64, push to registry)"
    echo "  prod          - Build for production (AMD64, push to registry)"
    echo ""
    echo "Examples:"
    echo "  $0 backend dev"
    echo "  $0 frontend prod"
    echo "  $0 match-scraper dev"
    echo "  $0 all dev"
    echo ""
    echo "Note: match-scraper is built from: $MATCH_SCRAPER_REPO"
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

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

# Read version from VERSION file
read_version() {
    if [ -f "$VERSION_FILE" ]; then
        APP_VERSION=$(cat "$VERSION_FILE" | tr -d '\n\r' | tr -d ' ')
        print_info "Version from $VERSION_FILE: $APP_VERSION"
    else
        APP_VERSION="0.0.0"
        print_error "VERSION file not found, using default: $APP_VERSION"
    fi
}

# Generate full version string with build ID
get_full_version() {
    if [ -n "$BUILD_ID" ]; then
        echo "v${APP_VERSION}-build.${BUILD_ID}"
    else
        echo "v${APP_VERSION}"
    fi
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

# Build function with versioning support
build_service() {
    local service=$1
    local env=$2
    local env_tag="${env}"

    # Get version information
    local full_version=$(get_full_version)
    local version_tag="${full_version}"

    # Handle match-scraper specially (external repo)
    if [ "$service" = "match-scraper" ]; then
        build_match_scraper "$env" "$env_tag"
        return
    fi

    # For backend/frontend, use local directories
    local dockerfile="${service}/Dockerfile"
    local context="${service}/"

    print_step "Building ${service} for ${env} environment..."
    print_info "Version: ${version_tag}"
    print_info "Commit: ${COMMIT_SHA}"

    # Build tags array
    local build_tags=()
    build_tags+=("${REGISTRY}/${service}:${env_tag}")  # Environment tag (dev/prod)

    # Add version tags only for cloud builds
    if [ "$env" != "local" ]; then
        build_tags+=("${REGISTRY}/${service}:${version_tag}")  # Full version with build ID
        build_tags+=("${REGISTRY}/${service}:v${APP_VERSION}")  # Semantic version only

        # Add 'latest' tag for production only
        if [ "$env" = "prod" ]; then
            build_tags+=("${REGISTRY}/${service}:latest")
        fi
    fi

    # Determine platform and push strategy
    if [ "$env" = "local" ]; then
        # Local build - use current platform, no push, no version tags
        PLATFORM=$(docker info --format '{{.Architecture}}')
        print_info "Building for local platform: ${PLATFORM}"

        # Build arguments
        local build_args="--build-arg APP_VERSION=${APP_VERSION}"
        build_args+=" --build-arg COMMIT_SHA=${COMMIT_SHA}"
        build_args+=" --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        build_args+=" --build-arg ENVIRONMENT=${env}"

        docker build \
            $build_args \
            -t "${REGISTRY}/${service}:${env_tag}" \
            -f "${dockerfile}" \
            "${context}"

        print_success "Built ${service}:${env_tag} for local use"

    else
        # Cloud build - always use AMD64 (GKE requirement), push to registry
        print_info "Building for AMD64 (GKE requirement) and pushing to registry..."
        print_info "Tags: ${build_tags[*]}"

        # CRITICAL: GKE clusters run on AMD64 architecture
        # Always build for linux/amd64 when deploying to cloud

        # Build tag arguments for docker buildx
        local tag_args=""
        for tag in "${build_tags[@]}"; do
            tag_args+=" -t ${tag}"
        done

        # Common build arguments
        local build_args="--build-arg APP_VERSION=${APP_VERSION}"
        build_args+=" --build-arg COMMIT_SHA=${COMMIT_SHA}"
        build_args+=" --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        build_args+=" --build-arg ENVIRONMENT=${env}"

        if [ -n "$BUILD_ID" ]; then
            build_args+=" --build-arg BUILD_ID=${BUILD_ID}"
        fi

        # Add service-specific build arguments
        if [ "$service" = "frontend" ]; then
            # Set API URL based on environment
            # For cloud deployments (dev/prod), use empty string for relative URLs
            # Ingress routes /api to backend on same domain
            if [ "$env" = "dev" ] || [ "$env" = "prod" ]; then
                API_URL=""
                print_info "Setting VITE_API_URL='' (relative URLs for ingress routing)"
            else
                # Local development uses localhost backend
                API_URL="http://localhost:8000"
                print_info "Setting VITE_API_URL=${API_URL}"
            fi

            build_args+=" --build-arg VITE_API_URL=${API_URL}"
        fi

        # Build and push with all tags
        docker buildx build \
            --platform linux/amd64 \
            $build_args \
            $tag_args \
            -f "${dockerfile}" \
            "${context}" \
            --push

        print_success "Built and pushed ${service} to ${REGISTRY}"
        for tag in "${build_tags[@]}"; do
            print_info "  - ${tag}"
        done
    fi
}

# Build match-scraper from external repo
build_match_scraper() {
    local env=$1
    local tag=$2
    local service="match-scraper"

    print_step "Building ${service} from external repository..."

    # Check if match-scraper repo exists
    if [ ! -d "$MATCH_SCRAPER_REPO" ]; then
        print_error "Match-scraper repository not found at: $MATCH_SCRAPER_REPO"
        print_info "Please clone the repository first:"
        echo "  git clone https://github.com/silverbeer/match-scraper.git $MATCH_SCRAPER_REPO"
        exit 1
    fi

    # Save current directory
    ORIGINAL_DIR=$(pwd)

    # Change to match-scraper directory
    cd "$MATCH_SCRAPER_REPO"

    print_info "Building from: $MATCH_SCRAPER_REPO"

    if [ "$env" = "local" ]; then
        # Local build - use current platform, no push
        PLATFORM=$(docker info --format '{{.Architecture}}')
        print_info "Building for local platform: ${PLATFORM}"

        docker build \
            -t "${REGISTRY}/${service}:${tag}" \
            .

        print_success "Built ${service}:${tag} for local use"
    else
        # Cloud build - always use AMD64 (GKE requirement), push to registry
        print_info "Building for AMD64 (GKE requirement) and pushing to registry..."
        print_info "Image tag: ${REGISTRY}/${service}:latest"

        # Always tag as 'latest' for match-scraper
        docker buildx build \
            --platform linux/amd64 \
            -t "${REGISTRY}/${service}:latest" \
            . \
            --push

        print_success "Built and pushed ${service}:latest to ${REGISTRY}"
    fi

    # Return to original directory
    cd "$ORIGINAL_DIR"
}

# Main execution
print_info "Starting build process..."
print_info "Service: ${SERVICE}"
print_info "Environment: ${ENVIRONMENT}"

# Read version for non-local builds
if [ "$ENVIRONMENT" != "local" ]; then
    read_version
    print_info "Build ID: ${BUILD_ID:-<not set>}"
    print_info "Commit SHA: ${COMMIT_SHA}"
fi

echo ""

if [ "$SERVICE" = "all" ]; then
    # Build all services
    print_info "Building all services for ${ENVIRONMENT} environment"
    echo ""

    build_service "backend" "$ENVIRONMENT"
    echo ""

    build_service "frontend" "$ENVIRONMENT"
    echo ""

    build_service "match-scraper" "$ENVIRONMENT"
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

    if [ "$SERVICE" = "match-scraper" ]; then
        echo "  Match-Scraper Deployment:"
        echo "    1. Deploy CronJob:"
        echo "       kubectl apply -f k3s/match-scraper/match-scraper-cronjob.yaml"
        echo ""
        echo "    2. Create test job:"
        echo "       kubectl create job --from=cronjob/match-scraper test-\$(date +%s) -n missing-table-${ENVIRONMENT}"
        echo ""
        echo "    3. View logs:"
        echo "       kubectl logs -f -l app=match-scraper -n missing-table-${ENVIRONMENT}"
        echo ""
        echo "    4. Check RabbitMQ queue:"
        echo "       kubectl port-forward -n missing-table-${ENVIRONMENT} svc/messaging-rabbitmq 15672:15672"
        echo "       # Open http://localhost:15672 (admin/admin123)"
    elif [ "$SERVICE" = "all" ]; then
        echo "  Backend/Frontend Deployment:"
        echo "    1. Deploy with Helm:"
        echo "       cd helm && ./deploy-helm.sh"
        echo ""
        echo "  Match-Scraper Deployment:"
        echo "    1. Deploy CronJob:"
        echo "       kubectl apply -f k3s/match-scraper/match-scraper-cronjob.yaml"
        echo ""
        echo "    2. Create test job:"
        echo "       kubectl create job --from=cronjob/match-scraper test-\$(date +%s) -n missing-table-${ENVIRONMENT}"
    else
        echo "  1. Deploy to Kubernetes:"
        echo "     kubectl rollout restart deployment/missing-table-${SERVICE} -n missing-table-${ENVIRONMENT}"
        echo ""
        echo "  2. Check deployment status:"
        echo "     kubectl rollout status deployment/missing-table-${SERVICE} -n missing-table-${ENVIRONMENT}"
        echo ""
        echo "  3. View logs:"
        echo "     kubectl logs -f -l app.kubernetes.io/component=${SERVICE} -n missing-table-${ENVIRONMENT}"
    fi
fi
