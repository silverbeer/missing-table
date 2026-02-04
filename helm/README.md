# Missing Table - Helm Chart

This directory contains the Helm chart for deploying the Missing Table application (MLS Next league management system) to Kubernetes.

## 🎯 Learning Objectives

This Helm chart is designed to help you learn:
- **Helm Charts**: Templating, values, dependencies, and lifecycle management
- **Kubernetes**: Deployments, services, persistent volumes, and resource management
- **ArgoCD**: GitOps workflows, continuous deployment, and application management

## 📁 Chart Structure

```
helm/missing-table/
├── Chart.yaml                 # Chart metadata and version info
├── values.yaml               # Default configuration values
├── values-dev.yaml           # Development environment overrides
├── templates/
│   ├── _helpers.tpl          # Template helpers and functions
│   ├── namespace.yaml        # Namespace, ResourceQuota, and LimitRange
│   ├── redis.yaml           # Redis cache deployment and service  
│   ├── backend.yaml         # Backend API deployment and services
│   └── frontend.yaml        # Frontend web app deployment and service
└── README.md                # This documentation
```

## 🚀 Quick Start

### Prerequisites

1. **Rancher Desktop** with Kubernetes enabled
2. **Helm 3.x** installed (`brew install helm`)
3. **Supabase** running locally (`npx supabase start`)

### Deploy with Helm

```bash
# Deploy to development environment
./helm/deploy-helm.sh

# Or manually
helm install missing-table ./helm/missing-table \
    --namespace missing-table \
    --create-namespace \
    --values ./helm/missing-table/values-dev.yaml
```

### Verify Deployment

```bash
# Check Helm release
helm status missing-table -n missing-table

# Check Kubernetes resources
kubectl get all -n missing-table

# Check services and external IPs
kubectl get services -n missing-table
```

### Access the Application

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000

## ⚙️ Configuration

### Key Helm Values

The chart is highly configurable through `values.yaml`:

#### Redis Configuration
```yaml
redis:
  enabled: true
  replicaCount: 1
  persistence:
    size: 1Gi
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
```

#### Backend Configuration
```yaml
backend:
  replicaCount: 1
  image:
    repository: missing-table-backend
    tag: "latest"
  env:
    databaseUrl: "postgresql://..."
    environment: "development"
    logLevel: "info"
```

#### Frontend Configuration
```yaml
frontend:
  replicaCount: 1
  image:
    repository: missing-table-frontend
    tag: "latest"
  env:
    apiUrl: "http://localhost:8000"
    supabaseUrl: "http://host.docker.internal:54321"
```

### Environment-Specific Values

- **`values.yaml`**: Production defaults
- **`values-dev.yaml`**: Development overrides (reduced resources, debug logging)

## 🛠️ Helm Operations

### Install/Upgrade
```bash
# Install new release
helm install missing-table ./helm/missing-table -n missing-table --create-namespace

# Upgrade existing release
helm upgrade missing-table ./helm/missing-table -n missing-table

# Install or upgrade (idempotent)
helm upgrade --install missing-table ./helm/missing-table -n missing-table
```

### Manage Releases
```bash
# List releases
helm list -n missing-table

# Get release history
helm history missing-table -n missing-table

# Rollback to previous version
helm rollback missing-table -n missing-table

# Uninstall release
helm uninstall missing-table -n missing-table
```

### Testing and Validation
```bash
# Dry run to see what would be deployed
helm install missing-table ./helm/missing-table --dry-run --debug

# Template and validate YAML
helm template missing-table ./helm/missing-table | kubectl apply --dry-run=client -f -

# Lint the chart
helm lint ./helm/missing-table
```

## 🔄 GitOps with ArgoCD

This chart is designed to work with ArgoCD for GitOps workflows. ArgoCD is managed via Terraform in the [missingtable-platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap) repository, following the 100% IaC principle.

- **ArgoCD installation**: Managed via Helm in Terraform (`clouds/digitalocean/environments/dev/main.tf`)
- **Application manifests**: Defined as Terraform `kubectl_manifest` resources
- **GitOps workflow**: ArgoCD syncs from `main` branch using `values-prod.yaml`

### Benefits of Helm + ArgoCD

1. **Declarative Configuration**: Infrastructure as Code
2. **Version Control**: Track all changes in Git
3. **Automated Deployments**: Continuous deployment on Git commits
4. **Rollback Capabilities**: Easy rollback to any previous version
5. **Multi-Environment Support**: Different configurations for dev/staging/prod

## 📊 Monitoring and Observability

The chart includes:

- **Resource Limits**: CPU and memory constraints
- **Health Checks**: Liveness and readiness probes
- **Persistent Storage**: Redis data persistence
- **Service Discovery**: Kubernetes services and DNS

### Useful Monitoring Commands

```bash
# Watch pod status
kubectl get pods -n missing-table -w

# View resource usage
kubectl top pods -n missing-table

# Check events
kubectl get events -n missing-table --sort-by='.lastTimestamp'

# View logs
kubectl logs -f deployment/missing-table-backend -n missing-table
kubectl logs -f deployment/missing-table-frontend -n missing-table
```

## 🐛 Troubleshooting

### Common Issues

#### Images Not Found
```bash
# Ensure images are built in k8s.io namespace
nerdctl --namespace k8s.io images | grep missing-table

# Rebuild if needed
nerdctl --namespace k8s.io build -t missing-table-backend:latest -f backend/Dockerfile.dev backend/
```

#### Pod Crashes
```bash
# Check pod details
kubectl describe pod <pod-name> -n missing-table

# View logs
kubectl logs <pod-name> -n missing-table

# Check resource constraints
kubectl get resourcequota -n missing-table
kubectl get limitrange -n missing-table
```

#### Service Connection Issues
```bash
# Test service connectivity
kubectl exec -it deployment/missing-table-backend -n missing-table -- curl http://missing-table-redis:6379

# Check service endpoints
kubectl get endpoints -n missing-table
```

## 🧹 Cleanup

```bash
# Quick cleanup with script
./helm/cleanup-helm.sh

# Manual cleanup
helm uninstall missing-table -n missing-table
kubectl delete namespace missing-table
```

## 📚 Learning Resources

### Helm
- [Helm Documentation](https://helm.sh/docs/)
- [Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Template Functions](https://helm.sh/docs/chart_template_guide/function_list/)

### Kubernetes
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

### ArgoCD
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [GitOps Principles](https://opengitops.dev/)

## 🏗️ Chart Development

### Adding New Features

1. **Update templates**: Add new Kubernetes resources
2. **Update values**: Add configuration options
3. **Test changes**: Use `helm template` and `--dry-run`
4. **Document**: Update this README

### Chart Versioning

The chart follows semantic versioning:
- **Major**: Breaking changes
- **Minor**: New features, backward compatible
- **Patch**: Bug fixes

Update `Chart.yaml` when making changes:
```yaml
version: 0.2.0  # Chart version
appVersion: "1.4.0"  # Application version
```