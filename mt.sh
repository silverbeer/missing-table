#!/bin/bash

# Missing Table Environment Management Script
# Usage: ./mt.sh [command] [options]

set -e

SCRIPT_NAME="mt.sh"
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_header() {
    echo -e "${PURPLE}🚀 $1${NC}"
    echo "======================================"
}

# Check if we're in the right directory
check_directory() {
    if [[ ! -f "backend/Dockerfile.dev" ]] || [[ ! -f "frontend/Dockerfile.dev" ]] || [[ ! -f "helm/missing-table/Chart.yaml" ]]; then
        log_error "Please run this script from the Missing Table project root directory"
        log_error "Expected files: backend/Dockerfile.dev, frontend/Dockerfile.dev, helm/missing-table/Chart.yaml"
        exit 1
    fi
}

# Show help
show_help() {
    echo -e "${CYAN}Missing Table Environment Manager v${VERSION}${NC}"
    echo ""
    echo "Usage: ./${SCRIPT_NAME} [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start [mode]     Start the environment"
    echo "    local          Start with local dev servers (default)"
    echo "    k8s            Start with Kubernetes"
    echo "    docker         Start with Docker Compose"
    echo ""
    echo "  stop             Stop all services"
    echo "  restart [mode]   Restart with specified mode"
    echo "  status           Show status of all services"
    echo "  build            Build Docker images"
    echo "  logs [service]   Show logs (backend|frontend|supabase)"
    echo "  clean            Clean up containers and reset"
    echo ""
    echo "Examples:"
    echo "  ./${SCRIPT_NAME} start           # Start local development"
    echo "  ./${SCRIPT_NAME} start k8s       # Start with Kubernetes"  
    echo "  ./${SCRIPT_NAME} stop            # Stop everything"
    echo "  ./${SCRIPT_NAME} status          # Check what's running"
    echo "  ./${SCRIPT_NAME} build           # Build fresh images"
    echo "  ./${SCRIPT_NAME} logs backend    # View backend logs"
    echo ""
}

# Start Supabase
start_supabase() {
    log_info "Starting Supabase..."
    if npx supabase start; then
        log_success "Supabase started successfully"
        npx supabase status | head -10
    else
        log_error "Failed to start Supabase"
        return 1
    fi
}

# Start local development mode
start_local() {
    log_header "Starting Missing Table - Local Development Mode"
    
    start_supabase
    
    echo ""
    log_info "Starting backend server..."
    cd backend
    uv run python app.py &
    BACKEND_PID=$!
    cd ..
    echo "Backend PID: $BACKEND_PID"
    
    echo ""
    log_info "Starting frontend server..."
    cd frontend  
    npm run serve &
    FRONTEND_PID=$!
    cd ..
    echo "Frontend PID: $FRONTEND_PID"
    
    # Save PIDs for later cleanup
    echo "$BACKEND_PID" > .backend.pid
    echo "$FRONTEND_PID" > .frontend.pid
    
    echo ""
    log_success "Local development started!"
    echo ""
    echo "🌐 Access URLs:"
    echo "   Frontend: http://localhost:8080"
    echo "   Backend:  http://localhost:8000" 
    echo "   Supabase: http://127.0.0.1:54323"
    echo ""
    echo "💡 Use './mt.sh stop' to shut down all services"
    echo "💡 Use './mt.sh logs backend' or './mt.sh logs frontend' to view logs"
}

