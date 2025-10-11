# Phase 0: Repository & Environment Setup

**Status:** ✅ Complete
**Duration:** 1-2 days
**Learning Goals:** Git branching strategy, Kubernetes cluster basics, project organization

---

## Overview

This phase establishes the foundation for implementing the RabbitMQ/Celery distributed messaging system. We'll set up feature branches in both repositories, verify our Kubernetes environment, and prepare our development workflow.

## Prerequisites

- Access to both `missing-table` and `match-scraper` repositories
- kubectl installed and configured
- Git command-line tools
- Basic understanding of Git branching

---

## 1. Repository Setup

### 1.1 missing-table Repository

The `missing-table` repo contains the backend API and frontend that will consume messages from RabbitMQ.

**Create Feature Branch:**
```bash
# Navigate to missing-table repo
cd ~/gitrepos/missing-table

# Ensure main branch is up to date
git checkout main
git pull origin main

# Create feature branch for RabbitMQ/Celery integration
git checkout -b feature/rabbitmq-celery-integration
```

**Branch Strategy:**
- All RabbitMQ/Celery backend changes go on this branch
- Helm charts for messaging platform will be added here
- Celery worker configuration and tasks will be added here

### 1.2 match-scraper Repository

The `match-scraper` repo will be updated to publish messages to RabbitMQ instead of making direct HTTP calls.

**Create Feature Branch:**
```bash
# Navigate to match-scraper repo
cd ~/gitrepos/match-scraper

# Stash any uncommitted changes
git stash save "WIP: before RabbitMQ feature branch"

# Ensure main branch is up to date
git checkout main
git pull origin main

# Create feature branch for RabbitMQ integration
git checkout -b feature/rabbitmq-integration
```

**Branch Strategy:**
- RabbitMQ publisher client will be added here
- Dual-mode support (HTTP fallback + RabbitMQ) will be implemented here

---

## 2. Kubernetes Environment

### 2.1 Current Cluster Status

**Available Clusters:**
```bash
# List all kubectl contexts
kubectl config get-contexts
```

**Expected Output:**
```
CURRENT   NAME                                              CLUSTER
*         gke_missing-table_us-central1_missing-table-dev   gke_missing-table_us-central1_missing-table-dev
          rancher-desktop                                   rancher-desktop
```

