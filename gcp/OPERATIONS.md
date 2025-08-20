# GCP Infrastructure Operations Runbook

This runbook provides operational procedures for managing the Missing Table application infrastructure on Google Cloud Platform.

## 📋 Daily Operations

### Health Checks

#### Morning Health Check (5 minutes)
```bash
#!/bin/bash
# daily-health-check.sh

echo "=== Missing Table Infrastructure Health Check ==="
echo "Date: $(date)"

# 1. Check GKE cluster health
echo "🔍 Checking GKE cluster status..."
kubectl get nodes --no-headers | awk '{print $1, $2}' | grep -v Ready && echo "❌ Node issues detected" || echo "✅ All nodes ready"

# 2. Check pod status
echo "🔍 Checking application pods..."
kubectl get pods -n missing-table --no-headers | grep -v Running && echo "❌ Pod issues detected" || echo "✅ All pods running"

# 3. Check external endpoint
echo "🔍 Checking application endpoint..."
curl -s -o /dev/null -w "%{http_code}" https://your-app-domain.com/health | grep -q 200 && echo "✅ Endpoint healthy" || echo "❌ Endpoint issues"

# 4. Check recent alerts
echo "🔍 Checking recent alerts..."
gcloud logging read 'resource.type="gce_instance" AND severity>=ERROR' --limit=5 --format="value(timestamp, jsonPayload.message)" --since="24h"

echo "=== Health check complete ==="
```

#### Application Performance Check
```bash
# Check application metrics
kubectl top pods -n missing-table
kubectl get hpa -n missing-table

# Check resource utilization
gcloud compute instances list --format="table(name,status,machineType,cpuPlatform)"
```

### Security Monitoring

#### Daily Security Review
```bash
# Check Binary Authorization denials
gcloud logging read 'resource.type="gke_cluster" AND jsonPayload.decision="DENY"' --limit=10 --since="24h"

# Review secret access logs
gcloud logging read 'protoPayload.serviceName="secretmanager.googleapis.com"' --limit=20 --since="24h"

# Check authentication failures
kubectl logs -l app=missing-table-backend -n missing-table --since=24h | grep -i "authentication.*failed"
```

## 🚨 Incident Response

### Alert Response Procedures

#### High Error Rate Alert
**Severity**: High | **Response Time**: 15 minutes

1. **Immediate Assessment**:
   ```bash
   # Check current error rate
   kubectl logs -l app=missing-table-backend -n missing-table --since=10m | grep -i error | wc -l
   
   # Check pod status
   kubectl get pods -n missing-table
   
   # Check recent deployments
   kubectl rollout history deployment/missing-table-backend -n missing-table
   ```

2. **Investigation Steps**:
   ```bash
   # Check application logs
   kubectl logs -f deployment/missing-table-backend -n missing-table --tail=100
   
   # Check database connectivity
   kubectl exec -it deployment/missing-table-backend -n missing-table -- curl -I database-health-endpoint
   
   # Check external service dependencies
   kubectl exec -it deployment/missing-table-backend -n missing-table -- nslookup external-service.com
   ```

3. **Resolution Actions**:
   ```bash
   # Restart pods if needed
   kubectl rollout restart deployment/missing-table-backend -n missing-table
   
   # Scale up if resource constrained
   kubectl scale deployment missing-table-backend --replicas=5 -n missing-table
   
   # Rollback if recent deployment caused issues
   kubectl rollout undo deployment/missing-table-backend -n missing-table
   ```

#### Database Connection Issues
**Severity**: Critical | **Response Time**: 10 minutes

1. **Immediate Actions**:
   ```bash
   # Check database service status
   kubectl get svc -n missing-table
   
   # Check database pod logs
   kubectl logs -l app=database -n missing-table --tail=50
   
   # Test connectivity from application pod
   kubectl exec -it deployment/missing-table-backend -n missing-table -- telnet database-service 5432
   ```

2. **Secret Verification**:
   ```bash
   # Verify database credentials are accessible
   kubectl get secret database-credentials -n missing-table -o yaml
   
   # Check Secret Manager access
   gcloud secrets versions access latest --secret="missing-table-production-database-url"
   ```

#### Binary Authorization Violations
**Severity**: Medium | **Response Time**: 30 minutes

1. **Investigation**:
   ```bash
   # Check denied images
   gcloud logging read 'resource.type="gke_cluster" AND jsonPayload.decision="DENY"' --limit=10 --since="2h"
   
   # Verify attestor status
   gcloud container binauthz attestors list
   
   # Check CI/CD pipeline status
   # Review GitHub Actions or other CI/CD logs
   ```

