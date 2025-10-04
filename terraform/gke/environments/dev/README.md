# GKE Autopilot - Dev Environment

This directory contains Terraform configuration for the **development** GKE Autopilot cluster.

## Quick Start

### 1. Prerequisites

```bash
# Install required tools
brew install --cask google-cloud-sdk
brew install terraform kubectl

# Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

### 2. Configure

```bash
# Copy example file
cp terraform.tfvars.example terraform.tfvars

# Edit with your GCP project ID
vim terraform.tfvars
```

**Minimum required:**
```hcl
project_id = "your-gcp-project-id"
```

### 3. Deploy

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy cluster
terraform apply

# This takes ~5-10 minutes for Autopilot cluster creation
# Network setup (secondary IP ranges) is handled automatically by Terraform
```

### 4. Configure kubectl

```bash
# Get credentials
terraform output -raw kubectl_config_command | bash

# Verify connection
kubectl get nodes
kubectl cluster-info
```

### 5. Deploy Application

```bash
# Navigate to helm directory
cd ../../../../helm

# Deploy to dev cluster
helm upgrade --install missing-table ./missing-table \
  --namespace missing-table-dev \
  --create-namespace \
  --values ./missing-table/values-dev.yaml

# Check deployment
kubectl get pods -n missing-table-dev
```

## Cluster Details

**Dev Cluster Configuration:**
- **Name**: `missing-table-dev`
- **Type**: GKE Autopilot
- **Region**: `us-central1` (default)
- **Release Channel**: `REGULAR`
- **Workload Identity**: Enabled
- **Labels**: `environment=dev`, `app=missing-table`

**Cost Estimate (Dev):**
- Backend pod: ~$15/month
- Frontend pod: ~$7/month
- **Total**: ~$22/month (covered by GCP free tier)

## Common Operations

### View Cluster Info

```bash
terraform output
terraform output cluster_name
terraform output kubectl_config_command
```

### Update Cluster

```bash
# Edit terraform.tfvars or variables
vim terraform.tfvars

# Preview and apply changes
terraform plan
terraform apply
```

### Access Cluster

```bash
# Re-configure kubectl (if needed)
gcloud container clusters get-credentials missing-table-dev \
  --region us-central1 \
  --project YOUR_PROJECT_ID

# View cluster in GCP Console
gcloud container clusters describe missing-table-dev --region us-central1
```

### Destroy Cluster

**⚠️ WARNING: This will delete the dev cluster!**

```bash
# Destroy infrastructure
terraform destroy
```

## Troubleshooting

### API not enabled

```bash
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

### Permission denied

```bash
# Re-authenticate
gcloud auth application-default login
gcloud auth login

# Verify project
gcloud config get-value project
```

## Next Steps

1. ✅ Deploy dev GKE cluster
2. Configure kubectl access
3. Create Helm values for dev environment
4. Deploy application to dev
5. Test application in dev cluster
6. Set up CI/CD pipeline for dev deployments
7. When ready, copy this config to `../prod/` for production

## Remote State (Recommended)

For team collaboration:

```bash
# Create GCS bucket for state
gsutil mb -p YOUR_PROJECT_ID gs://YOUR-PROJECT-ID-terraform-state

# Enable versioning
gsutil versioning set on gs://YOUR-PROJECT-ID-terraform-state

# Uncomment backend configuration in main.tf
# Update bucket name and prefix
```

## Resources

- [GKE Autopilot Docs](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [GKE Pricing Calculator](https://cloud.google.com/products/calculator)
