# Infrastructure as Code Migration Plan

**⚠️ NOTE:** This document references the old infrastructure architecture (separate dev/prod environments, GCE ingress, ManagedCertificate). As of 2025-11-14, infrastructure has been consolidated:
- ✅ Single `missing-table-dev` namespace serves all domains
- ✅ nginx ingress replaces GCE ingress
- ✅ cert-manager/Let's Encrypt replaces ManagedCertificate
- ✅ Reduced costs from $283/month to $40/month

**Date:** 2025-10-18
**Status:** Planning (needs update for consolidated infrastructure)
**Goal:** Migrate all manually created infrastructure to Terraform-managed IaC

## Current State: Manual Infrastructure

### What Was Created Manually

#### 1. GCP Resources
- **GKE Autopilot Cluster:** `missing-table-dev` (us-central1)
- **Static IPs:**
  - `missing-table-dev-ip`: 34.8.149.240 (global)
  - `missing-table-prod-ip`: 35.190.120.93 (global)
- **Service Accounts & IAM:**
  - GKE workload identity bindings
  - GitHub Actions service account
  - Artifact Registry permissions

#### 2. Kubernetes Resources (Dev Namespace)
- **Namespace:** `missing-table-dev`
- **Secret:** `missing-table-secrets` (database credentials, Supabase keys)
- **ManagedCertificate:** `missing-table-dev-cert` (dev.missingtable.com)
- **Ingress:** `missing-table-ingress` (with SSL, static IP annotations)
- **Helm ownership labels:** Added manually to support Helm adoption

#### 3. Kubernetes Resources (Prod Namespace)
- **Namespace:** `missing-table-prod`
- **Secret:** `missing-table-secrets` (production credentials)
- **ManagedCertificate:** `missing-table-prod-cert` (missingtable.com, www.missingtable.com)
- **Ingress:** `missing-table-ingress` (with SSL, static IP annotations)

#### 4. GitHub Configuration
- **Repository Secrets:** 18 secrets for dev/prod credentials
- **GitHub Actions Workflows:** Deploy workflows reference manual infrastructure

#### 5. External Services
- **DNS Records:** A records pointing to static IPs (managed in DNS provider)
- **Supabase Projects:** Dev and prod projects with databases

### Known Issues with Current Manual Setup
1. ❌ **Helm ownership conflicts** - Resources lack proper Helm labels/annotations
2. ❌ **Inconsistent naming** - GitHub secrets use `PROD_*` vs workflow expects `*_PROD`
3. ❌ **No disaster recovery** - Infrastructure can't be easily recreated
4. ❌ **No drift detection** - Manual changes go untracked
5. ❌ **Poor documentation** - Setup steps scattered across issues/PRs

---

## Proposed IaC Architecture

### Terraform Stack Organization

```
terraform/
├── 00-bootstrap/          # Initial GCP project setup (run once)
│   ├── main.tf           # Enable APIs, create state bucket
│   ├── outputs.tf
│   └── variables.tf
│
├── 01-foundation/        # Core GCP infrastructure
│   ├── main.tf           # Provider, backend config
│   ├── gke.tf            # GKE Autopilot cluster
│   ├── networking.tf     # VPC, static IPs
│   ├── iam.tf            # Service accounts, IAM bindings
│   ├── artifact-registry.tf  # Docker registry
│   ├── outputs.tf
│   ├── variables.tf
│   └── terraform.tfvars
│
├── 02-kubernetes-base/   # Kubernetes infrastructure (namespace-agnostic)
│   ├── main.tf           # Kubernetes provider
│   ├── namespaces.tf     # Create namespaces
│   ├── rbac.tf           # RBAC roles/bindings
│   ├── outputs.tf
│   └── variables.tf
│
├── 03-kubernetes-dev/    # Dev environment K8s resources
│   ├── main.tf
│   ├── secrets.tf        # External Secrets Operator config
│   ├── ingress.tf        # Ingress + ManagedCertificate
│   ├── outputs.tf
│   └── variables.tf
│
├── 04-kubernetes-prod/   # Prod environment K8s resources
│   ├── main.tf
│   ├── secrets.tf        # External Secrets Operator config
│   ├── ingress.tf        # Ingress + ManagedCertificate
│   ├── outputs.tf
│   └── variables.tf
│
└── modules/              # Reusable Terraform modules
    ├── gke-autopilot/
    ├── static-ip/
    ├── managed-cert/
    ├── gke-ingress/
    └── external-secrets/
```

