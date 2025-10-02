#!/bin/bash
set -e

# Build and push Docker images to Google Artifact Registry
# Usage: ./scripts/build-and-push.sh [OPTIONS]
#
# Options:
#   --env ENV        Environment (dev|prod) - default: dev
#   --tag TAG        Image tag - default: latest
#   --backend-only   Build and push backend only
#   --frontend-only  Build and push frontend only
#   --project ID     GCP project ID - default: missing-table
#   --region REGION  GCP region - default: us-central1

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
TAG="latest"
BUILD_BACKEND=true
BUILD_FRONTEND=true
PROJECT_ID="missing-table"
REGION="us-central1"
REPO_NAME="missing-table"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --backend-only)
            BUILD_FRONTEND=false
            shift
            ;;
        --frontend-only)
            BUILD_BACKEND=false
            shift
            ;;
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --env ENV        Environment (dev|prod) - default: dev"
            echo "  --tag TAG        Image tag - default: latest"
            echo "  --backend-only   Build and push backend only"
            echo "  --frontend-only  Build and push frontend only"
            echo "  --project ID     GCP project ID - default: missing-table"
            echo "  --region REGION  GCP region - default: us-central1"
            echo ""
            echo "Examples:"
            echo "  $0                           # Build all with defaults"
            echo "  $0 --tag v1.0.0              # Build with specific tag"
            echo "  $0 --backend-only --tag dev  # Build backend only"
            echo "  $0 --env prod --tag v1.0.0   # Build for production"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Set registry URL
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}=== Building and Pushing Docker Images ===${NC}"
echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
echo -e "${BLUE}Tag:${NC} $TAG"
echo -e "${BLUE}Registry:${NC} $REGISTRY"
echo -e "${BLUE}Project:${NC} $PROJECT_ID"
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
    echo -e "${RED}Error: Not authenticated with gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

# Check if Docker auth is configured
if ! grep -q "$REGION-docker.pkg.dev" ~/.docker/config.json 2>/dev/null; then
    echo -e "${YELLOW}Configuring Docker authentication for Artifact Registry...${NC}"
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
fi

# Build and push backend
if [ "$BUILD_BACKEND" = true ]; then
    echo -e "${GREEN}Building backend image...${NC}"
    cd "$PROJECT_ROOT/backend"

    # Choose Dockerfile based on environment
    DOCKERFILE="Dockerfile"
    if [ "$ENVIRONMENT" = "dev" ] && [ -f "Dockerfile.dev" ]; then
        DOCKERFILE="Dockerfile.dev"
    elif [ "$ENVIRONMENT" = "prod" ] && [ -f "Dockerfile.secure" ]; then
        DOCKERFILE="Dockerfile.secure"
    fi

    echo -e "${BLUE}Using Dockerfile: $DOCKERFILE${NC}"
    docker build --platform linux/amd64 -t ${REGISTRY}/backend:${TAG} -f ${DOCKERFILE} .

    echo -e "${GREEN}Pushing backend image...${NC}"
    docker push ${REGISTRY}/backend:${TAG}

    # Also tag as environment-specific
    docker tag ${REGISTRY}/backend:${TAG} ${REGISTRY}/backend:${ENVIRONMENT}
    docker push ${REGISTRY}/backend:${ENVIRONMENT}

    echo -e "${GREEN}✓ Backend image pushed:${NC}"
    echo -e "  ${REGISTRY}/backend:${TAG}"
    echo -e "  ${REGISTRY}/backend:${ENVIRONMENT}"
    echo ""
fi

# Build and push frontend
if [ "$BUILD_FRONTEND" = true ]; then
    echo -e "${GREEN}Building frontend image...${NC}"
    cd "$PROJECT_ROOT/frontend"

    # Choose Dockerfile based on environment
    DOCKERFILE="Dockerfile"
    if [ "$ENVIRONMENT" = "dev" ] && [ -f "Dockerfile.dev" ]; then
        DOCKERFILE="Dockerfile.dev"
    elif [ "$ENVIRONMENT" = "prod" ] && [ -f "Dockerfile.secure" ]; then
        DOCKERFILE="Dockerfile.secure"
    fi

    echo -e "${BLUE}Using Dockerfile: $DOCKERFILE${NC}"
    docker build --platform linux/amd64 -t ${REGISTRY}/frontend:${TAG} -f ${DOCKERFILE} .

    echo -e "${GREEN}Pushing frontend image...${NC}"
    docker push ${REGISTRY}/frontend:${TAG}

    # Also tag as environment-specific
    docker tag ${REGISTRY}/frontend:${TAG} ${REGISTRY}/frontend:${ENVIRONMENT}
    docker push ${REGISTRY}/frontend:${ENVIRONMENT}

    echo -e "${GREEN}✓ Frontend image pushed:${NC}"
    echo -e "  ${REGISTRY}/frontend:${TAG}"
    echo -e "  ${REGISTRY}/frontend:${ENVIRONMENT}"
    echo ""
fi

echo -e "${GREEN}=== Build and Push Complete ===${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Update Helm values with image tags:"
echo "   backend.image.repository: ${REGISTRY}/backend"
echo "   backend.image.tag: ${TAG}"
echo "   frontend.image.repository: ${REGISTRY}/frontend"
echo "   frontend.image.tag: ${TAG}"
echo ""
echo "2. Deploy with Helm:"
echo "   helm upgrade --install missing-table ./helm/missing-table --values ./helm/missing-table/values-${ENVIRONMENT}.yaml"
