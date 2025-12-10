# 🚀 Deployment Documentation

> **Audience**: DevOps engineers, system administrators
> **Prerequisites**: Docker, Kubernetes basics, GitHub Actions
> **Environments**: Local, Dev (GKE), Production (GKE)

Documentation for deploying the Missing Table application across different environments with automated CI/CD workflows.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Production Runbook](production-runbook.md)** | ⭐ Complete production operations guide |
| **[GKE Deployment](gke-deployment.md)** | Google Kubernetes Engine deployment |
| **[HTTPS Setup](https-setup.md)** | SSL certificates and custom domains |
| **[HTTPS Architecture](https-architecture.md)** | 📚 **Learning Guide** - How HTTPS and load balancers work |
| **[Quick Reference](https-quick-reference.md)** | Common commands and troubleshooting |
| **[Docker Guide](../../docs/02-development/docker-guide.md)** | Docker image building for DOKS |
| **[Kubernetes](kubernetes.md)** | K8s concepts and configuration |
| **[Helm Charts](helm-charts.md)** | Helm deployment and configuration |
| **[Infrastructure](infrastructure/)** | Terraform, ArgoCD, GitOps |
| **[IaC Migration Plan](IAC_MIGRATION_PLAN.md)** | 🚧 **PLANNING** - Terraform migration strategy |
| **[IaC Quick Start](IAC_QUICK_START.md)** | Quick reference for Terraform migration |
| **[IaC Architecture](IAC_ARCHITECTURE.md)** | Visual diagrams of proposed Terraform architecture |

---

## 🎯 Deployment Options

### Option 1: Automated CI/CD (Recommended)
**Best for**: Production and dev deployments

**Automatic deployments:**
- **Dev Environment**: Push to feature branch → Auto-deploy to dev.missingtable.com
- **Production**: Merge PR to main → Auto-deploy to missingtable.com

**Workflows:**
- `.github/workflows/deploy-dev.yml` - Development deployment
- `.github/workflows/deploy-prod.yml` - Production deployment (with rollback)

**Version management:**
```bash
# Bump version
./scripts/version-bump.sh major|minor|patch

# Commit and push triggers deployment
git add VERSION && git commit -m "chore: bump version to $(cat VERSION)"
git push origin main
```

### Option 2: Manual Production Deployment (Emergency)
**Best for**: Emergency deployments outside CI/CD
```bash
# Interactive deployment with safety checks
./scripts/deploy-prod.sh

# Deploy specific version
./scripts/deploy-prod.sh --version v1.2.3

# Rollback if needed
helm rollback missing-table -n missing-table-prod
```

### Option 3: Local Development (Bare Metal)
**Best for**: Development without Docker
```bash
./missing-table.sh dev
```

---

## 🔧 Quick Commands

### Version Management
```bash
# Bump version
./scripts/version-bump.sh patch    # 1.0.0 -> 1.0.1
./scripts/version-bump.sh minor    # 1.0.0 -> 1.1.0
./scripts/version-bump.sh major    # 1.0.0 -> 2.0.0

# Check current version
cat VERSION
```

### Health Checks
```bash
# Check dev environment
./scripts/health-check.sh dev

# Check production environment
./scripts/health-check.sh prod

# Interactive mode
./scripts/health-check.sh
```

### CI/CD Monitoring
```bash
# Watch GitHub Actions workflow
gh run watch

# List recent workflow runs
gh run list

# View workflow logs
gh run view <run-id> --log
```

### Manual Kubernetes Operations
```bash
# Build and push images
./build-and-push.sh all dev

# Deploy with Helm
helm upgrade --install missing-table ./helm/missing-table \
  --namespace missing-table-dev \
  --values ./helm/missing-table/values-dev.yaml

# Check status
kubectl get pods -n missing-table-dev
kubectl logs -f deployment/missing-table-backend -n missing-table-dev

# Rollback deployment
helm rollback missing-table -n missing-table-dev
```

### Docker Images
```bash
./build-and-push.sh backend dev   # Build backend for dev
./build-and-push.sh frontend prod # Build frontend for prod
./build-and-push.sh all dev       # Build all services
```

---

## 🌍 Environments

### Local Development
- **URL**: http://localhost:8081
- **Database**: Local Supabase
- **Purpose**: Development and testing
- **Deployment**: Manual (`./missing-table.sh dev`)

### Dev (GKE)
- **URL**: https://dev.missingtable.com
- **Cluster**: `missing-table-dev` (us-central1)
- **Namespace**: `missing-table-dev`
- **Database**: Supabase Cloud (dev project)
- **Purpose**: Integration testing, feature previews
- **Deployment**: Automatic on feature branch push
- **Replicas**: 1 (backend, frontend, celery-worker)

### Production (GKE)
- **URL**: https://missingtable.com
- **Cluster**: `missing-table-prod` (us-central1)
- **Namespace**: `missing-table-prod`
- **Database**: Supabase Cloud (production project)
- **Purpose**: Live application
- **Deployment**: Automatic on main branch merge (with rollback)
- **Replicas**: 2 (backend, frontend, celery-worker)
- **Features**:
  - Google-managed SSL certificates
  - Automatic rollback on failure
  - Health check validation
  - Version tracking with build IDs

---

## 📖 Related Documentation

- **[Development Guide](../02-development/)** - Local development
- **[Architecture](../03-architecture/)** - System design
- **[Security](../06-security/)** - Security practices
- **[Operations](../07-operations/)** - Monitoring and maintenance

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
