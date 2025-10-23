# RabbitMQ/Celery Distributed Messaging System

**Implementation Status:** 🚀 In Progress - Phase 0 Complete

---

## Overview

This directory contains comprehensive documentation for implementing a distributed messaging system using RabbitMQ and Celery in the missing-table application.

**Purpose:** Transform the match-scraper → backend communication from synchronous HTTP calls to asynchronous message-based processing for improved reliability, scalability, and learning.

**Architecture:** Hybrid deployment model
- **Cloud (GKE):** Frontend + Backend API (public services)
- **Local (K3s):** RabbitMQ + Celery Workers + Redis (private messaging infrastructure)

**Cost Impact:** +$5/month (electricity) vs +$72/month (full GKE deployment)

---

## Learning Objectives

By completing this implementation, you will become an expert in:

### Distributed Systems Concepts
- ✅ Message queue patterns (publisher/consumer)
- ✅ Task distribution and load balancing
- ✅ Asynchronous processing vs synchronous
- ✅ Message persistence and reliability
- ✅ Dead letter queues and error handling

### Technologies
- ✅ **RabbitMQ**: Message broker fundamentals
- ✅ **Celery**: Distributed task processing
- ✅ **Redis**: In-memory result backend
- ✅ **Kubernetes**: StatefulSets vs Deployments
- ✅ **Helm**: Package manager for Kubernetes

### DevOps Skills
- ✅ Hybrid cloud architecture (local + GKE)
- ✅ StatefulSets with persistent volumes
- ✅ Observability with Grafana Cloud
- ✅ Zero-downtime migrations
- ✅ Rollback strategies

---

## Implementation Phases

### [Phase 0: Repository & Environment Setup](./00-PHASE-0-SETUP.md) ✅ Complete
**Duration:** 1-2 days

- Create feature branches in both repos
- Verify Kubernetes clusters (GKE + local K3s)
- Set up documentation structure
- Push branches to remote

**Key Deliverable:** Feature branches ready, environment verified

---

### [Phase 1: Message Queue Fundamentals](./01-PHASE-1-MESSAGE-QUEUE-BASICS.md) 🔄 Next
**Duration:** 3-4 days

- Deploy standalone RabbitMQ to local K3s
- Explore RabbitMQ Management UI
- Deploy Redis for result storage
- Create "Hello World" Celery task
- Understand queues, exchanges, routing

**Key Deliverable:** "Understanding RabbitMQ" documentation + working Celery task

---

### [Phase 2: Helm Chart Development](./02-PHASE-2-HELM-CHARTS.md) 📋 Planned
**Duration:** 4-5 days

- Create `helm/messaging-platform/` chart structure
- Define RabbitMQ StatefulSet with persistent storage
- Define Redis StatefulSet
- Define Celery worker Deployment
- Create values files for local K3s and future GKE
- Test deployment and upgrades

**Key Deliverable:** Complete Helm chart + "Helm Charts Deep Dive" documentation

---

### [Phase 3: Backend Integration](./03-PHASE-3-BACKEND-INTEGRATION.md) 📋 Planned
**Duration:** 5-7 days

- Add Celery to backend dependencies
- Create `celery_app.py` and task definitions
- Implement `process_match_data` task
- Implement `validate_match_data` task
- Update Dockerfile for worker mode
- Deploy Celery workers to K3s
- Test manual task execution

**Key Deliverable:** Backend processing messages + "Celery Task Design Patterns" guide

---

### [Phase 4: match-scraper Integration](./04-PHASE-4-MATCH-SCRAPER.md) 📋 Planned
**Duration:** 5-7 days

- Create RabbitMQ publisher client
- Implement dual-mode (HTTP fallback + RabbitMQ)
- Add connection retry logic
- Configure dead letter queue
- Deploy match-scraper to K3s
- Test end-to-end flow

**Key Deliverable:** match-scraper publishing to RabbitMQ + "Publisher/Consumer Pattern" guide

---

### [Phase 5: Observability & Monitoring](./05-PHASE-5-OBSERVABILITY.md) 📋 Planned
**Duration:** 3-4 days

- Configure Prometheus exporters (RabbitMQ, Celery)
- Set up Grafana Cloud integration
- Create monitoring dashboards
- Define alert rules
- Test alerting

**Key Deliverable:** Monitoring dashboards + "Distributed Systems Observability" guide

---

### [Phase 6: Migration & Validation](./06-PHASE-6-MIGRATION.md) 📋 Planned
**Duration:** 4-5 days

- Run parallel operation (HTTP + RabbitMQ)
- Compare data consistency
- Measure performance
- Gradual cutover to RabbitMQ-only
- Monitor production for 48 hours
- Document rollback procedure

**Key Deliverable:** Production system + "Migration Runbook" + "Operator Guide"

---

## Quick Reference

### Repository Structure

**missing-table (feature/rabbitmq-celery-integration):**
```
missing-table/
├── backend/
│   ├── celery_app.py            # New: Celery application
│   ├── celery_tasks/            # New: Task definitions
│   ├── requirements.txt         # Updated: Add celery, kombu, redis
│   └── Dockerfile               # Updated: Worker entrypoint
├── helm/
│   └── messaging-platform/      # New: Helm chart for RabbitMQ/Redis/Celery
└── docs/
    └── rabbitmq-celery/         # New: Phase documentation
```

**match-scraper (feature/rabbitmq-integration):**
```
match-scraper/
├── rabbitmq_client.py           # New: RabbitMQ publisher
├── scraper.py                   # Updated: Dual-mode support
├── config.py                    # Updated: RabbitMQ connection
└── requirements.txt             # Updated: Add pika
```

### Key Commands

