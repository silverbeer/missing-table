#!/bin/bash

# Deploy Match-Scraper to GKE with RabbitMQ Integration
# This script handles the complete deployment of the match-scraper CronJob
# including building, pushing, and deploying to Kubernetes
#
# Usage:
#   ./scripts/deploy-match-scraper.sh           # Full deployment
#   ./scripts/deploy-match-scraper.sh --test    # Deploy and create test job
#   ./scripts/deploy-match-scraper.sh --skip-build  # Skip build, just deploy

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="us-central1-docker.pkg.dev/missing-table/missing-table"
IMAGE_NAME="match-scraper"
NAMESPACE="missing-table-dev"
CRONJOB_NAME="match-scraper"
MATCH_SCRAPER_DIR="/Users/silverbeer/gitrepos/match-scraper"
MISSING_TABLE_DIR="/Users/silverbeer/gitrepos/missing-table"

# Parse arguments
SKIP_BUILD=false
RUN_TEST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --test)
            RUN_TEST=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-build    Skip Docker build and push"
            echo "  --test          Create and run a test job after deployment"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Helper functions
print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    print_section "Checking Prerequisites"

    # Check if running from correct directory
    if [ ! -f "$MISSING_TABLE_DIR/CLAUDE.md" ]; then
        print_error "Not in missing-table directory: $MISSING_TABLE_DIR"
        exit 1
    fi

    # Check if match-scraper exists
    if [ ! -d "$MATCH_SCRAPER_DIR" ]; then
        print_error "match-scraper directory not found: $MATCH_SCRAPER_DIR"
        exit 1
    fi

    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        print_error "docker is not installed"
        exit 1
    fi

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi

    # Check if helm is available
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed"
        exit 1
    fi

    # Check kubectl context
    CURRENT_CONTEXT=$(kubectl config current-context)
    if [[ ! "$CURRENT_CONTEXT" =~ "missing-table" ]]; then
        print_warning "Current kubectl context: $CURRENT_CONTEXT"
        print_warning "Expected: gke_missing-table_*"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_success "Prerequisites check passed"
}

# Build and push Docker image
build_and_push() {
    print_section "Building and Pushing Docker Image"

    cd "$MATCH_SCRAPER_DIR"

    print_info "Building image: ${REGISTRY}/${IMAGE_NAME}:latest"
    print_info "Platform: linux/amd64 (GKE)"

    # Build with platform specification
    docker build \
        --platform linux/amd64 \
        -t "${REGISTRY}/${IMAGE_NAME}:latest" \
        .

    print_success "Docker image built"

    # Push to registry
    print_info "Pushing to Google Artifact Registry..."
    docker push "${REGISTRY}/${IMAGE_NAME}:latest"

    print_success "Image pushed: ${REGISTRY}/${IMAGE_NAME}:latest"

    cd "$MISSING_TABLE_DIR"
}

# Update Helm secrets with RabbitMQ configuration
update_helm_secrets() {
    print_section "Updating Helm Secrets"

    print_info "Checking if RabbitMQ configuration exists in values-dev.yaml..."

    if [ ! -f "helm/missing-table/values-dev.yaml" ]; then
        print_error "values-dev.yaml not found"
        print_info "Create from template: helm/missing-table/values-dev.yaml.example"
        exit 1
    fi

    # Check if rabbitmq section exists
    if ! grep -q "rabbitmq:" helm/missing-table/values-dev.yaml; then
        print_warning "RabbitMQ configuration not found in values-dev.yaml"
        print_info "Add the following to your values-dev.yaml:"
        echo ""
        echo "rabbitmq:"
        echo "  username: admin"
        echo "  password: admin123  # Change this!"
        echo "  host: messaging-rabbitmq.missing-table-dev.svc.cluster.local"
        echo "  port: 5672"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "RabbitMQ configuration found"
    fi

    # Deploy Helm release to update secrets
    print_info "Deploying Helm release to update secrets..."
    helm upgrade missing-table ./helm/missing-table \
        -n $NAMESPACE \
        --values ./helm/missing-table/values-dev.yaml \
        --wait

    print_success "Helm secrets updated"

    # Verify secret was created
    print_info "Verifying secret..."
    if kubectl get secret missing-table-secrets -n $NAMESPACE -o jsonpath='{.data.rabbitmq-url}' | base64 -d | grep -q "amqp://"; then
        print_success "RabbitMQ URL secret verified"
    else
        print_error "RabbitMQ URL secret not found or invalid"
        exit 1
    fi
}

