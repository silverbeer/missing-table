# GCP Infrastructure Deployment Guide

This guide provides detailed step-by-step instructions for deploying the Missing Table application infrastructure on Google Cloud Platform.

## 🎯 Prerequisites Checklist

Before starting the deployment, ensure you have completed the following:

### Required Tools
- [ ] **Google Cloud SDK** (gcloud) installed and configured
- [ ] **Terraform** >= 1.0.0 installed
- [ ] **kubectl** installed for Kubernetes management
- [ ] **Git** for version control
- [ ] **Docker** for local testing (optional)

### GCP Account Setup
- [ ] Google Cloud account with billing enabled
- [ ] GCP project created or selected
- [ ] Billing account linked to the project
- [ ] Appropriate IAM permissions (Project Owner or Editor)
- [ ] Organization-level permissions (if using organization policies)

### Verification Commands
```bash
# Verify gcloud installation and authentication
gcloud version
gcloud auth list
gcloud config get-value project

# Verify Terraform installation
terraform version

# Verify kubectl installation
kubectl version --client
```

## 🔧 Initial Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd missing-table/gcp
```

### 2. Set Up Environment Variables

Create a `.env` file (never commit this to version control):
```bash
# .env file
export TF_VAR_project_id="your-gcp-project-id"
export TF_VAR_billing_account_id="123456-ABCDEF-GHIJKL"
export TF_VAR_admin_email="admin@yourdomain.com"
export TF_VAR_security_contact_email="security@yourdomain.com"
export TF_VAR_devops_contact_email="devops@yourdomain.com"
export TF_VAR_alert_email="alerts@yourdomain.com"
export TF_VAR_organization_id=""  # Optional: your organization ID
```

Load the environment variables:
```bash
source .env
```

### 3. Configure Terraform Backend (Recommended)

Create a Cloud Storage bucket for Terraform state:
```bash
gsutil mb gs://${TF_VAR_project_id}-terraform-state
gsutil versioning set on gs://${TF_VAR_project_id}-terraform-state
```

Update `terraform/main.tf` backend configuration:
```hcl
terraform {
  backend "gcs" {
    bucket = "your-project-id-terraform-state"
    prefix = "terraform/state"
  }
}
```

## 🚀 Deployment Process

### Phase 1: Core Infrastructure

#### Step 1: Initialize Terraform
```bash
cd terraform
terraform init
```

Expected output:
```
Terraform has been successfully initialized!
```

#### Step 2: Validate Configuration
```bash
terraform validate
```

#### Step 3: Plan Deployment
```bash
terraform plan -var-file="terraform.tfvars" -out=tfplan
```

Review the plan carefully, ensuring:
- [ ] All required resources are being created
- [ ] No unexpected deletions or modifications
- [ ] Security policies are correctly configured
- [ ] Cost estimates are within budget

#### Step 4: Apply Configuration
```bash
terraform apply tfplan
```

**Expected Duration**: 15-20 minutes

Monitor the deployment progress and address any errors immediately.

### Phase 2: Verification

#### Step 1: Verify Core Services
```bash
# Check project APIs
gcloud services list --enabled --project=${TF_VAR_project_id}

# Verify service accounts
gcloud iam service-accounts list --project=${TF_VAR_project_id}

# Check KMS keys
gcloud kms keys list --location=global --keyring=missing-table-production-keyring
```

#### Step 2: Verify GKE Cluster
```bash
# Get cluster credentials
gcloud container clusters get-credentials missing-table-production-cluster \
  --region us-central1 --project ${TF_VAR_project_id}

# Verify cluster status
kubectl cluster-info
kubectl get nodes

# Check node pool status
gcloud container node-pools list --cluster=missing-table-production-cluster \
  --region=us-central1
```

#### Step 3: Verify Secret Manager
```bash
# List secrets
gcloud secrets list --project=${TF_VAR_project_id}

# Test secret access (should fail without proper permissions)
gcloud secrets versions access latest --secret="missing-table-production-jwt-secret"
```

#### Step 4: Verify Monitoring
```bash
# Check monitoring workspace
gcloud alpha monitoring policies list --project=${TF_VAR_project_id}

# List notification channels
gcloud alpha monitoring channels list --project=${TF_VAR_project_id}
```

### Phase 3: Application Deployment

#### Step 1: Configure Workload Identity
```bash
# Create Kubernetes service account
kubectl create serviceaccount missing-table-backend \
  --namespace missing-table

# Bind to Google service account
gcloud iam service-accounts add-iam-policy-binding \
  missing-table-production-backend@${TF_VAR_project_id}.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${TF_VAR_project_id}.svc.id.goog[missing-table/missing-table-backend]"

# Annotate Kubernetes service account
kubectl annotate serviceaccount missing-table-backend \
  --namespace missing-table \
  iam.gke.io/gcp-service-account=missing-table-production-backend@${TF_VAR_project_id}.iam.gserviceaccount.com
```

#### Step 2: Deploy Application Manifests
```bash
# Apply Kubernetes manifests
kubectl apply -f ../k8s/production/

