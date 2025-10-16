#!/bin/bash
#
# Setup GitHub Secrets for Production Deployment
#
# This script provides the commands to add required secrets to your GitHub repository.
# You'll need the GitHub CLI (`gh`) installed and authenticated.
#
# Install GitHub CLI:
#   brew install gh
#   gh auth login
#

set -e

REPO="silverbeer/missing-table"  # Update this!

echo "=================================================="
echo "GitHub Secrets Setup for Production"
echo "=================================================="
echo ""
echo "⚠️  IMPORTANT: Update the REPO variable in this script first!"
echo "   Current: ${REPO}"
echo ""
echo "This script will guide you through adding secrets."
echo "You can also add them manually at:"
echo "https://github.com/${REPO}/settings/secrets/actions"
echo ""

read -p "Press Enter to continue..."

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found!"
    echo "Install it with: brew install gh"
    echo "Then authenticate: gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated to GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo ""
echo "✅ GitHub CLI is ready"
echo ""

# Function to add secret
add_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=$3

    echo "=================================================="
    echo "Adding: ${secret_name}"
    echo "Description: ${description}"
    echo "=================================================="

    if [ -z "${secret_value}" ]; then
        echo "⚠️  Value is empty, skipping..."
        return
    fi

    echo "${secret_value}" | gh secret set "${secret_name}" --repo="${REPO}"

    if [ $? -eq 0 ]; then
        echo "✅ ${secret_name} added successfully"
    else
        echo "❌ Failed to add ${secret_name}"
    fi

    echo ""
}

# Load production environment variables
if [ -f "backend/.env.prod" ]; then
    echo "📄 Loading from backend/.env.prod..."
    source backend/.env.prod
else
    echo "❌ backend/.env.prod not found!"
    exit 1
fi

# Add all secrets
echo ""
echo "Adding production secrets..."
echo ""

# GCP Secrets (you need to provide these manually)
echo "=================================================="
echo "GCP Secrets"
echo "=================================================="
echo ""
echo "⚠️  You need to add these manually as they're not in .env files:"
echo ""
echo "1. GCP_PROJECT_ID"
echo "   gh secret set GCP_PROJECT_ID --repo=${REPO}"
echo "   Value: missing-table"
echo ""
echo "2. GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "   Get from: gcloud iam workload-identity-pools providers describe github-actions ..."
echo ""
echo "3. GCP_SERVICE_ACCOUNT"
echo "   Value: github-actions@missing-table.iam.gserviceaccount.com"
echo ""
read -p "Press Enter when you've added these (or skip for now)..."

# Database secrets
add_secret "PROD_DATABASE_URL" "${DATABASE_URL}" "Production database connection string"
add_secret "PROD_SUPABASE_URL" "${SUPABASE_URL}" "Production Supabase URL"
add_secret "PROD_SUPABASE_ANON_KEY" "${SUPABASE_ANON_KEY}" "Production Supabase anon key"
add_secret "PROD_SUPABASE_SERVICE_KEY" "${SUPABASE_SERVICE_KEY}" "Production Supabase service role key"
add_secret "PROD_SUPABASE_JWT_SECRET" "${SUPABASE_JWT_SECRET}" "Production Supabase JWT secret"

# Security secret
add_secret "PROD_SERVICE_ACCOUNT_SECRET" "${SERVICE_ACCOUNT_SECRET}" "Production service account secret"

echo ""
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="
echo ""
echo "Secrets added to: ${REPO}"
echo ""
echo "Verify secrets at:"
echo "https://github.com/${REPO}/settings/secrets/actions"
echo ""
echo "Next steps:"
echo "1. Configure DNS in Namecheap (see docs/PRODUCTION_DEPLOYMENT.md)"
echo "2. Commit and push the workflow file"
echo "3. Trigger deployment via GitHub Actions"
echo ""