2. **Resolution**:
   ```bash
   # Create manual attestation if needed (emergency only)
   gcloud beta container binauthz attestations sign-and-create \
     --artifact-url="gcr.io/project/image:tag" \
     --attestor="projects/PROJECT/attestors/vulnerability-attestor" \
     --signature-algorithm="rsa-pss-2048-sha256"
   ```

### Escalation Matrix

| Alert Type | Initial Response | Escalation (30min) | Executive (1hr) |
|------------|------------------|-------------------|------------------|
| Application Down | DevOps Team | Engineering Lead | CTO |
| Security Incident | Security Team | CISO | CEO |
| Data Loss | DBA + DevOps | Engineering Lead | CTO |
| Cost Overrun | FinOps | Engineering Lead | CFO |

## 🔧 Maintenance Tasks

### Weekly Maintenance

#### Security Updates (Sundays 2:00 AM UTC)
```bash
#!/bin/bash
# weekly-security-maintenance.sh

echo "=== Weekly Security Maintenance ==="

# 1. Update GKE cluster
gcloud container clusters upgrade missing-table-production-cluster \
  --region=us-central1 --cluster-version=latest

# 2. Update node pools
gcloud container node-pools upgrade primary \
  --cluster=missing-table-production-cluster \
  --region=us-central1

# 3. Review and rotate secrets if needed
gcloud secrets versions list missing-table-production-jwt-secret --limit=5

# 4. Update container images
kubectl set image deployment/missing-table-backend \
  backend=gcr.io/project/backend:latest -n missing-table

# 5. Clean up old images
gcloud container images list-tags gcr.io/project/backend \
  --format="get(digest)" --filter="timestamp.date('%Y-%m-%d')<'$(date -d '30 days ago' '+%Y-%m-%d')'" \
  | head -10 \
  | xargs -I {} gcloud container images delete gcr.io/project/backend@{} --quiet
```

#### Cost Optimization Review
```bash
# Check cost trends
gcloud billing budgets list --billing-account=BILLING_ACCOUNT_ID

# Review resource utilization
kubectl top nodes
kubectl top pods -n missing-table

# Check for unused resources
gcloud compute disks list --filter="status:READY AND NOT users:*"
gcloud compute addresses list --filter="status:RESERVED AND NOT users:*"
```

### Monthly Maintenance

#### Security Audit (First Monday of each month)
```bash
#!/bin/bash
# monthly-security-audit.sh

echo "=== Monthly Security Audit ==="

# 1. Review IAM permissions
gcloud projects get-iam-policy PROJECT_ID --format=json > iam-policy-$(date +%Y%m).json

# 2. Check service account usage
gcloud logging read 'protoPayload.authenticationInfo.principalEmail!=""' \
  --format="value(protoPayload.authenticationInfo.principalEmail)" \
  --since="30d" | sort | uniq -c | sort -nr

# 3. Review secret access patterns
gcloud logging read 'protoPayload.serviceName="secretmanager.googleapis.com"' \
  --format="table(timestamp, protoPayload.authenticationInfo.principalEmail, protoPayload.resourceName)" \
  --since="30d"

# 4. Validate binary authorization policies
gcloud container binauthz policy export

# 5. Review network security
gcloud compute firewall-rules list --format="table(name,direction,priority,sourceRanges.list():label=SRC_RANGES,allowed[].map().firewall_rule().list():label=ALLOW,targetTags.list():label=TARGET_TAGS)"
```

#### Performance Review
```bash
# Generate performance report
kubectl describe nodes | grep -A 5 "Allocated resources"
kubectl get hpa -n missing-table -o wide

# Review monitoring dashboards
echo "Review these dashboards in Cloud Monitoring:"
echo "- Application Performance Dashboard"
echo "- Security Monitoring Dashboard"
echo "- Cost Analysis Dashboard"
```

## 📊 Backup and Recovery

### Backup Procedures

#### Application Data Backup (Daily)
```bash
#!/bin/bash
# daily-backup.sh

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_BUCKET="gs://missing-table-backups"

echo "=== Daily Backup Process ==="

# 1. Backup database
kubectl exec deployment/database -n missing-table -- pg_dump database_name > db_backup_$BACKUP_DATE.sql
gsutil cp db_backup_$BACKUP_DATE.sql $BACKUP_BUCKET/database/

# 2. Backup Kubernetes configurations
kubectl get all -n missing-table -o yaml > k8s_backup_$BACKUP_DATE.yaml
gsutil cp k8s_backup_$BACKUP_DATE.yaml $BACKUP_BUCKET/kubernetes/

# 3. Backup secrets (metadata only)
kubectl get secrets -n missing-table -o yaml > secrets_backup_$BACKUP_DATE.yaml
gsutil cp secrets_backup_$BACKUP_DATE.yaml $BACKUP_BUCKET/secrets/

# 4. Cleanup local files
rm db_backup_$BACKUP_DATE.sql k8s_backup_$BACKUP_DATE.yaml secrets_backup_$BACKUP_DATE.yaml

echo "=== Backup complete ==="
```