# Verify deployment
kubectl get pods -n missing-table
kubectl get services -n missing-table
```

### Phase 4: CI/CD Setup

#### Step 1: Configure GitHub Secrets

In your GitHub repository settings, add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `GCP_PROJECT_ID` | Your project ID | GCP project identifier |
| `WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider` | Workload Identity provider |
| `WIF_SERVICE_ACCOUNT` | `missing-table-production-cicd@PROJECT_ID.iam.gserviceaccount.com` | CI/CD service account |
| `ADMIN_EMAIL` | admin@yourdomain.com | Admin contact |
| `SECURITY_CONTACT_EMAIL` | security@yourdomain.com | Security contact |
| `DEVOPS_CONTACT_EMAIL` | devops@yourdomain.com | DevOps contact |
| `ALERT_EMAIL` | alerts@yourdomain.com | Alert notifications |
| `BILLING_ACCOUNT_ID` | Your billing account ID | GCP billing account |
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL | Notification endpoint |

#### Step 2: Test CI/CD Pipeline
```bash
# Push a test commit to trigger the pipeline
git add .
git commit -m "test: trigger CI/CD pipeline"
git push origin main
```

Monitor the GitHub Actions workflow for successful execution.

## 🔍 Post-Deployment Verification

### Security Verification
```bash
# Check Binary Authorization policy
gcloud container binauthz policy export

# Verify firewall rules
gcloud compute firewall-rules list --project=${TF_VAR_project_id}

# Check IAM policies
gcloud projects get-iam-policy ${TF_VAR_project_id}
```

### Monitoring Verification
```bash
# Test alert policies
gcloud alpha monitoring policies list --project=${TF_VAR_project_id}

# Check dashboard creation
# Navigate to Cloud Monitoring console and verify dashboards exist
```

### Cost Verification
```bash
# Check budget configuration
gcloud billing budgets list --billing-account=${TF_VAR_billing_account_id}

# Verify cost optimization function
gcloud functions list --project=${TF_VAR_project_id}
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Issue: API Not Enabled
```
Error: Error when reading or editing Project Service
```

**Solution**:
```bash
# Enable required APIs manually
gcloud services enable container.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### Issue: Insufficient Permissions
```
Error: Error applying IAM policy for project
```

**Solution**:
```bash
# Verify your permissions
gcloud projects get-iam-policy ${TF_VAR_project_id} \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:$(gcloud config get-value account)"
```

#### Issue: Resource Quota Exceeded
```
Error: Quota 'CPUS' exceeded
```

**Solution**:
```bash
# Check quotas
gcloud compute regions describe us-central1 --project=${TF_VAR_project_id}

# Request quota increase through GCP Console
```

#### Issue: GKE Cluster Creation Fails
```
Error: Error waiting for creating GKE cluster
```

**Solution**:
```bash
# Check cluster status
gcloud container operations list --project=${TF_VAR_project_id}

# Review detailed error logs in GCP Console
```

### Rollback Procedures

#### Complete Infrastructure Rollback
```bash
# Destroy all infrastructure (USE WITH CAUTION)
terraform destroy -var-file="terraform.tfvars"
```

#### Partial Rollback
```bash
# Target specific resources for destruction
terraform destroy -target=google_container_cluster.main -var-file="terraform.tfvars"
```

## 📋 Verification Checklist

After deployment, verify the following:

### Infrastructure
- [ ] GCP project configured with all required APIs enabled
- [ ] Service accounts created with appropriate permissions
- [ ] KMS keys created and accessible
- [ ] VPC and subnets configured correctly
- [ ] GKE cluster running with correct node pools

### Security
- [ ] Binary Authorization policy enforced
- [ ] Workload Identity configured
- [ ] Secret Manager secrets created and encrypted
- [ ] Firewall rules properly configured
- [ ] Audit logging enabled

### Monitoring
- [ ] Alert policies configured and enabled
- [ ] Notification channels working
- [ ] Dashboards accessible
- [ ] SLOs configured correctly

### Cost Management
- [ ] Budget alerts configured
- [ ] Cost optimization function deployed
- [ ] Resource labels applied correctly

### CI/CD
- [ ] GitHub Actions workflow functional
- [ ] Security scanning enabled
- [ ] Deployment pipeline working
- [ ] Notifications configured

## 📞 Support

If you encounter issues during deployment:

1. **Check the troubleshooting section** above
2. **Review Terraform logs** for detailed error messages
3. **Consult GCP documentation** for service-specific issues
4. **Contact the development team** with specific error messages and context

## 🔄 Next Steps

After successful deployment:

1. **Configure monitoring alerts** based on your specific requirements
2. **Set up regular backup procedures** for critical data
3. **Implement disaster recovery testing** procedures
4. **Schedule regular security reviews** and updates
5. **Monitor costs** and optimize as needed

---

**Important**: This deployment creates production-grade infrastructure with associated costs. Monitor your billing dashboard regularly and set up appropriate budget alerts.