---

## Migration Strategy

### Phase 1: Bootstrap & Foundation (Week 1)

**Goal:** Set up Terraform state management and import core GCP resources

#### Tasks:
1. **Create bootstrap stack** (`00-bootstrap/`)
   ```hcl
   # Enable required APIs
   - compute.googleapis.com
   - container.googleapis.com
   - artifactregistry.googleapis.com
   - secretmanager.googleapis.com

   # Create Terraform state bucket
   resource "google_storage_bucket" "terraform_state" {
     name     = "missing-table-terraform-state"
     location = "US"
     versioning { enabled = true }
   }
   ```

2. **Create foundation stack** (`01-foundation/`)
   - Import existing GKE cluster
   - Import static IPs
   - Import Artifact Registry
   - Create/import service accounts

3. **Import existing resources:**
   ```bash
   # Import GKE cluster
   terraform import google_container_cluster.primary \
     projects/missing-table/locations/us-central1/clusters/missing-table-dev

   # Import static IPs
   terraform import google_compute_global_address.dev_ip \
     projects/missing-table/global/addresses/missing-table-dev-ip
   terraform import google_compute_global_address.prod_ip \
     projects/missing-table/global/addresses/missing-table-prod-ip
   ```

#### Success Criteria:
- ✅ Terraform state stored in GCS
- ✅ `terraform plan` shows no changes for imported resources
- ✅ Documentation updated with Terraform commands

---

### Phase 2: Kubernetes Base Resources (Week 2)

**Goal:** Manage namespaces and base Kubernetes configuration

#### Tasks:
1. **Create kubernetes-base stack** (`02-kubernetes-base/`)
   ```hcl
   # Namespaces
   resource "kubernetes_namespace" "dev" {
     metadata {
       name = "missing-table-dev"
       labels = {
         environment = "dev"
         managed-by  = "terraform"
       }
     }
   }

   resource "kubernetes_namespace" "prod" {
     metadata {
       name = "missing-table-prod"
       labels = {
         environment = "prod"
         managed-by  = "terraform"
       }
     }
   }
   ```

2. **Import existing namespaces:**
   ```bash
   terraform import kubernetes_namespace.dev missing-table-dev
   terraform import kubernetes_namespace.prod missing-table-prod
   ```

3. **Set up RBAC:**
   - GitHub Actions service account
   - Workload Identity bindings
   - Namespace-scoped roles

#### Success Criteria:
- ✅ Namespaces managed by Terraform
- ✅ RBAC policies codified
- ✅ No manual kubectl operations needed for base resources

---

### Phase 3: Secrets Management (Week 3)

**Goal:** Replace manual Kubernetes Secrets with External Secrets Operator

#### Why External Secrets Operator?
- ✅ Secrets stored in Google Secret Manager (encrypted at rest)
- ✅ No plaintext secrets in Terraform state
- ✅ Automatic sync from Secret Manager to K8s
- ✅ Audit logging for secret access
- ✅ GitHub secrets can also use Secret Manager

#### Tasks:
1. **Install External Secrets Operator (ESO) via Helm:**
   ```bash
   helm repo add external-secrets https://charts.external-secrets.io
   helm install external-secrets external-secrets/external-secrets \
     -n external-secrets-system --create-namespace
   ```

2. **Migrate secrets to Google Secret Manager:**
   ```bash
   # Create secrets in Secret Manager
   echo -n "$DATABASE_URL" | gcloud secrets create prod-database-url --data-file=-
   echo -n "$SUPABASE_URL" | gcloud secrets create prod-supabase-url --data-file=-
   # ... repeat for all secrets
   ```

3. **Create Terraform for ExternalSecret resources:**
   ```hcl
   # 03-kubernetes-dev/secrets.tf
   resource "kubernetes_manifest" "dev_external_secret" {
     manifest = {
       apiVersion = "external-secrets.io/v1beta1"
       kind       = "ExternalSecret"
       metadata = {
         name      = "missing-table-secrets"
         namespace = "missing-table-dev"
       }
       spec = {
         refreshInterval = "1h"
         secretStoreRef = {
           name = "gcpsm-secret-store"
           kind = "SecretStore"
         }
         target = {
           name = "missing-table-secrets"
         }
         data = [
           {
             secretKey = "database-url"
             remoteRef = { key = "dev-database-url" }
           },
           {
             secretKey = "supabase-url"
             remoteRef = { key = "dev-supabase-url" }
           },
           # ... all other secrets
         ]
       }
     }
   }
   ```

