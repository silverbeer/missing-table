# Infrastructure as Code Architecture

## Overview

This document provides visual representations of the proposed Terraform architecture for the Missing Table project.

## Terraform Stack Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         00-bootstrap                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Enable GCP APIs                                              │ │
│  │ • Create Terraform state GCS bucket                            │ │
│  │ • Set up Terraform service account                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        01-foundation                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ GCP Resources:                                                 │ │
│  │ • GKE Autopilot Cluster (missing-table-dev)                    │ │
│  │ • Static IPs (dev: 34.8.149.240, prod: 35.190.120.93)         │ │
│  │ • Artifact Registry (Docker images)                            │ │
│  │ • VPC Network & Subnets                                        │ │
│  │ • Service Accounts & IAM                                       │ │
│  │ • Workload Identity configuration                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      02-kubernetes-base                              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Kubernetes Infrastructure:                                     │ │
│  │ • Namespaces (missing-table-dev, missing-table-prod)           │ │
│  │ • RBAC Roles & Bindings                                        │ │
│  │ • External Secrets Operator (Helm)                             │ │
│  │ • SecretStore (Google Secret Manager backend)                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────┬────────────────────────────────┬─────────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│   03-kubernetes-dev          │  │    04-kubernetes-prod            │
│  ┌──────────────────────────┐│  │  ┌──────────────────────────────┐│
│  │ Dev Environment:         ││  │  │ Prod Environment:            ││
│  │ • ManagedCertificate     ││  │  │ • ManagedCertificate         ││
│  │   (dev.missingtable.com) ││  │  │   (missingtable.com)         ││
│  │ • Ingress                ││  │  │   (www.missingtable.com)     ││
│  │ • ExternalSecret         ││  │  │ • Ingress                    ││
│  │ • Dev ConfigMaps         ││  │  │ • ExternalSecret             ││
│  └──────────────────────────┘│  │  │ • Prod ConfigMaps            ││
└──────────────────────────────┘  │  └──────────────────────────────┘│
                                  └──────────────────────────────────┘
```

## Secrets Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Google Secret Manager                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Secrets (source of truth):                                     │ │
│  │ • dev-database-url                                             │ │
│  │ • dev-supabase-url                                             │ │
│  │ • dev-supabase-anon-key                                        │ │
│  │ • prod-database-url                                            │ │
│  │ • prod-supabase-url                                            │ │
│  │ • prod-supabase-anon-key                                       │ │
│  │ • ... (all secrets)                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ ESO syncs every 1h
                               │ using Workload Identity
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                External Secrets Operator (K8s)                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ ExternalSecret Resources:                                      │ │
│  │ • missing-table-dev/missing-table-secrets                      │ │
│  │ • missing-table-prod/missing-table-secrets                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ Creates/updates K8s Secrets
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Kubernetes Secrets                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • missing-table-dev/missing-table-secrets                      │ │
│  │   - database-url                                               │ │
│  │   - supabase-url                                               │ │
│  │   - supabase-anon-key                                          │ │
│  │   - ...                                                        │ │
│  │                                                                │ │
│  │ • missing-table-prod/missing-table-secrets                     │ │
│  │   - database-url                                               │ │
│  │   - supabase-url                                               │ │
│  │   - supabase-anon-key                                          │ │
│  │   - ...                                                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ Mounted as environment variables
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Application Pods                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ missing-table-backend    │  │ missing-table-frontend           │ │
│  │ env:                     │  │ env:                             │ │
│  │   DATABASE_URL           │  │   VUE_APP_SUPABASE_URL           │ │
│  │   SUPABASE_URL           │  │   VUE_APP_SUPABASE_ANON_KEY      │ │
│  │   SUPABASE_SERVICE_KEY   │  │   ...                            │ │
│  └──────────────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Networking & Ingress Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Internet                                    │
└──────────────┬────────────────────────────────┬─────────────────────┘
               │                                │
               │ DNS A Record                   │ DNS A Record
               │ dev.missingtable.com           │ missingtable.com
               │ → 34.8.149.240                 │ www.missingtable.com
               │                                │ → 35.190.120.93
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  GCP Global Load Balancer    │  │  GCP Global Load Balancer        │
│  (dev)                       │  │  (prod)                          │
│  • Static IP: 34.8.149.240   │  │  • Static IP: 35.190.120.93      │
│  • SSL Cert: dev-cert        │  │  • SSL Cert: prod-cert           │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  GKE Ingress                 │  │  GKE Ingress                     │
│  (missing-table-dev)         │  │  (missing-table-prod)            │
│  Rules:                      │  │  Rules:                          │
│  • /api → backend:8000       │  │  • /api → backend:8000           │
│  • /health → backend:8000    │  │  • /health → backend:8000        │
│  • / → frontend:8080         │  │  • / → frontend:8080             │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  Kubernetes Services         │  │  Kubernetes Services             │
│  • missing-table-backend     │  │  • missing-table-backend         │
│    (ClusterIP)               │  │    (ClusterIP)                   │
│  • missing-table-frontend    │  │  • missing-table-frontend        │
│    (ClusterIP)               │  │    (ClusterIP)                   │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  Pods (missing-table-dev)    │  │  Pods (missing-table-prod)       │
│  • backend (1 replica)       │  │  • backend (2 replicas)          │
│  • frontend (1 replica)      │  │  • frontend (2 replicas)         │
└──────────────────────────────┘  └──────────────────────────────────┘
```

