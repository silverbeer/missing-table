#!/bin/bash
# Sync Production Environment from GitHub Secrets
#
# This script retrieves production Supabase credentials from GitHub repository
# secrets and creates/updates the backend/.env.prod file.
#
# Prerequisites:
#   - GitHub CLI (gh) must be installed: brew install gh
#   - Must be authenticated: gh auth login
#   - Must have access to repository secrets
#
# Usage:
#   ./scripts/sync-prod-env-from-github.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/backend/.env.prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if GitHub CLI is installed
check_gh_cli() {
    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI (gh) is not installed"
        echo ""
        echo "Install it with:"
        echo "  brew install gh"
        echo ""
        echo "Then authenticate:"
        echo "  gh auth login"
        exit 1
    fi

    print_success "GitHub CLI is installed"
}

# Check if authenticated with GitHub
check_gh_auth() {
    if ! gh auth status &> /dev/null; then
        print_error "Not authenticated with GitHub"
        echo ""
        echo "Authenticate with:"
        echo "  gh auth login"
        exit 1
    fi

    print_success "Authenticated with GitHub"
}

# Get a secret from GitHub
get_secret() {
    local secret_name="$1"
    local value

    echo -n "Retrieving $secret_name... "

    # Note: GitHub CLI doesn't allow reading secret values directly for security
    # We need to use GitHub API with a personal access token

    # Try to get secret (this will fail with standard permissions)
    value=$(gh secret list --repo silverbeer/missing-table 2>&1 | grep -w "$secret_name" || echo "")

    if [ -z "$value" ]; then
        print_error "Secret $secret_name not found or not accessible"
        return 1
    fi

    echo "found"
    return 0
}

# Main script
main() {
    print_header "Sync Production Environment from GitHub Secrets"
    echo ""

    # Check prerequisites
    check_gh_cli
    check_gh_auth

    echo ""
    print_warning "IMPORTANT: GitHub CLI cannot retrieve secret VALUES directly for security"
    print_warning "This is a GitHub security feature - secrets can only be set, not read"
    echo ""
    echo "You have two options:"
    echo ""
    echo "1. Retrieve from GKE Kubernetes (RECOMMENDED)"
    echo "   kubectl get secret missing-table-secrets -n missing-table-prod -o yaml"
    echo ""
    echo "2. Manually copy from GitHub Secrets UI"
    echo "   https://github.com/silverbeer/missing-table/settings/secrets/actions"
    echo ""
    echo "3. Get from Supabase Dashboard"
    echo "   https://supabase.com/dashboard → Select PROD project → Settings → API"
    echo ""

    read -p "Press Enter to see available secrets in GitHub, or Ctrl+C to exit..."

    echo ""
    print_header "Available GitHub Secrets"
    gh secret list --repo silverbeer/missing-table

    echo ""
    print_header "Required Secrets for .env.prod"
    echo "  - PROD_SUPABASE_URL"
    echo "  - PROD_SUPABASE_ANON_KEY"
    echo "  - PROD_SUPABASE_SERVICE_KEY"
    echo "  - PROD_SUPABASE_JWT_SECRET"
    echo "  - PROD_DATABASE_URL"
    echo "  - PROD_SERVICE_ACCOUNT_SECRET"

    echo ""
    print_warning "Switching to alternative method: Retrieve from GKE"
    echo ""
    read -p "Do you want to retrieve secrets from GKE Kubernetes? (y/n): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please use option 2 or 3 above to get credentials manually."
        exit 0
    fi

    # Try to retrieve from GKE
    retrieve_from_gke
}

