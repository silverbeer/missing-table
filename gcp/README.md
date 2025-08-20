# GCP Infrastructure for Missing Table Application

This directory contains the complete Google Cloud Platform (GCP) infrastructure configuration for the Missing Table application, implemented with security-first principles and comprehensive monitoring.

## 🏗️ Architecture Overview

The infrastructure consists of:

- **Security-hardened GKE cluster** with private nodes and Workload Identity
- **Multi-region Secret Manager** with customer-managed encryption
- **Binary Authorization** with container image attestation
- **VPC with private networking** and controlled ingress/egress
- **Comprehensive monitoring** with SLOs and alerting
- **Automated cost optimization** with billing alerts
- **CI/CD pipeline** with security scanning and attestation

## 📁 Directory Structure

```
gcp/
├── terraform/                 # Infrastructure as Code
│   ├── main.tf               # Core project setup and security policies
│   ├── variables.tf          # Variable definitions with validation
│   ├── apis.tf               # API management with dependencies
│   ├── service-accounts.tf   # Service accounts with Workload Identity
│   ├── billing.tf            # Cost monitoring and optimization
│   ├── security.tf           # VPC, Binary Auth, Security Command Center
│   ├── secrets.tf            # Secret Manager with IAM and rotation
│   ├── gke.tf                # Secure GKE cluster configuration
│   ├── monitoring.tf         # Comprehensive monitoring and alerting
│   └── terraform.tfvars      # Environment-specific variables
├── k8s/                      # Kubernetes manifests
│   ├── staging/              # Staging environment
│   └── production/           # Production environment
├── functions/                # Cloud Functions
│   └── cost-optimization/    # Automated cost management
└── README.md                 # This documentation
```

## 🚀 Quick Start

### Prerequisites

1. **Google Cloud SDK** installed and configured
2. **Terraform** >= 1.0 installed
3. **kubectl** installed for GKE management
4. Required **GCP APIs** enabled (automated via Terraform)
5. **Billing account** set up and linked

### Environment Variables

Set these environment variables before deployment:

```bash
export TF_VAR_project_id="your-gcp-project-id"
export TF_VAR_billing_account_id="your-billing-account-id"
export TF_VAR_admin_email="admin@yourdomain.com"
export TF_VAR_security_contact_email="security@yourdomain.com"
export TF_VAR_devops_contact_email="devops@yourdomain.com"
export TF_VAR_alert_email="alerts@yourdomain.com"
```

### Deployment Steps

1. **Initialize Terraform**:
   ```bash
   cd gcp/terraform
   terraform init
   ```

2. **Review the plan**:
   ```bash
   terraform plan -var-file="terraform.tfvars"
   ```

3. **Deploy infrastructure**:
   ```bash
   terraform apply -var-file="terraform.tfvars"
   ```

4. **Configure kubectl** for GKE:
   ```bash
   gcloud container clusters get-credentials missing-table-production-cluster \
     --region us-central1 --project your-project-id
   ```

## 🔐 Security Features

### Authentication & Authorization
- **Workload Identity Federation** for GitHub Actions
- **Service accounts** with minimal required permissions
- **IAM policies** following least privilege principle
- **Binary Authorization** for container image security

### Network Security
- **Private GKE cluster** with authorized networks
- **VPC with private subnets** and controlled routing
- **Cloud NAT** for secure outbound internet access
- **Firewall rules** with default deny and explicit allows

### Data Protection
- **Secret Manager** with customer-managed encryption (CMEK)
- **Automated secret rotation** every 90 days
- **Database encryption** at rest and in transit
- **Audit logging** for all secret access

### Container Security
- **Binary Authorization** requiring attestations
- **Shielded GKE nodes** with secure boot
- **Container image scanning** in CI/CD pipeline
- **Pod Security Policies** (where supported)

## 📊 Monitoring & Alerting

### Key Metrics Monitored
- Application error rates and authentication failures
- GKE cluster health and node readiness
- Resource utilization (CPU, memory, disk)
- Security events and Binary Authorization violations
- Cost trends and budget thresholds

### Alert Policies
- **High error rate** (>10 errors/5min) → Operations team
- **Authentication attacks** (>20 failures/5min) → Security team
- **Database connectivity** issues → Operations team
- **Resource exhaustion** → Operations team
- **Security violations** → Security team
- **Budget thresholds** → All stakeholders

### Dashboards
- **Application Dashboard**: Performance and health metrics
- **Security Dashboard**: Security events and compliance
- **Cost Dashboard**: Spending trends and optimization

## 💰 Cost Management

### Automated Cost Controls
- **Budget alerts** at 50%, 80%, and 100% thresholds
- **Cloud Function** for automated cost optimization
- **Resource lifecycle policies** for log retention
- **Image cleanup** in CI/CD pipeline
- **Preemptible instances** for non-production workloads

### Cost Optimization Features
- **Rightsize recommendations** via Cloud Functions
- **Unused resource detection** and alerts
- **Regional resource placement** for lower costs
- **Storage class transitions** for long-term data

