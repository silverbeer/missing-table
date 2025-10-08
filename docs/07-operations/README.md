# 🔧 Operations Documentation

> **Audience**: DevOps, SRE, system administrators
> **Focus**: Monitoring, maintenance, incident response
> **SLA Target**: 99.9% uptime

Documentation for running, monitoring, and maintaining the Missing Table application.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Database Backup](database-backup.md)** | Backup and restore procedures |
| **[Monitoring](monitoring.md)** | Health checks, metrics, logging |
| **[Uptime Testing](uptime-testing.md)** | Automated health verification |
| **[Incident Response](incident-response.md)** | When things go wrong |

---

## 🎯 Operational Excellence

### Key Metrics

**Availability**:
- Target: 99.9% uptime
- Current: Monitoring in progress

**Performance**:
- API response time: < 200ms (p95)
- Page load time: < 2s
- Database query time: < 100ms (p95)

**Reliability**:
- Zero data loss
- < 1 hour recovery time
- Automated failover

---

## 💾 Database Operations

### Daily Backups

```bash
# Manual backup
./scripts/db_tools.sh backup

# Restore from latest
./scripts/db_tools.sh restore

# List backups
./scripts/db_tools.sh list

# Cleanup old backups (keep 10)
./scripts/db_tools.sh cleanup 10
```

### Backup Strategy

**Local Development**:
- JSON format backups
- Before/after major changes
- Stored in `backups/` directory

**Cloud (GKE)**:
- Automated daily backups
- 30-day retention
- Point-in-time recovery

See: [Database Backup Guide](database-backup.md)

---

## 📊 Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Full health check (database, auth, etc.)
curl http://localhost:8000/health/full

# Comprehensive uptime test
cd backend && uv run python ../scripts/uptime_test.py
```

### What We Monitor

**Application**:
- API endpoint health
- Response times
- Error rates
- Request volume

**Database**:
- Connection pool status
- Query performance
- Disk usage
- Replication lag

**Infrastructure**:
- CPU/Memory usage
- Network throughput
- Pod health (K8s)
- Container restarts

See: [Monitoring Guide](monitoring.md)

---

## 🚨 Alerts

### Alert Levels

**Critical** (Page immediately):
- Service down
- Database unavailable
- Critical security vulnerability

**Warning** (Investigate within 1 hour):
- High error rate
- Slow response times
- Disk space low

**Info** (Review daily):
- Increased traffic
- Successful deployments
- Backup completions

### Alert Channels

- Slack: #alerts channel
- Email: on-call rotation
- PagerDuty: Critical alerts

---

## 🔍 Logging

### Log Locations

**Local Development**:
```
~/.missing-table/logs/
├── backend.log
├── frontend.log
└── combined.log
```

**Cloud (GKE)**:
```bash
# View logs
kubectl logs -f deployment/missing-table-backend -n missing-table-dev

# Export logs
kubectl logs deployment/missing-table-backend -n missing-table-dev > backend.log
```

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical issues

---

## 🛠️ Common Operations

### Restart Services

```bash
# Local
./missing-table.sh restart

# Kubernetes
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
```

### Check Service Status

```bash
# Local
./missing-table.sh status

# Kubernetes
kubectl get pods -n missing-table-dev
kubectl get services -n missing-table-dev
kubectl describe pod <pod-name> -n missing-table-dev
```

### Scale Services

```bash
# Kubernetes
kubectl scale deployment/missing-table-backend --replicas=3 -n missing-table-dev
```

---

## 🆘 Incident Response

### Severity Levels

**SEV 1 - Critical**:
- Complete service outage
- Data loss or corruption
- Security breach

**SEV 2 - High**:
- Partial service degradation
- Performance issues
- Failed deployment

**SEV 3 - Medium**:
- Minor functionality issues
- Non-critical bugs
- Planned maintenance

**SEV 4 - Low**:
- Cosmetic issues
- Feature requests
- Documentation updates

### Incident Response Process

1. **Detect**: Monitoring alerts or user reports
2. **Assess**: Determine severity and impact
3. **Respond**: Execute mitigation plan
4. **Recover**: Restore normal operations
5. **Review**: Post-mortem and improvements

See: [Incident Response Guide](incident-response.md)

---

## 📈 Capacity Planning

### Resource Usage

**Current** (Dev environment):
- Backend: 1 pod, 512Mi memory, 250m CPU
- Frontend: 1 pod, 256Mi memory, 250m CPU
- Database: Supabase Cloud (managed)

**Scaling Triggers**:
- CPU > 70% sustained
- Memory > 80%
- Response time > 500ms

---

## 🔄 Maintenance Windows

### Planned Maintenance

- **Frequency**: Monthly
- **Duration**: 1-2 hours
- **Timing**: Sundays 2-4 AM EST
- **Notice**: 7 days advance

### Maintenance Tasks

- Database updates
- Security patches
- Performance optimizations
- Dependency updates

---

## 📖 Related Documentation

- **[Deployment](../05-deployment/)** - Deployment procedures
- **[Security](../06-security/)** - Security operations
- **[Architecture](../03-architecture/)** - System design
- **[Development](../02-development/)** - Local development

---

## 🎯 Operational Runbooks

### Database Recovery

1. Check Supabase status
2. Verify backup availability
3. Stop write operations
4. Restore from backup
5. Verify data integrity
6. Resume operations

### Performance Degradation

1. Check resource usage
2. Review recent deployments
3. Analyze slow queries
4. Check external dependencies
5. Scale if needed
6. Deploy hotfix if required

---

<div align="center">

**On-Call Rotation**: [Link to schedule]

[⬆ Back to Documentation Hub](../README.md)

</div>
