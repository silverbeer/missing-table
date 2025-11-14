#!/bin/bash

# ⚠️ DEPRECATED - This script is no longer needed
# As of 2025-11-14, the separate prod environment has been consolidated into missing-table-dev
# All deployments (dev and prod domains) now go to the missing-table-dev namespace
#
# Use GitHub Actions for deployments:
#   - Push to any branch → automatic deployment to missing-table-dev
#   - All domains (dev.missingtable.com, missingtable.com, www.missingtable.com) → missing-table-dev
#
# This script is kept for reference only. If you need emergency manual deployment:
#   ./scripts/deploy-to-dev.sh (if it exists)
# Or use Helm directly:
#   helm upgrade missing-table ./helm/missing-table \
#     --namespace missing-table-dev \
#     --values ./helm/missing-table/values-dev.yaml \
#     --install --wait

echo ""
echo "⚠️  WARNING: This script is DEPRECATED"
echo ""
echo "The separate production environment has been consolidated into missing-table-dev"
echo "to reduce GCP costs from \$283/month to \$40/month."
echo ""
echo "All domains now point to missing-table-dev namespace:"
echo "  - dev.missingtable.com"
echo "  - missingtable.com"
echo "  - www.missingtable.com"
echo ""
echo "For deployments, use GitHub Actions:"
echo "  git push origin <branch>  # Automatically deploys to missing-table-dev"
echo ""
read -p "Continue anyway with legacy script? (type 'yes' to confirm): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Exiting..."
    exit 0
fi
echo ""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration - UPDATED for consolidated environment
GCP_REGION="us-central1"
GKE_CLUSTER="missing-table-dev"  # Changed from missing-table-prod
NAMESPACE="missing-table-dev"    # Changed from missing-table-prod
REGISTRY="us-central1-docker.pkg.dev/missing-table/missing-table"
VERSION_FILE="VERSION"

# Flags
SKIP_CONFIRMATION=false
SKIP_HEALTH_CHECK=false
SPECIFIC_VERSION=""

print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  INFO: $1${NC}"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Manual Production Deployment Script for Missing Table

OPTIONS:
    --version VERSION    Deploy specific version (e.g., v1.2.3)
    --skip-confirmation  Skip confirmation prompts (dangerous!)
    --skip-health-check  Skip post-deployment health checks
    --help               Show this help message

EXAMPLES:
    $0                           # Interactive deployment (recommended)
    $0 --version v1.2.3          # Deploy specific version
    $0 --version v1.2.3 --skip-health-check

NOTES:
    - This script requires kubectl, helm, and gcloud to be installed
    - You must be authenticated to GCP with proper permissions
    - Production deployments should normally go through CI/CD
    - Use this script only for emergency deployments or testing

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --version)
                SPECIFIC_VERSION="$2"
                shift 2
                ;;
            --skip-confirmation)
                SKIP_CONFIRMATION=true
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi

    # Check helm
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed"
        exit 1
    fi

    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud is not installed"
        exit 1
    fi

    print_success "All prerequisites met"
}

# Verify GCP authentication
verify_gcp_auth() {
    print_step "Verifying GCP authentication..."

    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        print_error "Not authenticated to GCP"
        echo "Run: gcloud auth login"
        exit 1
    fi

    local account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    print_info "Authenticated as: ${account}"

    print_success "GCP authentication verified"
}

# Connect to GKE cluster
connect_to_cluster() {
    print_step "Connecting to GKE cluster..."

    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
        --region "$GCP_REGION" &> /dev/null; then
        print_error "Failed to connect to GKE cluster: $GKE_CLUSTER"
        exit 1
    fi

    # Verify connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    print_success "Connected to cluster: $GKE_CLUSTER"
}

# Get current deployment info
get_current_deployment() {
    print_step "Getting current deployment information..."

    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "Namespace $NAMESPACE does not exist"
        print_info "This might be the first deployment"
        echo ""
        return
    fi

    # Get Helm release info
    if helm list -n "$NAMESPACE" | grep -q "missing-table"; then
        local revision=$(helm history missing-table -n "$NAMESPACE" --max 1 -o json | jq -r '.[0].revision')
        local status=$(helm history missing-table -n "$NAMESPACE" --max 1 -o json | jq -r '.[0].status')

        print_info "Current Helm revision: ${revision}"
        print_info "Current status: ${status}"

        # Get current image versions
        if kubectl get deployment missing-table-backend -n "$NAMESPACE" &> /dev/null; then
            local backend_image=$(kubectl get deployment missing-table-backend -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')
            local frontend_image=$(kubectl get deployment missing-table-frontend -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')

            print_info "Backend image: ${backend_image}"
            print_info "Frontend image: ${frontend_image}"
        fi
    else
        print_warning "No existing Helm release found"
        print_info "This will be a fresh deployment"
    fi

    echo ""
}

# Determine version to deploy
determine_version() {
    if [ -n "$SPECIFIC_VERSION" ]; then
        VERSION="$SPECIFIC_VERSION"
        print_info "Using specified version: ${VERSION}"
    elif [ -f "$VERSION_FILE" ]; then
        local file_version=$(cat "$VERSION_FILE" | tr -d '\n\r' | tr -d ' ')
        VERSION="v${file_version}"
        print_info "Using version from VERSION file: ${VERSION}"
    else
        print_error "No version specified and VERSION file not found"
        exit 1
    fi

    # Validate version format
    if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-build\.[0-9]+)?$ ]]; then
        print_warning "Version format seems unusual: ${VERSION}"
        print_info "Expected format: v1.2.3 or v1.2.3-build.123"
    fi

    echo ""
}

