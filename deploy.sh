#!/bin/bash

# AWS Deployment Script for Sports League App
# Usage: ./deploy.sh [environment] [action]
# Example: ./deploy.sh production deploy

set -e

# Configuration
ENVIRONMENT=${1:-production}
ACTION=${2:-deploy}
AWS_REGION=${AWS_REGION:-us-east-1}
APP_NAME="sports-league"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if required tools are installed
    command -v aws >/dev/null 2>&1 || { log_error "AWS CLI is required but not installed."; exit 1; }
    command -v docker >/dev/null 2>&1 || { log_error "Docker is required but not installed."; exit 1; }
    command -v terraform >/dev/null 2>&1 || { log_error "Terraform is required but not installed."; exit 1; }
    command -v node >/dev/null 2>&1 || { log_error "Node.js is required but not installed."; exit 1; }
    
    # Check AWS credentials
    aws sts get-caller-identity >/dev/null 2>&1 || { log_error "AWS credentials not configured."; exit 1; }
    
    log_success "Prerequisites check passed"
}

# Initialize infrastructure
init_infrastructure() {
    log_info "Initializing infrastructure..."
    
    cd terraform
    
    # Initialize Terraform
    terraform init
    
    # Validate configuration
    terraform validate
    
    # Plan deployment
    terraform plan -out=tfplan
    
    # Ask for confirmation
    read -p "Do you want to apply the infrastructure changes? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        terraform apply tfplan
        log_success "Infrastructure deployed successfully"
    else
        log_warning "Infrastructure deployment cancelled"
        exit 1
    fi
    
    cd ..
}

# Build and push backend
deploy_backend() {
    log_info "Building and deploying backend..."
    
    # Get ECR repository URL from Terraform output
    ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL
    
    # Build Docker image
    cd backend
    docker build -t $APP_NAME-backend .
    
    # Tag and push image
    docker tag $APP_NAME-backend:latest $ECR_URL:latest
    docker tag $APP_NAME-backend:latest $ECR_URL:$(git rev-parse --short HEAD)
    docker push $ECR_URL:latest
    docker push $ECR_URL:$(git rev-parse --short HEAD)
    
    cd ..
    
    # Update ECS service
    CLUSTER_NAME=$(cd terraform && terraform output -raw ecs_cluster_name)
    SERVICE_NAME=$(cd terraform && terraform output -raw ecs_service_name)
    
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --force-new-deployment \
        --region $AWS_REGION
    
    # Wait for deployment to complete
    log_info "Waiting for backend deployment to complete..."
    aws ecs wait services-stable \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $AWS_REGION
    
    log_success "Backend deployed successfully"
}

# Deploy frontend
deploy_frontend() {
    log_info "Building and deploying frontend..."
    
    # Get S3 bucket and CloudFront distribution from Terraform output
    S3_BUCKET=$(cd terraform && terraform output -raw s3_bucket_name)
    CF_DISTRIBUTION_ID=$(cd terraform && terraform output -raw cloudfront_distribution_id)
    API_URL=$(cd terraform && terraform output -raw api_endpoint)
    
    # Build frontend
    cd frontend
    
    # Set environment variables for build
    export VUE_APP_API_URL=$API_URL
    export VUE_APP_SUPABASE_URL=${VUE_APP_SUPABASE_URL}
    export VUE_APP_SUPABASE_ANON_KEY=${VUE_APP_SUPABASE_ANON_KEY}
    
    # Install dependencies and build
    npm ci
    npm run build
    
    # Sync to S3
    aws s3 sync dist/ s3://$S3_BUCKET \
        --delete \
        --cache-control "public, max-age=31536000" \
        --exclude "index.html" \
        --exclude "*.json"
    
    # Upload index.html with no-cache headers
    aws s3 cp dist/index.html s3://$S3_BUCKET/index.html \
        --cache-control "no-cache, no-store, must-revalidate"
    
    # Invalidate CloudFront cache
    aws cloudfront create-invalidation \
        --distribution-id $CF_DISTRIBUTION_ID \
        --paths "/*"
    
    cd ..
    
    log_success "Frontend deployed successfully"
}

# Run health checks
health_check() {
    log_info "Running health checks..."
    
    API_URL=$(cd terraform && terraform output -raw api_endpoint)
    FRONTEND_URL=$(cd terraform && terraform output -raw frontend_url)
    
    # Check backend health
    log_info "Checking backend health..."
    for i in {1..30}; do
        if curl -f "$API_URL/health" >/dev/null 2>&1; then
            log_success "Backend health check passed"
            break
        else
            log_info "Backend not ready, waiting... ($i/30)"
            sleep 10
        fi
        
        if [ $i -eq 30 ]; then
            log_error "Backend health check failed"
            exit 1
        fi
    done
    
    # Check frontend
    log_info "Checking frontend..."
    if curl -f "$FRONTEND_URL" >/dev/null 2>&1; then
        log_success "Frontend health check passed"
    else
        log_warning "Frontend health check failed (might be CDN propagation delay)"
    fi
    
    log_success "Health checks completed"
}

# Show deployment information
show_info() {
    log_info "Deployment Information:"
    
    cd terraform
    
    echo "Frontend URL: $(terraform output -raw frontend_url)"
    echo "API URL: $(terraform output -raw api_endpoint)"
    echo "CloudFront Distribution ID: $(terraform output -raw cloudfront_distribution_id)"
    echo "ECR Repository: $(terraform output -raw ecr_repository_url)"
    
    cd ..
}

# Rollback deployment
rollback() {
    log_warning "Rolling back deployment..."
    
    # Get previous image tag from ECS
    CLUSTER_NAME=$(cd terraform && terraform output -raw ecs_cluster_name)
    SERVICE_NAME=$(cd terraform && terraform output -raw ecs_service_name)
    
    # This is a simplified rollback - in production you'd want to track versions
    log_info "Triggering ECS rollback..."
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --force-new-deployment \
        --region $AWS_REGION
    
    log_success "Rollback initiated"
}

# Destroy infrastructure
destroy() {
    log_warning "This will destroy ALL infrastructure!"
    read -p "Are you ABSOLUTELY sure? Type 'yes' to confirm: " -r
    echo
    if [[ $REPLY == "yes" ]]; then
        cd terraform
        terraform destroy
        cd ..
        log_success "Infrastructure destroyed"
    else
        log_info "Destroy cancelled"
    fi
}

# Main deployment function
main() {
    log_info "Starting deployment for environment: $ENVIRONMENT"
    
    case $ACTION in
        "init")
            check_prerequisites
            init_infrastructure
            ;;
        "deploy")
            check_prerequisites
            deploy_backend
            deploy_frontend
            health_check
            show_info
            ;;
        "backend")
            check_prerequisites
            deploy_backend
            health_check
            ;;
        "frontend")
            check_prerequisites
            deploy_frontend
            health_check
            ;;
        "health")
            health_check
            ;;
        "info")
            show_info
            ;;
        "rollback")
            rollback
            ;;
        "destroy")
            destroy
            ;;
        *)
            echo "Usage: $0 [environment] [action]"
            echo "Actions: init, deploy, backend, frontend, health, info, rollback, destroy"
            exit 1
            ;;
    esac
    
    log_success "Deployment completed successfully!"
}

# Run main function
main