# Deploy CronJob to Kubernetes
deploy_cronjob() {
    print_section "Deploying CronJob to Kubernetes"

    print_info "Applying CronJob manifest..."
    kubectl apply -f k8s/match-scraper-cronjob.yaml

    print_success "CronJob deployed"

    # Wait a moment for it to be created
    sleep 2

    # Verify deployment
    print_info "Verifying CronJob..."
    kubectl get cronjob $CRONJOB_NAME -n $NAMESPACE

    print_success "CronJob verification complete"
}

# Create and monitor test job
create_test_job() {
    print_section "Creating Test Job"

    TEST_JOB_NAME="${CRONJOB_NAME}-test-$(date +%s)"

    print_info "Creating test job: $TEST_JOB_NAME"
    kubectl create job --from=cronjob/$CRONJOB_NAME $TEST_JOB_NAME -n $NAMESPACE

    print_success "Test job created: $TEST_JOB_NAME"

    # Wait for pod to be created
    print_info "Waiting for pod to start..."
    sleep 5

    # Get pod name
    POD_NAME=$(kubectl get pods -n $NAMESPACE -l job-name=$TEST_JOB_NAME -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$POD_NAME" ]; then
        print_error "Pod not found for job $TEST_JOB_NAME"
        exit 1
    fi

    print_info "Pod: $POD_NAME"
    echo ""
    print_info "Streaming logs (Ctrl+C to stop)..."
    echo ""

    kubectl logs -f $POD_NAME -n $NAMESPACE || true

    echo ""
    print_info "Check job status:"
    kubectl get job $TEST_JOB_NAME -n $NAMESPACE

    echo ""
    print_info "Next steps:"
    echo "  1. Verify RabbitMQ queue: kubectl port-forward -n $NAMESPACE svc/messaging-rabbitmq 15672:15672"
    echo "     Then open http://localhost:15672 (admin/admin123)"
    echo "  2. Check Celery workers: kubectl logs -n $NAMESPACE deployment/missing-table-celery-worker --tail=50"
    echo "  3. Delete test job: kubectl delete job $TEST_JOB_NAME -n $NAMESPACE"
}

# Display post-deployment information
show_post_deployment_info() {
    print_section "Deployment Complete"

    echo "CronJob Information:"
    echo "  Name: $CRONJOB_NAME"
    echo "  Namespace: $NAMESPACE"
    echo "  Image: ${REGISTRY}/${IMAGE_NAME}:latest"
    echo ""
    echo "Useful Commands:"
    echo "  # View CronJob details"
    echo "  kubectl describe cronjob $CRONJOB_NAME -n $NAMESPACE"
    echo ""
    echo "  # View recent jobs"
    echo "  kubectl get jobs -n $NAMESPACE --selector=app=match-scraper"
    echo ""
    echo "  # Create test job"
    echo "  kubectl create job --from=cronjob/$CRONJOB_NAME test-\$(date +%s) -n $NAMESPACE"
    echo ""
    echo "  # View logs of most recent job"
    echo "  kubectl logs -f job/\$(kubectl get jobs -n $NAMESPACE --selector=app=match-scraper --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}') -n $NAMESPACE"
    echo ""
    echo "  # Suspend CronJob (pause scheduled runs)"
    echo "  kubectl patch cronjob $CRONJOB_NAME -n $NAMESPACE -p '{\"spec\":{\"suspend\":true}}'"
    echo ""
    echo "  # Resume CronJob"
    echo "  kubectl patch cronjob $CRONJOB_NAME -n $NAMESPACE -p '{\"spec\":{\"suspend\":false}}'"
    echo ""
    echo "Monitoring:"
    echo "  # RabbitMQ Management UI"
    echo "  kubectl port-forward -n $NAMESPACE svc/messaging-rabbitmq 15672:15672"
    echo "  # Then open http://localhost:15672 (admin/admin123)"
    echo ""
    echo "  # Celery Worker Logs"
    echo "  kubectl logs -n $NAMESPACE deployment/missing-table-celery-worker --tail=50 -f"
    echo ""
}

# Main execution
main() {
    print_section "Match-Scraper Deployment Script"
    echo "Image: ${REGISTRY}/${IMAGE_NAME}:latest"
    echo "Namespace: $NAMESPACE"
    echo ""

    check_prerequisites

    if [ "$SKIP_BUILD" = false ]; then
        build_and_push
    else
        print_info "Skipping build (--skip-build specified)"
    fi

    update_helm_secrets
    deploy_cronjob

    if [ "$RUN_TEST" = true ]; then
        create_test_job
    fi

    show_post_deployment_info

    print_success "Deployment completed successfully!"
}

# Run main function
main
