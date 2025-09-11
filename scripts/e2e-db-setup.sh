#!/bin/bash
# E2E Test Database Setup Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if required tools are available
check_requirements() {
    if ! command -v supabase &> /dev/null; then
        print_error "Supabase CLI not found. Please install with: brew install supabase/tap/supabase"
        exit 1
    fi
    
    if [ ! -f "$PROJECT_ROOT/supabase-e2e/config.toml" ]; then
        print_error "E2E Supabase config not found. Expected: $PROJECT_ROOT/supabase-e2e/config.toml"
        exit 1
    fi
    
    if [ ! -f "$PROJECT_ROOT/.env.e2e" ]; then
        print_error "E2E environment file not found. Expected: $PROJECT_ROOT/.env.e2e"
        exit 1
    fi
}

# Start E2E Supabase instance
start_e2e_database() {
    print_header "Starting E2E Test Database"
    
    cd "$PROJECT_ROOT" || exit 1
    
    # Check if e2e instance is already running
    if curl -s http://127.0.0.1:54321/health &> /dev/null; then
        print_warning "E2E Supabase instance already running on port 54321"
        return 0
    fi
    
    print_warning "Starting E2E Supabase instance (port 55321)..."
    supabase start --workdir supabase-e2e
    
    if [ $? -eq 0 ]; then
        print_success "E2E Supabase instance started successfully"
        print_warning "API URL: http://127.0.0.1:54321"
        print_warning "Studio URL: http://127.0.0.1:54323"
    else
        print_error "Failed to start E2E Supabase instance"
        exit 1
    fi
}

# Wait for database to be ready
wait_for_database() {
    print_header "Waiting for Database to be Ready"
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://127.0.0.1:54321/rest/v1/ &> /dev/null; then
            print_success "Database is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "Database did not become ready within 60 seconds"
    exit 1
}

# Display connection information
show_connection_info() {
    print_header "E2E Database Connection Information"
    echo
    echo "📊 Supabase Studio: http://127.0.0.1:54323"
    echo "🔗 API URL: http://127.0.0.1:54321"
    echo "🗃️  Database URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    echo "📧 Inbucket (Email Testing): http://127.0.0.1:54324"
    echo
    echo "Environment file: .env.e2e"
    echo
    print_success "E2E Test Database setup complete!"
    echo
    print_warning "Next steps:"
    echo "1. Run: ./scripts/e2e-db-seed.sh (to add test data)"
    echo "2. Run: cd backend && uv run pytest -m e2e (to run tests)"
}

# Show usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Setup E2E test database for Missing Table application"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -s, --status   Check if E2E database is running"
    echo "  -k, --stop     Stop E2E database"
    echo
    echo "Examples:"
    echo "  $0                  # Setup and start E2E database"
    echo "  $0 --status         # Check if E2E database is running"
    echo "  $0 --stop           # Stop E2E database"
}

# Check database status
check_status() {
    print_header "E2E Database Status"
    
    if curl -s http://127.0.0.1:54321/rest/v1/ &> /dev/null; then
        print_success "E2E Supabase instance is running"
        echo "📊 Studio: http://127.0.0.1:54323"
        echo "🔗 API: http://127.0.0.1:54321"
        echo "🗃️  Database: postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    else
        print_warning "E2E Supabase instance is not running"
        echo "Run: $0 to start the database"
    fi
}

# Stop database
stop_database() {
    print_header "Stopping E2E Database"
    
    cd "$PROJECT_ROOT" || exit 1
    
    if ! curl -s http://127.0.0.1:54321/rest/v1/ &> /dev/null; then
        print_warning "E2E Supabase instance is not running"
        return 0
    fi
    
    print_warning "Stopping E2E Supabase instance..."
    supabase stop --project-id missing-table-e2e
    
    if [ $? -eq 0 ]; then
        print_success "E2E Supabase instance stopped"
    else
        print_error "Failed to stop E2E Supabase instance"
        exit 1
    fi
}

# Main execution
main() {
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--status)
            check_status
            exit 0
            ;;
        -k|--stop)
            stop_database
            exit 0
            ;;
        "")
            # Default: setup database
            check_requirements
            start_e2e_database
            wait_for_database
            show_connection_info
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"