## 🔧 Operations Guide

### Accessing Services

1. **GKE Cluster**:
   ```bash
   gcloud container clusters get-credentials missing-table-production-cluster \
     --region us-central1 --project your-project-id
   ```

2. **Secrets**:
   ```bash
   gcloud secrets versions access latest --secret="missing-table-production-database-url"
   ```

3. **Monitoring**:
   - Navigate to Cloud Monitoring in GCP Console
   - Use custom dashboards created by Terraform

### Common Tasks

#### Updating Secrets
```bash
echo "new-secret-value" | gcloud secrets versions add secret-name --data-file=-
```

#### Scaling GKE Cluster
```bash
gcloud container clusters resize missing-table-production-cluster \
  --num-nodes 5 --region us-central1
```

#### Viewing Logs
```bash
kubectl logs -f deployment/missing-table-backend -n missing-table
```

### Troubleshooting

#### Common Issues

1. **Binary Authorization Denials**:
   - Check attestation status in Security Dashboard
   - Verify CI/CD pipeline completed successfully
   - Review Binary Authorization policy configuration

2. **Pod Startup Failures**:
   - Check secret access permissions
   - Verify Workload Identity configuration
   - Review resource quotas and limits

3. **Network Connectivity**:
   - Verify firewall rules and VPC configuration
   - Check Cloud NAT and routing configuration
   - Review authorized networks for GKE master

## 🚀 CI/CD Pipeline

### GitHub Actions Workflow

The pipeline includes:

1. **Security Scanning**:
   - Trivy for vulnerability scanning
   - Hadolint for Dockerfile linting
   - Checkov for infrastructure security

2. **Infrastructure Validation**:
   - Terraform format and validation
   - Plan generation and review
   - Security policy compliance

3. **Container Build & Push**:
   - Multi-stage secure builds
   - Image vulnerability scanning
   - Artifact Registry storage

4. **Deployment**:
   - Staging environment deployment
   - Production deployment with approvals
   - Binary Authorization attestation

5. **Post-Deployment**:
   - Health checks and smoke tests
   - Notification to Slack/Teams
   - Image cleanup and retention

### Required Secrets

Configure these in GitHub repository settings:

```
GCP_PROJECT_ID              # Your GCP project ID
WIF_PROVIDER                # Workload Identity Federation provider
WIF_SERVICE_ACCOUNT         # Service account email for WIF
ADMIN_EMAIL                 # Admin contact email
SECURITY_CONTACT_EMAIL      # Security contact email
DEVOPS_CONTACT_EMAIL        # DevOps contact email
ALERT_EMAIL                 # Alert notification email
BILLING_ACCOUNT_ID          # GCP billing account ID
SLACK_WEBHOOK_URL           # Slack notification webhook
```

## 🔄 Backup & Recovery

### Automated Backups
- **GKE cluster configuration** backed up via Terraform state
- **Secrets** replicated across multiple regions
- **Application logs** archived to Cloud Storage
- **Monitoring data** retained per configured policies

### Recovery Procedures

1. **Infrastructure Recovery**:
   ```bash
   cd gcp/terraform
   terraform apply -var-file="terraform.tfvars"
   ```

2. **Application Recovery**:
   ```bash
   kubectl apply -f gcp/k8s/production/
   ```

3. **Secret Recovery**:
   - Secrets are automatically replicated
   - Use Secret Manager version history for rollback

## 📋 Compliance & Security

### Security Standards
- **CIS Google Cloud Platform Benchmark** compliance
- **NIST Cybersecurity Framework** alignment
- **SOC 2 Type II** controls implementation
- **GDPR/CCPA** data protection measures

### Audit Trail
- **Cloud Audit Logs** for all API calls
- **Secret Manager access** logging
- **VPC Flow Logs** for network analysis
- **Binary Authorization** decision logs

### Regular Security Tasks
- **Vulnerability scanning** (automated in CI/CD)
- **Security policy reviews** (quarterly)
- **Access reviews** (monthly)
- **Incident response testing** (semi-annually)

## 🆘 Support & Contacts

### Escalation Matrix

| Issue Type | Contact | Response Time |
|------------|---------|---------------|
| Security Incident | security@yourdomain.com | 15 minutes |
| Production Outage | devops@yourdomain.com | 30 minutes |
| Cost Alert | admin@yourdomain.com | 2 hours |
| General Issues | alerts@yourdomain.com | 4 hours |

### External Resources
- [GCP Security Best Practices](https://cloud.google.com/security/best-practices)
- [GKE Security Guide](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster)
- [Binary Authorization Documentation](https://cloud.google.com/binary-authorization/docs)
- [Workload Identity Guide](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)

---

## 📄 License

This infrastructure configuration is part of the Missing Table application and follows the same licensing terms.

---

**Note**: This infrastructure implements security-first principles and comprehensive monitoring. Regular reviews and updates are recommended to maintain security posture and operational efficiency.