#### Infrastructure Backup
```bash
# Terraform state backup (automated via backend)
terraform state pull > terraform-state-backup-$(date +%Y%m%d).json

# GKE cluster configuration backup
gcloud container clusters describe missing-table-production-cluster \
  --region=us-central1 --format=export > gke-config-backup-$(date +%Y%m%d).yaml
```

### Recovery Procedures

#### Database Recovery
```bash
# Restore from latest backup
LATEST_BACKUP=$(gsutil ls gs://missing-table-backups/database/ | tail -1)
gsutil cp $LATEST_BACKUP ./restore.sql

# Apply to database
kubectl exec -i deployment/database -n missing-table -- psql database_name < restore.sql
```

#### Application Recovery
```bash
# Restore Kubernetes resources
kubectl apply -f k8s_backup_YYYYMMDD_HHMMSS.yaml

# Verify restoration
kubectl get pods -n missing-table
kubectl get svc -n missing-table
```

#### Infrastructure Recovery
```bash
# Restore from Terraform
cd terraform
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

## 🔍 Monitoring and Alerting

### Key Metrics to Monitor

#### Application Metrics
- **Response Time**: < 500ms for 95th percentile
- **Error Rate**: < 1% of total requests
- **Throughput**: Requests per second
- **Availability**: > 99.9% uptime

#### Infrastructure Metrics
- **CPU Utilization**: < 80% average
- **Memory Usage**: < 85% of allocated
- **Disk I/O**: Monitor for saturation
- **Network Latency**: < 100ms internal

#### Security Metrics
- **Failed Authentication Attempts**: < 10 per hour
- **Binary Authorization Denials**: 0 per hour
- **Anomalous Secret Access**: Manual review required
- **Network Traffic Anomalies**: Investigate spikes

### Custom Alerts Setup

#### Application Alert
```bash
# Create custom metric for application errors
gcloud logging metrics create application_critical_errors \
  --description="Critical application errors requiring immediate attention" \
  --log-filter='resource.type="k8s_container" AND jsonPayload.level="CRITICAL"'

# Create alert policy
gcloud alpha monitoring policies create \
  --policy-from-file=alert-policies/critical-errors.yaml
```

#### Cost Alert
```bash
# Set up budget alert
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Missing Table Monthly Budget" \
  --budget-amount=1000 \
  --threshold-rule=percent:50,basis:CURRENT_SPEND \
  --threshold-rule=percent:90,basis:CURRENT_SPEND \
  --all-projects-scope
```

## 🔧 Useful Commands

### Quick Diagnostics
```bash
# One-liner health check
kubectl get pods -A | grep -v Running | grep -v Completed

# Check all services
kubectl get svc -A --show-labels

# Resource usage overview
kubectl top nodes && kubectl top pods -A --sort-by=memory

# Recent events
kubectl get events --sort-by=.metadata.creationTimestamp -A | tail -20
```

### Emergency Commands
```bash
# Force pod restart
kubectl delete pod -l app=missing-table-backend -n missing-table

# Emergency scale up
kubectl scale deployment missing-table-backend --replicas=10 -n missing-table

# Drain node for maintenance
kubectl drain NODE_NAME --ignore-daemonsets --delete-emptydir-data

# Emergency secret update
echo "new-secret" | gcloud secrets versions add secret-name --data-file=-
kubectl rollout restart deployment/missing-table-backend -n missing-table
```

## 📞 Contact Information

### Emergency Contacts
- **Primary On-Call**: +1-555-0123 (DevOps)
- **Secondary On-Call**: +1-555-0124 (Engineering)
- **Security Escalation**: +1-555-0125 (Security Team)
- **Executive Escalation**: +1-555-0126 (CTO)

### Useful URLs
- **GCP Console**: https://console.cloud.google.com/
- **Monitoring Dashboard**: https://console.cloud.google.com/monitoring
- **GitHub Actions**: https://github.com/org/repo/actions
- **Slack Alerts**: #missing-table-alerts
- **Status Page**: https://status.missingtable.com

---

**Remember**: Always test procedures in staging before applying to production, and maintain this runbook with updates as the infrastructure evolves.