**Kubernetes Context Switching:**
```bash
# Work on local K3s (RabbitMQ/Celery)
kubectl config use-context rancher-desktop

# Work on GKE (Backend/Frontend)
kubectl config use-context gke_missing-table_us-central1_missing-table-dev

# Check current context
kubectl config current-context
```

**Helm Chart Deployment:**
```bash
# Deploy messaging platform to local K3s
kubectl config use-context rancher-desktop
helm upgrade --install messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  --namespace messaging \
  --create-namespace
```

**Celery Worker Management:**
```bash
# View Celery worker logs
kubectl logs -f deployment/celery-worker -n messaging

# Scale Celery workers
kubectl scale deployment/celery-worker --replicas=3 -n messaging

# Restart Celery workers
kubectl rollout restart deployment/celery-worker -n messaging
```

**RabbitMQ Management:**
```bash
# Port-forward RabbitMQ Management UI
kubectl port-forward svc/rabbitmq 15672:15672 -n messaging
# Access at http://localhost:15672 (guest/guest)

# View RabbitMQ logs
kubectl logs -f statefulset/rabbitmq -n messaging
```

---

## Architecture Diagrams

### Current Architecture (Before)
```
match-scraper
    |
    | HTTP POST /api/matches
    v
Backend API (GKE)
    |
    | SQL INSERT
    v
Supabase Database
```

**Issues:**
- ❌ Synchronous blocking
- ❌ No retry mechanism
- ❌ Single point of failure
- ❌ No visibility into processing

### Proposed Architecture (After)
```
match-scraper (K3s)
    |
    | Publish message
    v
RabbitMQ (K3s)
    |
    | Consume message
    v
Celery Worker (K3s)
    |
    | Validated data
    v
Backend API (GKE)
    |
    | SQL INSERT
    v
Supabase Database
```

**Benefits:**
- ✅ Asynchronous, non-blocking
- ✅ Automatic retries
- ✅ Distributed processing
- ✅ Full observability
- ✅ Easy to scale workers

---

## Testing Strategy

Each phase includes comprehensive testing:

### Unit Tests
- Celery task logic
- RabbitMQ publisher connection handling
- Message serialization/deserialization

### Integration Tests
- End-to-end message flow
- Database updates after task processing
- Error handling and dead letter queue

### Load Tests
- High message volume (1000+ messages)
- Worker scaling under load
- Queue depth monitoring

### Chaos Tests
- Worker crashes during processing
- RabbitMQ restarts with persistent storage
- Network partitions

---

## Success Metrics

The implementation will be considered successful when:

- ✅ **Reliability:** Messages are processed with 99.9% success rate
- ✅ **Performance:** Average processing latency < 500ms
- ✅ **Scalability:** System handles 10x current load without issues
- ✅ **Observability:** All components monitored with alerts configured
- ✅ **Documentation:** Complete operator runbook and troubleshooting guide
- ✅ **Learning:** You can explain every component and design decision confidently

---

## Troubleshooting

For common issues and solutions, see:
- [99-TROUBLESHOOTING.md](./99-TROUBLESHOOTING.md) (Coming in Phase 1)

### Quick Fixes

**RabbitMQ not accessible:**
```bash
kubectl get pods -n messaging
kubectl logs -f statefulset/rabbitmq -n messaging
kubectl describe statefulset/rabbitmq -n messaging
```

**Celery workers not processing:**
```bash
kubectl logs -f deployment/celery-worker -n messaging
# Check RabbitMQ queues in Management UI
```

**Persistent storage issues:**
```bash
kubectl get pvc -n messaging
kubectl describe pvc rabbitmq-data-0 -n messaging
```

---

## References

### Official Documentation
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Kubernetes StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Helm Charts](https://helm.sh/docs/topics/charts/)

### Related Project Documentation
- [RABBITMQ_CELERY_PROPOSAL.md](../../RABBITMQ_CELERY_PROPOSAL.md) - Full architectural proposal
- [docs/03-architecture/README.md](../03-architecture/README.md) - System architecture
- [docs/05-deployment/README.md](../05-deployment/README.md) - Deployment guides
- [docs/07-operations/README.md](../07-operations/README.md) - Operations guides

### Learning Resources
- [Distributed Systems Patterns](https://www.oreilly.com/library/view/designing-distributed-systems/9781491983638/)
- [Message Queue Best Practices](https://www.cloudamqp.com/blog/part1-rabbitmq-best-practice.html)
- [Celery Best Practices](https://denibertovic.com/posts/celery-best-practices/)

---

## Timeline

**Total Duration:** 5-6 weeks

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 0: Setup | 1-2 days | Oct 11 | Oct 12 |
| Phase 1: Basics | 3-4 days | Oct 13 | Oct 16 |
| Phase 2: Helm | 4-5 days | Oct 17 | Oct 21 |
| Phase 3: Backend | 5-7 days | Oct 22 | Oct 28 |
| Phase 4: Scraper | 5-7 days | Oct 29 | Nov 4 |
| Phase 5: Observability | 3-4 days | Nov 5 | Nov 8 |
| Phase 6: Migration | 4-5 days | Nov 9 | Nov 13 |

**Buffer:** 1 week for unexpected issues and deep learning

---

## Getting Help

If you encounter issues:

1. Check phase-specific documentation
2. Review [99-TROUBLESHOOTING.md](./99-TROUBLESHOOTING.md)
3. Search official documentation
4. Check component logs: `kubectl logs -f <pod> -n messaging`
5. Ask for help with specific error messages

**Remember:** This is a learning experience. Take time to understand each concept before moving forward. It's better to go slow and learn deeply than to rush and miss fundamental concepts.

---

**Last Updated:** 2025-10-11
**Current Phase:** Phase 0 ✅ Complete
**Next Phase:** Phase 1 - Message Queue Fundamentals
**Implementation Lead:** silverbeer