4. **Delete manual Kubernetes Secrets:**
   ```bash
   kubectl delete secret missing-table-secrets -n missing-table-dev
   kubectl delete secret missing-table-secrets -n missing-table-prod
   # ESO will recreate them from Secret Manager
   ```

5. **Update GitHub Actions workflows:**
   ```yaml
   # Use Google Secret Manager instead of GitHub secrets
   - name: Get secrets from Secret Manager
     id: secrets
     uses: google-github-actions/get-secretmanager-secrets@v1
     with:
       secrets: |-
         DATABASE_URL:projects/missing-table/secrets/prod-database-url
         SUPABASE_URL:projects/missing-table/secrets/prod-supabase-url
   ```

#### Success Criteria:
- ✅ All secrets in Google Secret Manager
- ✅ No plaintext secrets in GitHub or Terraform
- ✅ ESO syncing secrets to Kubernetes
- ✅ Applications still function correctly

---

### Phase 4: Ingress & SSL (Week 4)

**Goal:** Manage Ingress and ManagedCertificate resources with Terraform

#### Tasks:
1. **Create Terraform modules:**
   ```hcl
   # modules/gke-ingress/main.tf
   resource "kubernetes_manifest" "managed_cert" {
     manifest = {
       apiVersion = "networking.gke.io/v1"
       kind       = "ManagedCertificate"
       metadata = {
         name      = var.cert_name
         namespace = var.namespace
         labels = {
           "app.kubernetes.io/managed-by" = "Terraform"
         }
       }
       spec = {
         domains = var.domains
       }
     }
   }

   resource "kubernetes_ingress_v1" "main" {
     metadata {
       name      = var.ingress_name
       namespace = var.namespace
       annotations = {
         "kubernetes.io/ingress.global-static-ip-name" = var.static_ip_name
         "networking.gke.io/managed-certificates"      = var.cert_name
       }
     }
     spec {
       rule {
         host = var.primary_domain
         http {
           path {
             path = "/api"
             path_type = "Prefix"
             backend {
               service {
                 name = "missing-table-backend"
                 port { number = 8000 }
               }
             }
           }
           # ... other paths
         }
       }
     }
   }
   ```

2. **Use modules in environment stacks:**
   ```hcl
   # 03-kubernetes-dev/ingress.tf
   module "ingress" {
     source = "../../modules/gke-ingress"

     namespace      = "missing-table-dev"
     cert_name      = "missing-table-dev-cert"
     ingress_name   = "missing-table-ingress"
     static_ip_name = "missing-table-dev-ip"
     primary_domain = "dev.missingtable.com"
     domains        = ["dev.missingtable.com"]
   }

   # 04-kubernetes-prod/ingress.tf
   module "ingress" {
     source = "../../modules/gke-ingress"

     namespace      = "missing-table-prod"
     cert_name      = "missing-table-prod-cert"
     ingress_name   = "missing-table-ingress"
     static_ip_name = "missing-table-prod-ip"
     primary_domain = "missingtable.com"
     domains        = ["missingtable.com", "www.missingtable.com"]
   }
   ```

3. **Import existing resources:**
   ```bash
   # Import ManagedCertificate (custom resource)
   terraform import kubernetes_manifest.dev_cert \
     "apiVersion=networking.gke.io/v1,kind=ManagedCertificate,namespace=missing-table-dev,name=missing-table-dev-cert"

   # Import Ingress
   terraform import kubernetes_ingress_v1.dev \
     missing-table-dev/missing-table-ingress
   ```

4. **Remove manual Helm labels:**
   - Terraform will manage these resources going forward
   - Helm chart should NOT include ingress/certificates

#### Success Criteria:
- ✅ Ingress and SSL managed by Terraform
- ✅ No manual kubectl apply needed for networking
- ✅ SSL certificates automatically provision for new domains
- ✅ Helm chart focuses only on application resources

---

### Phase 5: Helm Integration (Week 5)

**Goal:** Integrate Terraform-managed infrastructure with Helm deployments

