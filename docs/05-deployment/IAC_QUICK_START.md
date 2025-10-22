# Infrastructure as Code - Quick Start Guide

**For the complete migration plan, see:** [IAC_MIGRATION_PLAN.md](./IAC_MIGRATION_PLAN.md)

## TL;DR

Convert manual infrastructure setup to Terraform in 6 phases over 6 weeks:

1. **Foundation** - GKE, networking, static IPs
2. **K8s Base** - Namespaces, RBAC
3. **Secrets** - External Secrets Operator + Google Secret Manager
4. **Ingress** - SSL certificates, load balancers
5. **Helm** - Integrate with Terraform-managed infra
6. **CI/CD** - Automated Terraform deployments

## Proposed Directory Structure

```
missing-table/
├── terraform/
│   ├── 00-bootstrap/         # GCP project setup (run once)
│   ├── 01-foundation/        # GKE, networking, IAM
│   ├── 02-kubernetes-base/   # Namespaces, RBAC
│   ├── 03-kubernetes-dev/    # Dev environment resources
│   ├── 04-kubernetes-prod/   # Prod environment resources
│   └── modules/              # Reusable modules
│       ├── gke-autopilot/
│       ├── static-ip/
│       ├── managed-cert/
│       ├── gke-ingress/
│       └── external-secrets/
├── helm/                     # Application deployments (unchanged)
└── docs/
    └── 05-deployment/
        ├── IAC_MIGRATION_PLAN.md  # This comprehensive plan
        └── IAC_QUICK_START.md     # You are here
```

## Stack Dependencies

```
00-bootstrap (run once)
    ↓
01-foundation (GCP resources)
    ↓
02-kubernetes-base (namespaces)
    ↓
    ├─→ 03-kubernetes-dev (dev ingress, secrets)
    └─→ 04-kubernetes-prod (prod ingress, secrets)
```

## What Each Stack Manages

### 00-bootstrap
- Enable GCP APIs
- Create Terraform state GCS bucket
- Set up service accounts for Terraform

### 01-foundation
- GKE Autopilot cluster (`missing-table-dev`)
- Static IPs (`missing-table-dev-ip`, `missing-table-prod-ip`)
- Artifact Registry
- IAM roles and service accounts
- VPC networking

### 02-kubernetes-base
- Namespaces (`missing-table-dev`, `missing-table-prod`)
- RBAC roles and bindings
- Workload Identity configuration
- External Secrets Operator installation

### 03-kubernetes-dev (per-environment)
- ManagedCertificate (`missing-table-dev-cert`)
- Ingress (`missing-table-ingress`)
- ExternalSecret resources (sync from Secret Manager)
- Dev-specific ConfigMaps

### 04-kubernetes-prod (per-environment)
- ManagedCertificate (`missing-table-prod-cert`)
- Ingress (`missing-table-ingress`)
- ExternalSecret resources (sync from Secret Manager)
- Prod-specific ConfigMaps

## Key Decisions

### 1. Secrets Management: External Secrets Operator

**Why?**
- No secrets in Terraform state
- Centralized in Google Secret Manager
- Automatic K8s sync
- Audit logging

**How it works:**
```
Google Secret Manager (source of truth)
    ↓ (ESO syncs every 1h)
Kubernetes Secret (missing-table-secrets)
    ↓ (mounted as env vars)
Application pods
```

### 2. Terraform vs Helm Boundary

**Terraform Manages:**
- GCP infrastructure (GKE, IPs, networks)
- Kubernetes infrastructure (namespaces, ingress, SSL)
- Secrets infrastructure (ESO, Secret Manager)

**Helm Manages:**
- Application deployments (backend, frontend)
- Application services
- Application ConfigMaps

**Why this split?**
- Infrastructure changes are infrequent, reviewed carefully
- Application deployments are frequent, need fast CI/CD
- Clear separation of concerns

### 3. State Management

**State Storage:** Google Cloud Storage bucket
- Encryption at rest
- Versioning enabled
- IAM-restricted access

**State Locking:** GCS native locking
- Prevents concurrent modifications
- Automatic lock cleanup

## Migration Safety

### Import, Don't Recreate

```bash
# SAFE: Import existing resource
terraform import google_container_cluster.primary \
  projects/missing-table/locations/us-central1/clusters/missing-table-dev

# DANGEROUS: Would destroy and recreate
# terraform apply (on new resource)
```

### Verify Before Apply

```bash
# Always run plan first
terraform plan

# Look for these danger signs:
# - Resources being destroyed
# - Unexpected changes
# - Replacement instead of update
```

### Backup Everything

```bash
# Before migration, backup all resources
kubectl get all -A -o yaml > backups/k8s-all-resources.yaml
kubectl get ingress -A -o yaml > backups/k8s-ingress.yaml
kubectl get managedcertificate -A -o yaml > backups/k8s-certs.yaml
kubectl get secrets -A -o yaml > backups/k8s-secrets.yaml
```

## Quick Commands

### Initialize a Stack

```bash
cd terraform/01-foundation
terraform init
terraform plan
terraform apply
```

### Import Existing Resources

```bash
# Import GKE cluster
terraform import google_container_cluster.primary \
  projects/missing-table/locations/us-central1/clusters/missing-table-dev

# Import static IP
terraform import google_compute_global_address.dev_ip \
  projects/missing-table/global/addresses/missing-table-dev-ip

# Import namespace
terraform import kubernetes_namespace.dev missing-table-dev

# Import ingress
terraform import kubernetes_ingress_v1.dev \
  missing-table-dev/missing-table-ingress
```

### Check Drift

```bash
# See if manual changes were made
terraform plan

# If drift detected, update code to match reality
# OR refresh state and apply to fix drift
terraform refresh
terraform apply
```

### Rollback

```bash
# Revert to previous state version
gsutil cp gs://missing-table-terraform-state/default.tfstate.backup \
  gs://missing-table-terraform-state/default.tfstate

terraform refresh
```

## Security Checklist

- [ ] Terraform state bucket has IAM restrictions
- [ ] Terraform state bucket has versioning enabled
- [ ] No secrets in Terraform files (use Secret Manager)
- [ ] Service accounts follow least privilege
- [ ] All IAM bindings documented in code
- [ ] Secret Manager has audit logging enabled
- [ ] Workload Identity used for K8s → GCP access

## Next Steps

1. **Read the full plan:** [IAC_MIGRATION_PLAN.md](./IAC_MIGRATION_PLAN.md)
2. **Create bootstrap stack:** Start with `00-bootstrap/`
3. **Import foundation:** Import GKE cluster and networking
4. **Test incremental migration:** One stack at a time
5. **Update documentation:** As you go

## Getting Help

- **Terraform Docs:** https://www.terraform.io/docs
- **GCP Provider:** https://registry.terraform.io/providers/hashicorp/google/latest/docs
- **Kubernetes Provider:** https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs
- **External Secrets:** https://external-secrets.io/

---

**Last Updated:** 2025-10-18