# Start Kubernetes mode
start_k8s() {
    log_header "Starting Missing Table - Kubernetes Mode"
    
    # Check if Kubernetes is available
    if ! kubectl cluster-info >/dev/null 2>&1; then
        log_warning "Kubernetes cluster not accessible. Starting Rancher Desktop..."
        
        # Check if Rancher Desktop is running
        if ! pgrep -f "Rancher Desktop" >/dev/null 2>&1; then
            log_info "Starting Rancher Desktop application..."
            open -a "Rancher Desktop"
            
            log_info "Waiting for Rancher Desktop to start..."
            local attempts=0
            while ! kubectl cluster-info >/dev/null 2>&1 && [ $attempts -lt 60 ]; do
                sleep 2
                attempts=$((attempts + 1))
                printf "."
            done
            echo ""
            
            if [ $attempts -eq 60 ]; then
                log_error "Rancher Desktop failed to start within 2 minutes"
                log_error "Please start Rancher Desktop manually and try again"
                exit 1
            fi
            
            log_success "Rancher Desktop started successfully!"
        else
            log_error "Rancher Desktop is running but Kubernetes is not accessible"
            log_error "Please check Rancher Desktop settings and ensure Kubernetes is enabled"
            exit 1
        fi
    fi
    
    start_supabase
    
    echo ""
    log_info "Deploying to Kubernetes with Helm..."
    if ./helm/deploy-helm.sh; then
        log_success "Kubernetes deployment successful!"
        
        echo ""
        log_info "Starting port-forwards..."
        kubectl port-forward -n missing-table service/missing-table-frontend 8080:8080 &
        kubectl port-forward -n missing-table service/missing-table-backend 8000:8000 &
        
        echo ""
        log_success "Kubernetes mode started!"
        echo ""
        echo "🌐 Access URLs:"
        echo "   Frontend: http://localhost:8080"
        echo "   Backend:  http://localhost:8000"
        echo "   Supabase: http://127.0.0.1:54323"
        echo ""
        echo "💡 Use './mt.sh status' to check pod status"
        echo "💡 Use './mt.sh stop' to shut down all services"
    else
        log_error "Kubernetes deployment failed"
        exit 1
    fi
}

# Start Docker Compose mode  
start_docker() {
    log_header "Starting Missing Table - Docker Compose Mode"
    
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found"
        exit 1
    fi
    
    log_info "Starting with Docker Compose..."
    if docker-compose up -d; then
        log_success "Docker Compose started successfully!"
        docker-compose ps
        
        echo ""
        echo "🌐 Access URLs:"
        echo "   Check 'docker-compose ps' for port mappings"
    else
        log_error "Docker Compose failed to start"
        exit 1
    fi
}

# Stop all services
stop_all() {
    log_header "Stopping Missing Table Environment"
    
    # Stop Kubernetes port-forwards
    log_info "Stopping port-forward processes..."
    pkill -f "kubectl port-forward" 2>/dev/null || log_warning "No port-forward processes found"
    
    # Scale down Kubernetes deployments
    if kubectl cluster-info >/dev/null 2>&1; then
        log_info "Scaling down Kubernetes deployments..."
        kubectl scale deployment missing-table-backend --replicas=0 -n missing-table 2>/dev/null || true
        kubectl scale deployment missing-table-frontend --replicas=0 -n missing-table 2>/dev/null || true
        kubectl scale deployment missing-table-redis --replicas=0 -n missing-table 2>/dev/null || true
    fi
    
    # Stop local development servers
    log_info "Stopping local development servers..."
    if [[ -f ".backend.pid" ]]; then
        kill $(cat .backend.pid) 2>/dev/null || true
        rm .backend.pid
    fi
    if [[ -f ".frontend.pid" ]]; then
        kill $(cat .frontend.pid) 2>/dev/null || true  
        rm .frontend.pid
    fi
    
    # Kill processes on common ports
    for port in 8000 8080 8081 3000; do
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
    done
    
    # Stop Docker Compose
    if [[ -f "docker-compose.yml" ]]; then
        log_info "Stopping Docker Compose..."
        docker-compose down 2>/dev/null || true
    fi
    
    # Stop Supabase  
    log_info "Stopping Supabase..."
    npx supabase stop || log_warning "Supabase may already be stopped"
    
    log_success "Environment stopped successfully!"
}