#### Tasks:
1. **Update Helm chart to remove infrastructure:**
   ```yaml
   # helm/missing-table/values.yaml
   # REMOVE:
   # - ingress configuration
   # - certificate configuration
   # - namespace creation

   # KEEP:
   # - Application deployments
   # - Services
   # - ConfigMaps (non-sensitive)
   ```

2. **Create Terraform Helm release management:**
   ```hcl
   # 03-kubernetes-dev/helm.tf
   resource "helm_release" "missing_table" {
     name       = "missing-table"
     namespace  = kubernetes_namespace.dev.metadata[0].name
     chart      = "../../helm/missing-table"

     values = [
       templatefile("${path.module}/helm-values.yaml.tpl", {
         backend_image  = var.backend_image
         frontend_image = var.frontend_image
         environment    = "dev"
       })
     ]

     depends_on = [
       kubernetes_manifest.external_secret  # Wait for secrets
     ]
   }
   ```

3. **Update GitHub Actions workflows:**
   ```yaml
   # Remove Helm upgrade from workflow
   # Terraform will manage Helm releases
   # OR keep Helm in workflow for CD, but let Terraform manage infra
   ```

#### Decision Point: Helm Management Strategy

**Option A: Terraform Manages Helm Releases**
- ✅ Single source of truth (Terraform)
- ✅ Infrastructure and app deployed together
- ❌ Slower deployments (Terraform apply)
- ❌ Couples infrastructure changes with app deploys

**Option B: GitHub Actions Manages Helm Releases** (RECOMMENDED)
- ✅ Fast application deployments
- ✅ Separation of concerns (infra vs app)
- ✅ Existing CI/CD pipeline continues to work
- ✅ Terraform only manages infrastructure
- ❌ Two deployment systems to maintain

**Recommendation:** Use Option B
- Terraform manages: GKE, networking, ingress, SSL, secrets infrastructure
- Helm (via GitHub Actions) manages: Application deployments
- Clear boundary: Terraform for platform, Helm for applications

#### Success Criteria:
- ✅ Helm chart contains only application resources
- ✅ Terraform manages all infrastructure
- ✅ GitHub Actions can still deploy applications
- ✅ No conflicts between Terraform and Helm

---

### Phase 6: CI/CD Integration (Week 6)

**Goal:** Update GitHub Actions workflows to use Terraform-managed infrastructure

#### Tasks:
1. **Add Terraform validation to CI:**
   ```yaml
   # .github/workflows/terraform-validate.yml
   name: Terraform Validation
   on:
     pull_request:
       paths:
         - 'terraform/**'
   jobs:
     validate:
       runs-on: ubuntu-latest
       steps:
         - uses: hashicorp/setup-terraform@v2
         - run: terraform init
         - run: terraform validate
         - run: terraform plan
   ```

2. **Add Terraform apply workflow:**
   ```yaml
   # .github/workflows/terraform-apply.yml
   name: Terraform Apply
   on:
     push:
       branches: [main]
       paths:
         - 'terraform/**'
   jobs:
     apply:
       runs-on: ubuntu-latest
       steps:
         - uses: hashicorp/setup-terraform@v2
         - run: terraform init
         - run: terraform apply -auto-approve
   ```

3. **Update deployment workflows:**
   ```yaml
   # .github/workflows/deploy-prod.yml
   # REMOVE:
   # - Ingress creation
   # - Certificate creation
   # - Secret creation

   # UPDATE:
   # - Use External Secrets from Secret Manager
   # - Reference Terraform-created infrastructure
   ```

4. **Create runbook for infrastructure changes:**
   ```markdown
   # Infrastructure Change Process
   1. Create feature branch
   2. Modify Terraform files
   3. Run `terraform plan` locally
   4. Create PR
   5. Review Terraform plan in CI
   6. Merge to main
   7. Terraform apply runs automatically
   ```

#### Success Criteria:
- ✅ Terraform changes validated in PRs
- ✅ Infrastructure changes automated via CI/CD
- ✅ No manual Terraform operations required
- ✅ Runbook documented for team

---

## Security Considerations

### Secrets Management
- ✅ Use Google Secret Manager for all sensitive data
- ✅ Enable audit logging for secret access
- ✅ Implement secret rotation policies
- ✅ Use Workload Identity for K8s → Secret Manager access
- ✅ No secrets in Terraform state (use External Secrets Operator)

