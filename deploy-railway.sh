#!/bin/bash

# Railway + Supabase Deployment Script
# Usage: ./deploy-railway.sh [setup|deploy|status]

set -e

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

# Check if Railway CLI is installed
check_railway_cli() {
    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI is not installed"
        log_info "Install it with: npm install -g @railway/cli"
        exit 1
    fi
}

# Check if user is logged into Railway
check_railway_auth() {
    if ! railway whoami &> /dev/null; then
        log_error "Not logged into Railway"
        log_info "Login with: railway login"
        exit 1
    fi
}

# Setup function - creates projects and sets basic config
setup() {
    log_info "Setting up Railway projects..."
    
    check_railway_cli
    check_railway_auth
    
    # Setup backend
    log_info "Setting up backend project..."
    cd backend
    railway init
    railway add redis
    
    log_success "Backend project created with Redis"
    
    # Setup frontend
    log_info "Setting up frontend project..."
    cd ../frontend
    railway init
    
    log_success "Frontend project created"
    
    cd ..
    
    log_warning "Next steps:"
    echo "1. Set up your Supabase project at https://supabase.com"
    echo "2. Run the migrations in Supabase SQL editor"
    echo "3. Get your Supabase credentials"
    echo "4. Run: ./deploy-railway.sh configure"
}

# Configure environment variables
configure() {
    log_info "Configuring environment variables..."
    
    # Prompt for Supabase credentials
    echo "Enter your Supabase credentials:"
    read -p "Supabase URL: " SUPABASE_URL
    read -p "Supabase Anon Key: " SUPABASE_ANON_KEY
    read -s -p "Supabase Service Key: " SUPABASE_SERVICE_KEY
    echo
    read -s -p "Supabase JWT Secret: " SUPABASE_JWT_SECRET
    echo
    
    # Generate CSRF secret
    CSRF_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Configure backend
    log_info "Configuring backend environment..."
    cd backend
    railway variables set SUPABASE_URL="$SUPABASE_URL"
    railway variables set SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
    railway variables set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"
    railway variables set SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET"
    railway variables set CSRF_SECRET_KEY="$CSRF_SECRET"
    railway variables set ENVIRONMENT="production"
    railway variables set USE_REDIS_RATE_LIMIT="true"
    
    # Get backend URL for frontend config
    log_info "Deploying backend to get URL..."
    railway deploy --detach
    
    # Wait a bit for deployment
    sleep 30
    
    BACKEND_URL=$(railway domain)
    if [ -z "$BACKEND_URL" ]; then
        log_warning "Backend URL not found. You'll need to set VUE_APP_API_URL manually."
        BACKEND_URL="https://your-backend.up.railway.app"
    else
        BACKEND_URL="https://$BACKEND_URL"
    fi
    
    log_success "Backend configured and deployed"
    
    # Configure frontend
    log_info "Configuring frontend environment..."
    cd ../frontend
    railway variables set VUE_APP_SUPABASE_URL="$SUPABASE_URL"
    railway variables set VUE_APP_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
    railway variables set VUE_APP_API_URL="$BACKEND_URL"
    
    log_success "Frontend configured"
    cd ..
    
    log_success "Configuration complete!"
    log_info "Run: ./deploy-railway.sh deploy"
}

# Deploy both services
deploy() {
    log_info "Deploying to Railway..."
    
    check_railway_cli
    check_railway_auth
    
    # Deploy backend
    log_info "Deploying backend..."
    cd backend
    railway deploy --detach
    
    # Deploy frontend
    log_info "Deploying frontend..."
    cd ../frontend
    railway deploy --detach
    
    cd ..
    
    log_success "Deployment initiated!"
    log_info "Check deployment status with: ./deploy-railway.sh status"
}

# Check status of deployments
status() {
    log_info "Checking deployment status..."
    
    check_railway_cli
    check_railway_auth
    
    echo "=== Backend Status ==="
    cd backend
    railway status
    echo
    echo "Backend URL: https://$(railway domain 2>/dev/null || echo 'domain-not-set')"
    echo "Backend Logs: railway logs"
    echo
    
    echo "=== Frontend Status ==="
    cd ../frontend
    railway status
    echo
    echo "Frontend URL: https://$(railway domain 2>/dev/null || echo 'domain-not-set')"
    echo "Frontend Logs: railway logs"
    
    cd ..
}

# Show logs
logs() {
    SERVICE=${2:-both}
    
    case $SERVICE in
        "backend")
            log_info "Showing backend logs..."
            cd backend && railway logs
            ;;
        "frontend")
            log_info "Showing frontend logs..."
            cd frontend && railway logs
            ;;
        "both"|*)
            log_info "Showing backend logs..."
            cd backend && railway logs --tail 20
            echo
            log_info "Showing frontend logs..."
            cd ../frontend && railway logs --tail 20
            cd ..
            ;;
    esac
}

# Health check
health() {
    log_info "Running health checks..."
    
    # Get URLs
    cd backend
    BACKEND_URL="https://$(railway domain 2>/dev/null)"
    cd ../frontend
    FRONTEND_URL="https://$(railway domain 2>/dev/null)"
    cd ..
    
    # Check backend health
    if curl -f "$BACKEND_URL/health" >/dev/null 2>&1; then
        log_success "Backend health check passed: $BACKEND_URL/health"
    else
        log_error "Backend health check failed: $BACKEND_URL/health"
    fi
    
    # Check frontend
    if curl -f "$FRONTEND_URL" >/dev/null 2>&1; then
        log_success "Frontend health check passed: $FRONTEND_URL"
    else
        log_error "Frontend health check failed: $FRONTEND_URL"
    fi
}

# Scale services
scale() {
    REPLICAS=${2:-1}
    SERVICE=${3:-both}
    
    log_info "Scaling to $REPLICAS replicas..."
    
    case $SERVICE in
        "backend")
            cd backend && railway scale --replicas $REPLICAS
            ;;
        "frontend")
            cd frontend && railway scale --replicas $REPLICAS
            ;;
        "both"|*)
            cd backend && railway scale --replicas $REPLICAS
            cd ../frontend && railway scale --replicas $REPLICAS
            cd ..
            ;;
    esac
}

# Main function
main() {
    ACTION=${1:-help}
    
    case $ACTION in
        "setup")
            setup
            ;;
        "configure")
            configure
            ;;
        "deploy")
            deploy
            ;;
        "status")
            status
            ;;
        "logs")
            logs "$@"
            ;;
        "health")
            health
            ;;
        "scale")
            scale "$@"
            ;;
        "help"|*)
            echo "Railway + Supabase Deployment Script"
            echo
            echo "Usage: $0 [command]"
            echo
            echo "Commands:"
            echo "  setup      - Create Railway projects and add Redis"
            echo "  configure  - Set environment variables"
            echo "  deploy     - Deploy both frontend and backend"
            echo "  status     - Check deployment status"
            echo "  logs       - Show logs [backend|frontend|both]"
            echo "  health     - Run health checks"
            echo "  scale      - Scale services [replicas] [backend|frontend|both]"
            echo "  help       - Show this help message"
            echo
            echo "Example workflow:"
            echo "  1. $0 setup"
            echo "  2. $0 configure"
            echo "  3. $0 deploy"
            echo "  4. $0 status"
            echo "  5. $0 health"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"