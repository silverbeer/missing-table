#!/bin/bash
# Sync Production Environment from GKE Kubernetes
#
# This script retrieves production Supabase credentials from GKE Kubernetes
# and creates/updates the backend/.env.prod file.
#
# Prerequisites:
#   - kubectl must be installed and configured
#   - Must have access to missing-table-prod namespace
#
# Usage:
#   ./scripts/sync-prod-env-from-gke.sh

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

# Main script
print_header "Sync Production Environment from GKE Kubernetes"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed"
    exit 1
fi

print_success "kubectl is installed"

# Check if we can access the cluster
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster"
    echo "Make sure you're connected to a cluster:"
    echo "  kubectl config get-contexts"
    echo "  kubectl config use-context <context-name>"
    exit 1
fi

print_success "Connected to Kubernetes cluster"

# Check current context
current_context=$(kubectl config current-context)
echo "Current context: $current_context"

# Check if secret exists
if ! kubectl get secret missing-table-secrets -n missing-table-prod &> /dev/null 2>&1; then
    print_error "Secret 'missing-table-secrets' not found in namespace 'missing-table-prod'"
    echo ""
    echo "Available secrets in missing-table-prod:"
    kubectl get secrets -n missing-table-prod 2>/dev/null || echo "Cannot access namespace"
    exit 1
fi

print_success "Found missing-table-secrets in missing-table-prod namespace"

# Retrieve secret and decode
echo ""
print_header "Retrieving Secrets from Kubernetes"

echo -n "Retrieving SUPABASE_URL... "
SUPABASE_URL=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.supabase-url}' 2>/dev/null | base64 --decode)
if [ -z "$SUPABASE_URL" ]; then
    print_error "Failed"
    exit 1
fi
echo "✓"

echo -n "Retrieving SUPABASE_ANON_KEY... "
SUPABASE_ANON_KEY=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.supabase-anon-key}' 2>/dev/null | base64 --decode)
if [ -z "$SUPABASE_ANON_KEY" ]; then
    print_error "Failed"
    exit 1
fi
echo "✓"

echo -n "Retrieving SUPABASE_SERVICE_KEY... "
SUPABASE_SERVICE_KEY=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.supabase-service-key}' 2>/dev/null | base64 --decode)
if [ -z "$SUPABASE_SERVICE_KEY" ]; then
    print_error "Failed"
    exit 1
fi
echo "✓"

echo -n "Retrieving SUPABASE_JWT_SECRET... "
SUPABASE_JWT_SECRET=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.supabase-jwt-secret}' 2>/dev/null | base64 --decode)
if [ -z "$SUPABASE_JWT_SECRET" ]; then
    print_error "Failed"
    exit 1
fi
echo "✓"

echo -n "Retrieving DATABASE_URL... "
DATABASE_URL=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.database-url}' 2>/dev/null | base64 --decode)
echo "✓"

echo -n "Retrieving SERVICE_ACCOUNT_SECRET... "
SERVICE_ACCOUNT_SECRET=$(kubectl get secret missing-table-secrets -n missing-table-prod -o jsonpath='{.data.service-account-secret}' 2>/dev/null | base64 --decode)
echo "✓"

print_success "Successfully retrieved all secrets from Kubernetes"

# Show preview (masked)
echo ""
print_header "Retrieved Values (masked)"
echo "SUPABASE_URL: ${SUPABASE_URL:0:30}..."
echo "SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:0:20}...${SUPABASE_ANON_KEY: -8}"
echo "SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_KEY:0:20}...${SUPABASE_SERVICE_KEY: -8}"
echo "SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET:0:20}...${SUPABASE_JWT_SECRET: -8}"

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
