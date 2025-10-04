#!/bin/bash
# Setup GitHub Secrets for GKE Deployment
# This script uses GitHub CLI (gh) to add required secrets to the repository
# It automatically pulls values from your current environment (backend/.env.dev)

set -e

echo "=========================================="
echo "GitHub Secrets Setup for GKE Deployment"
echo "=========================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo ""
    echo "Install it with:"
    echo "  brew install gh"
    echo ""
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo ""
    echo "Please run:"
    echo "  gh auth login"
    echo ""
    exit 1
fi

echo "✅ GitHub CLI is installed and authenticated"
echo ""

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    echo "❌ Could not determine repository. Are you in a git repository?"
    exit 1
fi

echo "📦 Repository: $REPO"
echo ""

# Load environment variables from .env.dev
if [ -f "backend/.env.dev" ]; then
    echo "📄 Loading environment from backend/.env.dev..."
    set -a  # Automatically export all variables
    source backend/.env.dev
    set +a
    echo "✅ Environment loaded"
    echo ""
else
    echo "⚠️  backend/.env.dev not found"
    echo "   This script works best when run from the repository root"
    echo "   with backend/.env.dev configured"
    echo ""
    read -p "Continue anyway? (y/n): " continue_anyway
    if [ "$continue_anyway" != "y" ]; then
        exit 1
    fi
fi

# Function to add a secret from environment variable
add_secret_from_env() {
    local secret_name=$1
    local env_var_name=$2
    local description=$3

    echo "─────────────────────────────────────────"
    echo "Setting: $secret_name"
    echo "Description: $description"

    # Get value from environment variable
    local secret_value="${!env_var_name}"

    if [ -z "$secret_value" ]; then
        echo "⚠️  ${env_var_name} not found in environment"
        read -p "Enter value manually (or 'skip'): " manual_value
        if [ "$manual_value" = "skip" ] || [ -z "$manual_value" ]; then
            echo "⚠️  Skipping $secret_name"
            echo ""
            return
        fi
        secret_value="$manual_value"
    else
        echo "✓ Using value from \$${env_var_name}"
    fi

    echo "$secret_value" | gh secret set "$secret_name" --repo "$REPO"
    echo "✅ Secret $secret_name set successfully"
    echo ""
}

# Function to add a secret from file
add_secret_from_file() {
    local secret_name=$1
    local secret_description=$2
    local file_path=$3

    echo "─────────────────────────────────────────"
    echo "Setting: $secret_name"
    echo "Description: $secret_description"
    echo ""

    if [ -f "$file_path" ]; then
        read -p "Use value from $file_path? (y/n): " use_file
        if [ "$use_file" = "y" ]; then
            gh secret set "$secret_name" --repo "$REPO" < "$file_path"
            echo "✅ Secret $secret_name set from $file_path"
            echo ""
            return
        fi
    fi

    read -p "Enter path to JSON key file (or 'skip'): " key_file

    if [ "$key_file" = "skip" ] || [ -z "$key_file" ]; then
        echo "⚠️  Skipping $secret_name"
        echo ""
        return
    fi

    if [ ! -f "$key_file" ]; then
        echo "❌ File not found: $key_file"
        echo "⚠️  Skipping $secret_name"
        echo ""
        return
    fi

    gh secret set "$secret_name" --repo "$REPO" < "$key_file"
    echo "✅ Secret $secret_name set successfully"
    echo ""
}

echo "════════════════════════════════════════"
echo "  Required Secrets for Dev Deployment"
echo "════════════════════════════════════════"
echo ""

# 1. GCP Service Account Key
add_secret_from_file \
    "GCP_SA_KEY" \
    "GCP service account JSON key for authentication" \
    "$HOME/.config/gcloud/application_default_credentials.json"

# 2. Supabase URL (from environment)
add_secret_from_env \
    "SUPABASE_URL" \
    "SUPABASE_URL" \
    "Supabase project URL"

# 3. Supabase Anon Key (from environment)
add_secret_from_env \
    "SUPABASE_ANON_KEY" \
    "SUPABASE_ANON_KEY" \
    "Supabase anonymous key"

# 4. Supabase Service Key (from environment)
add_secret_from_env \
    "SUPABASE_SERVICE_KEY" \
    "SUPABASE_SERVICE_KEY" \
    "Supabase service role key"

# 5. Supabase JWT Secret (from environment)
add_secret_from_env \
    "SUPABASE_JWT_SECRET" \
    "SUPABASE_JWT_SECRET" \
    "Supabase JWT secret"

# 6. Service Account Secret (from environment or generate new)
if [ -z "$SERVICE_ACCOUNT_SECRET" ]; then
    echo "─────────────────────────────────────────"
    echo "Setting: SERVICE_ACCOUNT_SECRET"
    echo "Description: Service account secret for API access"
    echo "⚠️  SERVICE_ACCOUNT_SECRET not found in environment"
    echo "🔒 Generating new random secret..."
    SERVICE_ACCOUNT_SECRET=$(openssl rand -base64 32)
fi
add_secret_from_env \
    "SERVICE_ACCOUNT_SECRET" \
    "SERVICE_ACCOUNT_SECRET" \
    "Service account secret for API access"

echo "════════════════════════════════════════"
echo ""
echo "✅ GitHub Secrets Setup Complete!"
echo ""
echo "You can view your secrets at:"
echo "  https://github.com/$REPO/settings/secrets/actions"
echo ""
echo "To verify secrets were set:"
echo "  gh secret list --repo $REPO"
echo ""
echo "════════════════════════════════════════"
echo ""

# List current secrets
echo "Current secrets in repository:"
gh secret list --repo "$REPO"