## Terraform & Helm Separation

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Terraform Manages                               │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Infrastructure (changes infrequently):                         │ │
│  │                                                                │ │
│  │ GCP Layer:                                                     │ │
│  │ • GKE Cluster                                                  │ │
│  │ • Static IPs                                                   │ │
│  │ • VPC Network                                                  │ │
│  │ • Artifact Registry                                            │ │
│  │ • IAM & Service Accounts                                       │ │
│  │                                                                │ │
│  │ Kubernetes Infrastructure Layer:                               │ │
│  │ • Namespaces                                                   │ │
│  │ • Ingress                                                      │ │
│  │ • ManagedCertificate (SSL)                                     │ │
│  │ • ExternalSecret (ESO config)                                  │ │
│  │ • RBAC                                                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ Provides infrastructure for
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Helm Manages                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Applications (changes frequently):                             │ │
│  │                                                                │ │
│  │ • Deployments (backend, frontend)                              │ │
│  │ • Services (ClusterIP, LoadBalancer)                           │ │
│  │ • ConfigMaps (non-sensitive config)                            │ │
│  │ • PodDisruptionBudgets                                         │ │
│  │ • HorizontalPodAutoscalers                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ Deployed via GitHub Actions
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Running Application                              │
└─────────────────────────────────────────────────────────────────────┘
```

## CI/CD Flow with Terraform

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Developer Workflow                                │
└──────────────┬────────────────────────────────┬─────────────────────┘
               │                                │
               │ Infrastructure Change          │ Application Change
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  terraform/                  │  │  helm/ or backend/ or frontend/  │
│  └── 01-foundation/          │  │  └── ... application code        │
│      └── gke.tf              │  │                                  │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               │ Create PR                      │ Create PR
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  GitHub Actions:             │  │  GitHub Actions:                 │
│  terraform-validate.yml      │  │  deploy-dev.yml                  │
│  • terraform init            │  │  • Build Docker images           │
│  • terraform validate        │  │  • Push to Artifact Registry     │
│  • terraform plan            │  │  • Helm upgrade                  │
│  • Post plan to PR comment   │  │  • Health checks                 │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               │ Merge to main                  │ Merge to main
               │                                │
               ▼                                ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  GitHub Actions:             │  │  GitHub Actions:                 │
│  terraform-apply.yml         │  │  deploy-prod.yml                 │
│  • terraform init            │  │  • Build Docker images           │
│  • terraform apply           │  │  • Push to Artifact Registry     │
│  • Automatic approval        │  │  • Helm upgrade                  │
└──────────────┬───────────────┘  └──────────────┬───────────────────┘
               │                                │
               └──────────────┬─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Production GKE                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Terraform-managed infrastructure + Helm-deployed applications  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## State Management Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Terraform Workstation                            │
│  (Developer laptop or GitHub Actions runner)                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ $ terraform init                                               │ │
│  │ $ terraform plan                                               │ │
│  │ $ terraform apply                                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ Read/Write state
                               │ with state locking
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Google Cloud Storage                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Bucket: missing-table-terraform-state                          │ │
│  │ ┌────────────────────────────────────────────────────────────┐ │ │
│  │ │ State Files:                                               │ │ │
│  │ │ • 01-foundation/default.tfstate                            │ │ │
│  │ │ • 02-kubernetes-base/default.tfstate                       │ │ │
│  │ │ • 03-kubernetes-dev/default.tfstate                        │ │ │
│  │ │ • 04-kubernetes-prod/default.tfstate                       │ │ │
│  │ │                                                            │ │ │
│  │ │ Features:                                                  │ │ │
│  │ │ ✓ Versioning enabled (rollback capability)                │ │ │
│  │ │ ✓ Encryption at rest                                      │ │ │
│  │ │ ✓ Native state locking                                    │ │ │
│  │ │ ✓ IAM-restricted access                                   │ │ │
│  │ └────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Migration Safety Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Existing Manual Resources                         │
│  • GKE Cluster                                                       │
│  • Static IPs                                                        │
│  • Ingress                                                           │
│  • Secrets                                                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ IMPORT (don't recreate!)
                               │ terraform import ...
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Terraform State                                   │
│  Resources tracked by Terraform but not managed yet                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ terraform plan
                               │ (should show NO changes)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Verify: No Destructive Changes                         │
│  ✓ Plan shows 0 to add, 0 to change, 0 to destroy                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ NOW Terraform manages resources
                               │ Future changes via terraform apply
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Terraform-Managed Resources                         │
│  Same resources, now managed by IaC                                  │
│  ✓ Drift detection                                                   │
│  ✓ Version control                                                   │
│  ✓ Disaster recovery                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

**Last Updated:** 2025-10-18
**See Also:**
- [IAC_MIGRATION_PLAN.md](./IAC_MIGRATION_PLAN.md) - Complete migration plan
- [IAC_QUICK_START.md](./IAC_QUICK_START.md) - Quick reference guide
