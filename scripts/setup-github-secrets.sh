#!/bin/bash
# Setup GitHub Secrets for GKE Deployment
# This script uses GitHub CLI (gh) to add required secrets to the repository

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

# Function to add a secret
add_secret() {
    local secret_name=$1
    local secret_description=$2
    local default_value=$3

    echo "─────────────────────────────────────────"
    echo "Setting: $secret_name"
    echo "Description: $secret_description"
    echo ""

    if [ -n "$default_value" ]; then
        read -p "Enter value (or press Enter for default): " secret_value
        if [ -z "$secret_value" ]; then
            secret_value="$default_value"
        fi
    else
        read -p "Enter value: " secret_value
    fi

    if [ -z "$secret_value" ]; then
        echo "⚠️  Skipping $secret_name (no value provided)"
        echo ""
        return
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

# Load environment variables from .env.dev if it exists
if [ -f "backend/.env.dev" ]; then
    echo "📄 Found backend/.env.dev - loading values..."
    source backend/.env.dev
fi

# 2. Supabase URL (Dev)
add_secret \
    "SUPABASE_URL_DEV" \
    "Supabase project URL for dev environment" \
    "${SUPABASE_URL:-}"

# 3. Supabase Anon Key (Dev)
add_secret \
    "SUPABASE_ANON_KEY_DEV" \
    "Supabase anonymous key for dev environment" \
    "${SUPABASE_ANON_KEY:-}"

# 4. Supabase Service Key (Dev)
add_secret \
    "SUPABASE_SERVICE_KEY_DEV" \
    "Supabase service role key for dev environment" \
    "${SUPABASE_SERVICE_KEY:-}"

# 5. JWT Secret (Dev)
add_secret \
    "JWT_SECRET_DEV" \
    "JWT secret for dev environment authentication" \
    "${JWT_SECRET:-}"

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