# Retrieve secrets from GKE Kubernetes
retrieve_from_gke() {
    print_header "Retrieving Secrets from GKE"

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi

    # Check if we can access the cluster
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        echo "Make sure you're connected to the right cluster:"
        echo "  kubectl config use-context gke_missing-table_us-central1_missing-table-prod"
        exit 1
    fi

    # Check current context
    current_context=$(kubectl config current-context)
    echo "Current context: $current_context"

    if [[ "$current_context" != *"prod"* ]]; then
        print_warning "You're not on a prod context!"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi

    # Get the secret
    print_header "Retrieving secret from Kubernetes..."

    # Check if secret exists
    if ! kubectl get secret missing-table-secrets -n missing-table-prod &> /dev/null; then
        print_error "Secret 'missing-table-secrets' not found in namespace 'missing-table-prod'"
        echo ""
        echo "Available secrets:"
        kubectl get secrets -n missing-table-prod
        exit 1
    fi

    # Retrieve secret and decode
    echo "Retrieving SUPABASE_URL..."
    SUPABASE_URL=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.SUPABASE_URL}' | base64 --decode)

    echo "Retrieving SUPABASE_ANON_KEY..."
    SUPABASE_ANON_KEY=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.SUPABASE_ANON_KEY}' | base64 --decode)

    echo "Retrieving SUPABASE_SERVICE_KEY..."
    SUPABASE_SERVICE_KEY=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.SUPABASE_SERVICE_KEY}' | base64 --decode)

    echo "Retrieving SUPABASE_JWT_SECRET..."
    SUPABASE_JWT_SECRET=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.SUPABASE_JWT_SECRET}' | base64 --decode)

    echo "Retrieving DATABASE_URL..."
    DATABASE_URL=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.DATABASE_URL}' | base64 --decode)

    echo "Retrieving SERVICE_ACCOUNT_SECRET..."
    SERVICE_ACCOUNT_SECRET=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.SERVICE_ACCOUNT_SECRET}' | base64 --decode)

    # Validate we got the values
    if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
        print_error "Failed to retrieve required secrets"
        exit 1
    fi

    print_success "Successfully retrieved all secrets from Kubernetes"

    # Show preview (masked)
    echo ""
    print_header "Retrieved Values (masked)"
    echo "SUPABASE_URL: ${SUPABASE_URL:0:30}..."
    echo "SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:0:20}...${SUPABASE_ANON_KEY: -8}"
    echo "SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_KEY:0:20}...${SUPABASE_SERVICE_KEY: -8}"
    echo "SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET:0:20}...${SUPABASE_JWT_SECRET: -8}"

    # Create .env.prod file
    echo ""
    read -p "Write these values to $ENV_FILE? (y/n): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled. No files were modified."
        exit 0
    fi

    # Backup existing file
    if [ -f "$ENV_FILE" ]; then
        backup_file="$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$ENV_FILE" "$backup_file"
        print_success "Backed up existing file to: $backup_file"
    fi

    # Write new .env.prod file
    cat > "$ENV_FILE" << EOF
# Production Environment Configuration
# Generated from Kubernetes secrets on $(date)
# Source: missing-table-secrets in missing-table-prod namespace
#
# ⚠️ SECURITY WARNING ⚠️
# This file contains REAL production credentials
# NEVER commit this file to git
# It is gitignored - keep it that way!

# =============================================================================
# SUPABASE CONFIGURATION (Production)
# =============================================================================

# Production Supabase URL
SUPABASE_URL=$SUPABASE_URL

# Production Anon Key (public, safe to expose to frontend)
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY

# Production Service Key (KEEP SECRET - full database access)
SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY

# JWT Secret for token validation
SUPABASE_JWT_SECRET=$SUPABASE_JWT_SECRET

# Direct database connection URL (for migrations)
DATABASE_URL=$DATABASE_URL

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

# Environment name
ENVIRONMENT=prod

# Application version (will be set by CI/CD)
APP_VERSION=1.0.0

# Security settings
DISABLE_SECURITY=false

# Logging
LOG_LEVEL=INFO
DEBUG=false

# CORS Origins (production domains)
CORS_ORIGINS=https://missingtable.com,https://www.missingtable.com

# =============================================================================
# SERVICE ACCOUNT
# =============================================================================

# Service account secret for API authentication
SERVICE_ACCOUNT_SECRET=$SERVICE_ACCOUNT_SECRET

# =============================================================================
# RABBITMQ/CELERY (Optional - if using messaging platform)
# =============================================================================

# Uncomment if using RabbitMQ/Celery
# RABBITMQ_HOST=localhost
# RABBITMQ_PORT=5672
# RABBITMQ_USERNAME=admin
# RABBITMQ_PASSWORD=your_rabbitmq_password
# CELERY_BROKER_URL=amqp://admin:your_rabbitmq_password@localhost:5672//
# CELERY_RESULT_BACKEND=redis://localhost:6379/0
# REDIS_HOST=localhost
# REDIS_PORT=6379

EOF

    # Set secure permissions
    chmod 600 "$ENV_FILE"

    print_success "Successfully created $ENV_FILE"
    print_success "File permissions set to 600 (owner read/write only)"

    echo ""
    print_header "Next Steps"
    echo "1. Verify the connection:"
    echo "   cd backend && uv run python scripts/diagnose_connection.py prod"
    echo ""
    echo "2. Run schema audit:"
    echo "   cd backend && uv run python scripts/inspect_schema_direct.py prod"
    echo ""
    echo "3. Test with your application:"
    echo "   ./switch-env.sh prod"
    echo "   ./missing-table.sh start"
}

# Run main function
main "$@"