**Active Clusters:**
- ✅ **GKE (Google Kubernetes Engine)**: `gke_missing-table_us-central1_missing-table-dev`
  - Status: Running
  - Location: us-central1 (Google Cloud)
  - Purpose: Production dev environment (https://dev.missingtable.com)

- ❌ **Rancher Desktop (Local K3s)**: `rancher-desktop`
  - Status: Not running
  - Purpose: Local development and testing
  - **Action Required:** Start Rancher Desktop before Phase 1

### 2.2 Starting Local K3s Cluster

The RabbitMQ/Celery messaging platform will be deployed to a **local K3s cluster** to keep costs low (hybrid architecture).

**Why Local K3s?**
- ✅ **Cost Effective**: Only $5/month in electricity vs $72/month on GKE
- ✅ **Learning Experience**: Hands-on with Kubernetes management
- ✅ **Fast Iteration**: No cloud deployment delays during development
- ✅ **Persistent Storage**: StatefulSets with local volumes

**Start Rancher Desktop:**
1. Open Rancher Desktop application on Mac
2. Wait for Kubernetes to initialize (2-3 minutes)
3. Verify cluster is running:
   ```bash
   kubectl config use-context rancher-desktop
   kubectl get nodes
   ```

**Expected Output:**
```
NAME                   STATUS   ROLES                  AGE   VERSION
lima-rancher-desktop   Ready    control-plane,master   Xd    v1.XX.X+k3s1
```

### 2.3 Switching Between Clusters

**During Development:**
```bash
# Work on local K3s for RabbitMQ/Celery
kubectl config use-context rancher-desktop

# Deploy to GKE for backend/frontend testing
kubectl config use-context gke_missing-table_us-central1_missing-table-dev
```

**Quick Context Check:**
```bash
# Show current context
kubectl config current-context

# Show all contexts
kubectl config get-contexts
```

---

## 3. Project Structure

### 3.1 Documentation Organization

All RabbitMQ/Celery implementation documentation will live in:
```
docs/rabbitmq-celery/
├── 00-PHASE-0-SETUP.md              (This file)
├── 01-PHASE-1-MESSAGE-QUEUE-BASICS.md
├── 02-PHASE-2-HELM-CHARTS.md
├── 03-PHASE-3-BACKEND-INTEGRATION.md
├── 04-PHASE-4-MATCH-SCRAPER.md
├── 05-PHASE-5-OBSERVABILITY.md
├── 06-PHASE-6-MIGRATION.md
└── 99-TROUBLESHOOTING.md
```

### 3.2 Helm Chart Structure

The messaging platform Helm chart will be created at:
```
helm/messaging-platform/
├── Chart.yaml
├── values-local.yaml        # For Rancher Desktop
├── values-dev.yaml          # Future: For GKE if needed
├── templates/
│   ├── rabbitmq-statefulset.yaml
│   ├── rabbitmq-service.yaml
│   ├── redis-statefulset.yaml
│   ├── redis-service.yaml
│   ├── celery-worker-deployment.yaml
│   └── secrets.yaml
└── README.md
```

### 3.3 Backend Changes

Celery integration will be added to the backend:
```
backend/
├── celery_app.py            # New: Celery application setup
├── celery_tasks/            # New: Task definitions
│   ├── __init__.py
│   ├── match_tasks.py       # Process match data
│   └── validation_tasks.py  # Validate match data
├── requirements.txt         # Updated: Add celery, kombu
└── Dockerfile               # Updated: Add entrypoint for worker mode
```

### 3.4 match-scraper Changes

RabbitMQ publisher will be added:
```
match-scraper/
├── rabbitmq_client.py       # New: RabbitMQ connection and publishing
├── config.py                # Updated: Add RabbitMQ connection string
├── scraper.py               # Updated: Dual-mode (HTTP + RabbitMQ)
└── requirements.txt         # Updated: Add pika
```

---

## 4. Verification Checklist

Before proceeding to Phase 1, verify:

- [ ] Feature branch `feature/rabbitmq-celery-integration` created in missing-table
- [ ] Feature branch `feature/rabbitmq-integration` created in match-scraper
- [ ] Both branches pushed to origin:
  ```bash
  cd ~/gitrepos/missing-table
  git push -u origin feature/rabbitmq-celery-integration

  cd ~/gitrepos/match-scraper
  git push -u origin feature/rabbitmq-integration
  ```
- [ ] GKE cluster is accessible (`kubectl get nodes` with gke context)
- [ ] Rancher Desktop installed and running
- [ ] Local K3s cluster is accessible (`kubectl get nodes` with rancher-desktop context)
- [ ] Created `docs/rabbitmq-celery/` directory structure

---

## 5. What We Learned

### Git Branching for Multi-Repo Features

When implementing features that span multiple repositories:

1. **Create parallel feature branches** with descriptive names
2. **Use consistent naming conventions** (e.g., `feature/rabbitmq-*`)
3. **Push branches early** to enable collaboration and backup
4. **Keep branches in sync** by regularly merging from main

### Kubernetes Context Management

Kubernetes contexts allow managing multiple clusters:

- **Context = Cluster + User + Namespace**
- Use `kubectl config use-context` to switch between clusters
- Use `kubectl config current-context` to verify active cluster
- **Always verify context** before applying changes to avoid deploying to wrong cluster!

### Hybrid Cloud Architecture

The hybrid deployment model combines benefits of both cloud and local:

| Component | Location | Why? |
|-----------|----------|------|
| Frontend | GKE | Public accessibility, HTTPS |
| Backend API | GKE | Public accessibility, Supabase connection |
| RabbitMQ | Local K3s | Cost savings, persistent storage |
| Celery Workers | Local K3s | Cost savings, close to message queue |
| Redis | Local K3s | Cost savings, low latency to workers |

**Key Insight:** Not everything needs to be in the cloud! The messaging infrastructure can run locally since it doesn't need public accessibility.

---

## 6. Common Issues

### Issue: "The connection to the server was refused"

**Symptom:**
```bash
kubectl get nodes
E1011 18:31:35.068781 memcache.go:265] couldn't get current server API group list
The connection to the server 127.0.0.1:6443 was refused
```

**Cause:** Rancher Desktop is not running or Kubernetes is disabled

**Solution:**
1. Open Rancher Desktop application
2. Wait for "Kubernetes is running" status
3. Retry kubectl command

### Issue: "error: You must be logged in to the server (Unauthorized)"

**Cause:** kubectl context credentials are stale or invalid

**Solution:**
```bash
# For GKE
gcloud container clusters get-credentials missing-table-dev \
  --region us-central1 \
  --project missing-table

# For Rancher Desktop
# Restart Rancher Desktop application
```

### Issue: Stashed changes in match-scraper

**Symptom:** `git stash list` shows uncommitted work

**Solution:**
```bash
cd ~/gitrepos/match-scraper
git stash list  # View stashed changes
git stash pop   # Reapply stashed changes when ready
```

---

## 7. Next Steps

✅ **Phase 0 Complete!** You now have:
- Feature branches in both repositories
- Understanding of available Kubernetes clusters
- Project structure for documentation and code

**Ready for Phase 1:** [Message Queue Fundamentals](./01-PHASE-1-MESSAGE-QUEUE-BASICS.md)

In Phase 1, we'll:
- Start Rancher Desktop and deploy RabbitMQ
- Explore the RabbitMQ Management UI
- Deploy Redis for Celery result backend
- Create and execute your first "Hello World" Celery task
- Learn core concepts: queues, exchanges, routing, tasks

---

## 8. References

- [Git Branching Strategy](https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows)
- [Kubernetes Contexts and Configuration](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
- [Rancher Desktop Documentation](https://docs.rancherdesktop.io/)
- [RABBITMQ_CELERY_PROPOSAL.md](../../RABBITMQ_CELERY_PROPOSAL.md) - Full architectural proposal

---

**Last Updated:** 2025-10-11
**Phase Status:** ✅ Complete
**Next Phase:** Phase 1 - Message Queue Fundamentals
