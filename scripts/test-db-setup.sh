#!/bin/bash

#
# Test Database Setup Script
#
# Sets up database with test data for different test layers:
#   - integration: Basic reference data + sample teams
#   - e2e: Full database with users, teams, matches
#   - contract: Minimal data for API contract tests
#
# Usage:
#   ./scripts/test-db-setup.sh integration
#   ./scripts/test-db-setup.sh e2e
#   ./scripts/test-db-setup.sh contract
#

set -e  # Exit on error

LAYER=${1:-integration}
BACKEND_DIR="$(cd "$(dirname "$0")/../backend" && pwd)"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Supabase is running
check_supabase() {
    log_info "Checking if Supabase is running..."
    
    if ! curl -s http://127.0.0.1:54321 > /dev/null 2>&1; then
        log_error "Supabase is not running"
        log_info "Start Supabase with: cd supabase-local && npx supabase start"
        exit 1
    fi
    
    log_info "Supabase is running"
}

# Setup integration test database
setup_integration() {
    log_info "Setting up integration test database..."
    
    # Check if db_tools.sh exists and use it to restore reference data
    if [ -f "$SCRIPTS_DIR/db_tools.sh" ]; then
        log_info "Restoring reference data using db_tools.sh..."
        "$SCRIPTS_DIR/db_tools.sh" restore
    else
        log_warn "db_tools.sh not found, skipping data restore"
    fi
    
    log_info "Integration test database setup complete"
}

# Setup e2e test database
setup_e2e() {
    log_info "Setting up e2e test database..."
    
    # Check if e2e-db-setup.sh exists and use it
    if [ -f "$SCRIPTS_DIR/e2e-db-setup.sh" ]; then
        log_info "Running e2e-db-setup.sh..."
        "$SCRIPTS_DIR/e2e-db-setup.sh"
    else
        log_warn "e2e-db-setup.sh not found, using integration setup"
        setup_integration
    fi
    
    # Seed test users if needed
    if [ -f "$SCRIPTS_DIR/seed_test_users.sh" ]; then
        log_info "Seeding test users..."
        "$SCRIPTS_DIR/seed_test_users.sh"
    fi
    
    log_info "E2E test database setup complete"
}

# Setup contract test database
setup_contract() {
    log_info "Setting up contract test database..."
    
    # Contract tests need minimal data - just reference data
    log_info "Restoring minimal reference data..."
    
    if [ -f "$SCRIPTS_DIR/db_tools.sh" ]; then
        "$SCRIPTS_DIR/db_tools.sh" restore
    fi
    
    log_info "Contract test database setup complete"
}

# Setup unit test database (minimal or none)
setup_unit() {
    log_info "Unit tests don't require database setup (use mocks)"
    log_info "If you need to setup database for pseudo-unit tests, use: integration"
}

# Teardown database
teardown() {
    log_info "Tearing down test database..."
    
    # For now, we don't actually tear down since we're using local Supabase
    # In the future, we could add cleanup logic here
    
    log_warn "Teardown not implemented - using persistent local Supabase"
    log_info "To reset database: cd supabase-local && npx supabase db reset"
}

# Main execution
main() {
    log_info "Test Database Setup"
    log_info "Layer: $LAYER"
    echo ""
    
    check_supabase
    
    case "$LAYER" in
        integration)
            setup_integration
            ;;
        e2e)
            setup_e2e
            ;;
        contract)
            setup_contract
            ;;
        unit)
            setup_unit
            ;;
        teardown)
            teardown
            ;;
        *)
            log_error "Unknown layer: $LAYER"
            echo "Usage: $0 {integration|e2e|contract|unit|teardown}"
            exit 1
            ;;
    esac
    
    echo ""
    log_info "Done!"
}

main
