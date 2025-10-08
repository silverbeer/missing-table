# 🚀 Deployment Documentation

> **Audience**: DevOps engineers, system administrators
> **Prerequisites**: Docker, Kubernetes basics
> **Environments**: Local, Dev (GKE), Production (planned)

Documentation for deploying the Missing Table application across different environments.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Docker Compose](docker-compose.md)** | Local containerized deployment |
| **[Kubernetes](kubernetes.md)** | K8s concepts and configuration |
| **[GKE Deployment](gke-deployment.md)** | Google Kubernetes Engine deployment |
| **[Helm Charts](helm-charts.md)** | Helm deployment and configuration |
| **[HTTPS Setup](https-setup.md)** | SSL certificates and custom domains |
| **[Quick Reference](https-quick-reference.md)** | Common commands |
| **[Infrastructure](infrastructure/)** | Terraform, ArgoCD, GitOps |

---

## 🎯 Deployment Options

### Option 1: Local Development (Docker Compose)
**Best for**: Local testing, quick iterations
```bash
docker-compose up --build
```

### Option 2: Kubernetes (GKE)
**Best for**: Dev, staging, production
```bash
./build-and-push.sh all dev
helm upgrade --install missing-table ./helm/missing-table -n missing-table-dev
```

### Option 3: Bare Metal
**Best for**: Development without Docker
```bash
./missing-table.sh dev
```

---

## 🔧 Quick Commands

### Docker Compose
```bash
docker-compose up --build        # Start all services
docker-compose down              # Stop all services
docker-compose logs -f backend   # Follow logs
```

### Kubernetes (GKE)
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
```

---

## 🌍 Environments

### Local Development
- **URL**: http://localhost:8081
- **Database**: Local Supabase
- **Purpose**: Development and testing

### Dev (GKE)
- **URL**: https://dev.missingtable.com
- **Database**: Supabase Cloud (dev project)
- **Purpose**: Integration testing, demos

### Production (Planned)
- **URL**: https://missingtable.com (planned)
- **Database**: Supabase Cloud (prod project)
- **Purpose**: Live application

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