# Show status
show_status() {
    log_header "Missing Table Environment Status"
    
    echo ""
    echo "🗄️  Supabase:"
    if npx supabase status 2>/dev/null | head -5; then
        echo "   Status: Running ✅"
    else
        echo "   Status: Stopped ❌"
    fi
    
    echo ""
    echo "☸️  Kubernetes:"
    if kubectl cluster-info >/dev/null 2>&1; then
        echo "   Cluster: Available ✅"
        kubectl get pods -n missing-table 2>/dev/null | head -10 || echo "   No missing-table pods found"
    else
        echo "   Cluster: Not available ❌"
    fi
    
    echo ""
    echo "🌐 Port Usage:"
    for port in 8000 8080 8081 3000; do
        if lsof -ti:$port >/dev/null 2>&1; then
            process=$(lsof -ti:$port | head -1 | xargs ps -p | tail -1 | awk '{for(i=5;i<=NF;i++) printf $i" "}')
            echo "   Port $port: In use ✅ ($process)"
        else
            echo "   Port $port: Available ⚪"
        fi
    done
    
    echo ""
    echo "🐳 Docker:"
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep missing-table 2>/dev/null; then
        echo "   Missing Table containers found ✅"
    else
        echo "   No Missing Table containers running ⚪"
    fi
}

# Build images
build_images() {
    log_header "Building Docker Images"
    
    if [[ -f "build-docker-images.sh" ]]; then
        ./build-docker-images.sh
    else
        log_error "build-docker-images.sh not found. Please ensure the build script exists."
        exit 1
    fi
}

# Show logs
show_logs() {
    local service=$1
    
    case $service in
        "backend")
            if kubectl cluster-info >/dev/null 2>&1; then
                log_info "Showing Kubernetes backend logs..."
                kubectl logs -f deployment/missing-table-backend -n missing-table
            else
                log_info "Kubernetes not available. Showing local backend logs..."
                log_warning "For local development, run backend manually to see logs"
            fi
            ;;
        "frontend")
            if kubectl cluster-info >/dev/null 2>&1; then
                log_info "Showing Kubernetes frontend logs..."
                kubectl logs -f deployment/missing-table-frontend -n missing-table
            else
                log_info "Kubernetes not available. Showing local frontend logs..."
                log_warning "For local development, run frontend manually to see logs"
            fi
            ;;
        "supabase")
            log_info "Showing Supabase logs..."
            docker logs supabase_db_missing-table -f 2>/dev/null || log_warning "Supabase container not found"
            ;;
        *)
            log_error "Unknown service: $service"
            echo "Available services: backend, frontend, supabase"
            ;;
    esac
}

# Clean up
clean_all() {
    log_header "Cleaning Up Missing Table Environment"
    
    stop_all
    
    echo ""
    log_info "Removing Docker containers..."
    docker ps -a --format "table {{.Names}}\t{{.Image}}" | grep missing-table | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true
    
    log_info "Removing temporary files..."
    rm -f .backend.pid .frontend.pid
    
    log_success "Cleanup complete!"
}

# Main script logic
main() {
    check_directory
    
    case "${1:-help}" in
        "start")
            case "${2:-local}" in
                "local"|"") start_local ;;
                "k8s"|"kubernetes") start_k8s ;;
                "docker") start_docker ;;
                *) log_error "Unknown start mode: $2"; show_help ;;
            esac
            ;;
        "stop") stop_all ;;
        "restart") 
            stop_all
            sleep 2
            case "${2:-local}" in
                "local"|"") start_local ;;
                "k8s"|"kubernetes") start_k8s ;;  
                "docker") start_docker ;;
                *) log_error "Unknown restart mode: $2"; show_help ;;
            esac
            ;;
        "status") show_status ;;
        "build") build_images ;;
        "logs") show_logs "${2:-backend}" ;;
        "clean") clean_all ;;
        "help"|"-h"|"--help") show_help ;;
        *) log_error "Unknown command: $1"; echo ""; show_help ;;
    esac
}

# Run main function with all arguments
main "$@"