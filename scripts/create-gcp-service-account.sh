#!/bin/bash
# Create GCP Service Account for GitHub Actions
# This script creates a service account with the necessary permissions for GKE deployment

set -e

PROJECT_ID="missing-table"
SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="gcp-github-actions-key.json"

echo "=========================================="
echo "GCP Service Account Setup for GitHub Actions"
echo "=========================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Service Account: $SA_EMAIL"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed."
    echo "Install it with: brew install google-cloud-sdk"
    exit 1
fi

# Set project
echo "Setting GCP project..."
gcloud config set project $PROJECT_ID

# Create service account
echo ""
echo "Creating service account: $SA_NAME..."
gcloud iam service-accounts create $SA_NAME \
    --display-name="GitHub Actions Deployer" \
    --description="Service account for GitHub Actions to deploy to GKE" \
    || echo "Service account already exists"

# Grant necessary roles
echo ""
echo "Granting IAM roles..."

roles=(
    "roles/container.admin"           # GKE cluster management
    "roles/storage.admin"             # Artifact Registry
    "roles/iam.serviceAccountUser"    # Service account usage
    "roles/artifactregistry.admin"    # Artifact Registry admin
)

for role in "${roles[@]}"; do
    echo "  - Granting $role..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role" \
        --quiet
done

# Create key file
echo ""
echo "Creating service account key..."
gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$SA_EMAIL

echo ""
echo "✅ Service account key created: $KEY_FILE"
echo ""
echo "════════════════════════════════════════"
echo "Next Steps:"
echo "════════════════════════════════════════"
echo ""
echo "1. Set the GitHub secret using the key file:"
echo "   gh secret set GCP_SA_KEY < $KEY_FILE"
echo ""
echo "2. Securely delete the key file:"
echo "   rm $KEY_FILE"
echo ""
echo "⚠️  IMPORTANT: Keep this key file secure and delete it after use!"
echo ""