# Confirm deployment
confirm_deployment() {
    if [ "$SKIP_CONFIRMATION" = true ]; then
        print_warning "Skipping confirmation (--skip-confirmation flag)"
        return
    fi

    print_header "⚠️  PRODUCTION DEPLOYMENT CONFIRMATION"

    echo -e "${BOLD}You are about to deploy to PRODUCTION (consolidated dev environment):${NC}"
    echo ""
    echo "  Environment: dev (serves all domains)"
    echo "  Cluster: $GKE_CLUSTER"
    echo "  Namespace: $NAMESPACE"
    echo "  Version: $VERSION"
    echo "  URLs: https://dev.missingtable.com, https://missingtable.com, https://www.missingtable.com"
    echo ""
    echo -e "${YELLOW}This will affect all users (dev and prod domains)!${NC}"
    echo ""

    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

    if [ "$confirmation" != "yes" ]; then
        print_info "Deployment cancelled"
        exit 0
    fi

    echo ""
    print_success "Deployment confirmed"
    echo ""
}

# Build images
build_images() {
    print_step "Building Docker images for production..."

    # Check if we're in the project root
    if [ ! -f "build-and-push.sh" ]; then
        print_error "build-and-push.sh not found. Are you in the project root?"
        exit 1
    fi

    # Build backend
    print_info "Building backend..."
    ./build-and-push.sh backend prod

    # Build frontend
    print_info "Building frontend..."
    ./build-and-push.sh frontend prod

    print_success "Images built and pushed successfully"
    echo ""
}

# Deploy with Helm
deploy_with_helm() {
    print_step "Deploying with Helm..."

    # Check if values-dev.yaml exists (consolidated environment)
    if [ ! -f "helm/missing-table/values-dev.yaml" ]; then
        print_error "helm/missing-table/values-dev.yaml not found"
        print_info "This file should exist for the consolidated dev environment"
        exit 1
    fi

    # Deploy with Helm
    print_info "Running Helm upgrade to consolidated dev environment..."
    helm upgrade missing-table ./helm/missing-table \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --values ./helm/missing-table/values-dev.yaml \
        --install \
        --wait \
        --timeout 15m \
        --atomic \
        --cleanup-on-fail

    print_success "Helm deployment successful"
    echo ""
}

# Verify deployment
verify_deployment() {
    print_step "Verifying deployment..."

    # Wait a moment for pods to start
    sleep 5

    # Check backend deployment
    print_info "Checking backend deployment..."
    kubectl rollout status deployment/missing-table-backend -n "$NAMESPACE" --timeout=5m

    # Check frontend deployment
    print_info "Checking frontend deployment..."
    kubectl rollout status deployment/missing-table-frontend -n "$NAMESPACE" --timeout=5m

    # Check celery worker deployment
    print_info "Checking celery worker deployment..."
    kubectl rollout status deployment/missing-table-celery-worker -n "$NAMESPACE" --timeout=5m

    print_success "All deployments are ready"
    echo ""
}

# Run health checks
run_health_checks() {
    if [ "$SKIP_HEALTH_CHECK" = true ]; then
        print_warning "Skipping health checks (--skip-health-check flag)"
        return
    fi

    print_step "Running health checks..."

    # Check if health-check.sh exists
    if [ -f "scripts/health-check.sh" ]; then
        ./scripts/health-check.sh prod
    else
        print_warning "scripts/health-check.sh not found, running basic checks..."

        # Basic health check (consolidated environment serves all domains)
        sleep 10

        if curl -f -s https://dev.missingtable.com/health > /dev/null; then
            print_success "Backend health check passed"
        else
            print_error "Backend health check failed"
            exit 1
        fi

        if curl -f -s https://missingtable.com > /dev/null; then
            print_success "Frontend check passed (prod domain)"
        else
            print_error "Frontend check failed"
            exit 1
        fi
    fi

    echo ""
}

# Show deployment summary
show_summary() {
    print_header "🚀 DEPLOYMENT SUMMARY"

    echo "✅ Deployment completed successfully!"
    echo ""
    echo "Environment: dev (consolidated - serves all domains)"
    echo "Version: $VERSION"
    echo "Namespace: $NAMESPACE"
    echo "URLs:"
    echo "  - https://dev.missingtable.com"
    echo "  - https://missingtable.com"
    echo "  - https://www.missingtable.com"
    echo ""

    # Get new revision
    local new_revision=$(helm history missing-table -n "$NAMESPACE" --max 1 -o json | jq -r '.[0].revision')
    echo "Helm Revision: ${new_revision}"
    echo ""

    print_info "Next steps:"
    echo "  1. Monitor the application:"
    echo "     - https://dev.missingtable.com"
    echo "     - https://missingtable.com"
    echo "     - https://www.missingtable.com"
    echo "  2. Check logs: kubectl logs -f -l app.kubernetes.io/name=missing-table -n $NAMESPACE"
    echo "  3. Check metrics in GCP Console"
    echo ""

    print_info "Rollback command (if needed):"
    echo "  helm rollback missing-table $((new_revision - 1)) -n $NAMESPACE"
    echo ""
}

# Main execution
main() {
    # Parse command line arguments
    parse_args "$@"

    # Show header
    print_header "Missing Table - Production Deployment"

    # Run checks
    check_prerequisites
    verify_gcp_auth
    connect_to_cluster
    get_current_deployment
    determine_version
    confirm_deployment

    # Deploy
    build_images
    deploy_with_helm
    verify_deployment
    run_health_checks

    # Summary
    show_summary

    print_success "Deployment completed successfully! 🎉"
}

# Run main function
main "$@"