### Terraform State Security
- ✅ Store state in GCS with encryption at rest
- ✅ Enable versioning on state bucket
- ✅ Restrict access to state bucket (IAM)
- ✅ Use state locking to prevent concurrent modifications

### IAM Best Practices
- ✅ Principle of least privilege for service accounts
- ✅ Separate service accounts per environment
- ✅ Document all IAM bindings in Terraform
- ✅ Regular IAM audits

---

## Migration Checklist

### Pre-Migration
- [ ] Backup all manual configurations (`kubectl get all -A -o yaml`)
- [ ] Document current DNS records
- [ ] Export current GitHub secrets to secure storage
- [ ] Create GCS bucket for Terraform state
- [ ] Set up Terraform Cloud/Enterprise (optional)

### Phase 1: Foundation
- [ ] Create bootstrap stack
- [ ] Import GKE cluster
- [ ] Import static IPs
- [ ] Import Artifact Registry
- [ ] Verify `terraform plan` shows no changes

### Phase 2: Kubernetes Base
- [ ] Import namespaces
- [ ] Create RBAC resources
- [ ] Test namespace isolation

### Phase 3: Secrets
- [ ] Install External Secrets Operator
- [ ] Migrate secrets to Secret Manager
- [ ] Test ESO sync
- [ ] Update applications to use new secrets
- [ ] Delete manual K8s secrets

### Phase 4: Ingress
- [ ] Import ManagedCertificate resources
- [ ] Import Ingress resources
- [ ] Verify SSL still works
- [ ] Test DNS resolution
- [ ] Test HTTPS traffic

### Phase 5: Helm
- [ ] Update Helm charts
- [ ] Remove infrastructure from charts
- [ ] Test Helm deployments
- [ ] Verify no Helm/Terraform conflicts

### Phase 6: CI/CD
- [ ] Add Terraform validation to CI
- [ ] Add Terraform apply workflow
- [ ] Update deployment workflows
- [ ] Test full deployment pipeline

### Post-Migration
- [ ] Document new infrastructure
- [ ] Train team on Terraform workflows
- [ ] Set up Terraform state backups
- [ ] Schedule regular drift detection
- [ ] Decommission manual infrastructure docs

---

## Rollback Plan

### If Migration Fails
1. **Keep manual resources:** Don't delete until Terraform is verified
2. **State file backups:** Version state bucket for easy rollback
3. **Import vs. Create:** Prefer import to avoid downtime
4. **Gradual migration:** One stack at a time, not all at once

### Rollback Commands
```bash
# Destroy Terraform-managed resources (last resort)
terraform destroy -auto-approve

# Restore from manual backup
kubectl apply -f backups/manual-resources-backup.yaml

# Restore GitHub secrets from secure storage
gh secret set SECRET_NAME < secrets-backup.txt
```

---

## Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 1 week | GCP access, Terraform setup |
| Phase 2: K8s Base | 1 week | Phase 1 complete |
| Phase 3: Secrets | 1 week | Phase 2 complete, ESO installed |
| Phase 4: Ingress | 1 week | Phase 3 complete |
| Phase 5: Helm | 1 week | Phase 4 complete |
| Phase 6: CI/CD | 1 week | Phase 5 complete |
| **Total** | **6 weeks** | |

### Parallel Work Opportunities
- Phases 1-2 can overlap (different resources)
- CI/CD setup can start during Phase 5
- Documentation can be written throughout

---

## Success Metrics

### Technical Metrics
- ✅ 100% of infrastructure in Terraform
- ✅ Zero manual kubectl operations for infrastructure
- ✅ All secrets in Secret Manager
- ✅ Terraform state stored securely in GCS
- ✅ CI/CD validates all Terraform changes

### Operational Metrics
- ✅ Infrastructure changes deployed in < 15 minutes
- ✅ Zero downtime during migration
- ✅ Disaster recovery tested and documented
- ✅ Team trained on Terraform workflows

### Documentation Metrics
- ✅ Runbooks for all infrastructure operations
- ✅ Architecture diagrams updated
- ✅ Onboarding guide for new team members

---

## References

- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
- [External Secrets Operator](https://external-secrets.io/)
- [GKE Ingress](https://cloud.google.com/kubernetes-engine/docs/concepts/ingress)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)

---

**Last Updated:** 2025-10-18
**Next Review:** After Phase 1 completion
