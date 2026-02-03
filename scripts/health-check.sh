#!/bin/bash

# Health Check Script for Missing Table
# Performs comprehensive health checks on deployed environments
#
# Usage:
#   ./scripts/health-check.sh dev              # Check dev environment
#   ./scripts/health-check.sh prod             # Check production environment
#   ./scripts/health-check.sh https://custom   # Check custom URL
#   ./scripts/health-check.sh                  # Interactive mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-}"
MAX_RETRIES=5
RETRY_DELAY=10
TIMEOUT=10

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

# Get base URL based on environment
get_base_url() {
    local env=$1

    case "$env" in
        local)
            echo "http://localhost:8080"
            ;;
        prod|production)
            echo "https://missingtable.com"
            ;;
        http://*|https://*)
            echo "$env"
            ;;
        *)
            print_error "Invalid environment: $env"
            echo ""
            echo "Usage: $0 <environment|url>"
            echo ""
            echo "Environments:"
            echo "  local       - Local environment (http://localhost:8080)"
            echo "  prod        - Production environment (https://missingtable.com)"
            echo "  <url>       - Custom URL (http://... or https://...)"
            echo ""
            echo "Examples:"
            echo "  $0 local"
            echo "  $0 prod"
            echo "  $0 https://missingtable.com"
            exit 1
            ;;
    esac
}

# Check if a URL is accessible
check_url() {
    local url=$1
    local description=$2
    local retry_count=${3:-1}

    for i in $(seq 1 $retry_count); do
        if curl -f -s -m $TIMEOUT "${url}" > /dev/null 2>&1; then
            return 0
        fi
        if [ $i -lt $retry_count ]; then
            sleep $RETRY_DELAY
        fi
    done

    return 1
}

# Check a URL and get response
check_url_with_response() {
    local url=$1
    local description=$2
    local retry_count=${3:-1}

    for i in $(seq 1 $retry_count); do
        local response=$(curl -f -s -m $TIMEOUT "${url}" 2>&1)
        if [ $? -eq 0 ]; then
            echo "$response"
            return 0
        fi
        if [ $i -lt $retry_count ]; then
            sleep $RETRY_DELAY
        fi
    done

    return 1
}

# Main health check function
run_health_checks() {
    local base_url=$1
    local env_name=$2
    local all_passed=true

    echo ""
    print_step "Running health checks for ${env_name}"
    print_info "Base URL: ${base_url}"
    echo ""

    # 1. Check backend health endpoint
    print_step "Checking backend health..."
    local health_url="${base_url}/health"

    if check_url "$health_url" "Backend health" $MAX_RETRIES; then
        print_success "Backend health check passed"
    else
        print_error "Backend health check failed: ${health_url}"
        all_passed=false
    fi

    # 2. Check frontend
    print_step "Checking frontend..."

    if check_url "$base_url" "Frontend" $MAX_RETRIES; then
        print_success "Frontend check passed"
    else
        print_error "Frontend check failed: ${base_url}"
        all_passed=false
    fi

    # 3. Check version endpoint
    print_step "Checking version endpoint..."
    local version_url="${base_url}/api/version"

    local version_response=$(check_url_with_response "$version_url" "Version API" $MAX_RETRIES)
    if [ $? -eq 0 ]; then
        print_success "Version endpoint check passed"

        # Parse and display version info
        if command -v jq &> /dev/null; then
            local version=$(echo "$version_response" | jq -r '.version // "unknown"')
            local environment=$(echo "$version_response" | jq -r '.environment // "unknown"')
            local status=$(echo "$version_response" | jq -r '.status // "unknown"')

            print_info "Version: ${version}"
            print_info "Environment: ${environment}"
            print_info "Status: ${status}"
        else
            print_warning "jq not installed, skipping version parsing"
            echo "$version_response"
        fi
    else
        print_error "Version endpoint check failed: ${version_url}"
        all_passed=false
    fi

    # 4. Check API endpoints
    print_step "Checking API endpoints..."

    # Check standings API
    local standings_url="${base_url}/api/standings"
    if check_url "$standings_url" "Standings API" 3; then
        print_success "Standings API check passed"
    else
        print_warning "Standings API check failed: ${standings_url}"
        # Don't fail overall check for this - might be empty database
    fi

    # Check matches API
    local matches_url="${base_url}/api/matches"
    if check_url "$matches_url" "Matches API" 3; then
        print_success "Matches API check passed"
    else
        print_warning "Matches API check failed: ${matches_url}"
        # Don't fail overall check for this - might be empty database
    fi

    # 5. Check SSL certificate (for HTTPS)
    if [[ "$base_url" == https://* ]]; then
        print_step "Checking SSL certificate..."

        local domain=$(echo "$base_url" | sed -e 's|^https://||' -e 's|/.*||')

        if echo | openssl s_client -servername "$domain" -connect "${domain}:443" -showcerts 2>/dev/null | grep -q "Verify return code: 0"; then
            print_success "SSL certificate is valid"
        else
            print_warning "SSL certificate check failed or certificate not trusted"
        fi

        # Check certificate expiry
        local expiry=$(echo | openssl s_client -servername "$domain" -connect "${domain}:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
        if [ -n "$expiry" ]; then
            print_info "Certificate expires: ${expiry}"
        fi
    fi

    # Final summary
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ "$all_passed" = true ]; then
        print_success "All critical health checks passed!"
        echo ""
        return 0
    else
        print_error "Some critical health checks failed"
        echo ""
        return 1
    fi
}

# Interactive mode
interactive_mode() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Missing Table - Health Check Utility"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Select environment to check:"
    echo "  1) Local (http://localhost:8080)"
    echo "  2) Production (https://missingtable.com)"
    echo "  3) Custom URL"
    echo "  4) Exit"
    echo ""
    read -p "Enter choice [1-4]: " choice

    case $choice in
        1)
            ENVIRONMENT="local"
            ;;
        2)
            ENVIRONMENT="prod"
            ;;
        3)
            read -p "Enter custom URL: " custom_url
            ENVIRONMENT="$custom_url"
            ;;
        4)
            echo "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # If no environment specified, run interactive mode
    if [ -z "$ENVIRONMENT" ]; then
        interactive_mode
    fi

    # Get base URL for environment
    BASE_URL=$(get_base_url "$ENVIRONMENT")

    # Determine environment name for display
    case "$ENVIRONMENT" in
        dev)
            ENV_NAME="Development"
            ;;
        prod|production)
            ENV_NAME="Production"
            ;;
        *)
            ENV_NAME="Custom"
            ;;
    esac

    # Run health checks
    if run_health_checks "$BASE_URL" "$ENV_NAME"; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main
