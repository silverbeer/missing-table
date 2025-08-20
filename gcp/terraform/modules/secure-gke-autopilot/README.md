# Secure GKE Autopilot Terraform Module

This Terraform module creates a production-ready Google Kubernetes Engine (GKE) Autopilot cluster with comprehensive security hardening and best practices implementation.

## Features

### Security Hardening
- **Private cluster** with private nodes and optional private endpoint
- **Customer-managed encryption (CMEK)** using Cloud KMS for etcd encryption
- **Workload Identity** for secure service account authentication
- **Binary Authorization** for container image security
- **Network policies** using Calico for microsegmentation
- **Shielded GKE nodes** with secure boot and integrity monitoring
- **Security posture management** with vulnerability scanning
- **Pod Security Standards** enforcement at the cluster level

### Compliance & Monitoring
- **Comprehensive logging** (system components, workloads, API server)
- **Advanced monitoring** with managed Prometheus integration
- **Security event monitoring** with custom metrics and alerts
- **Audit logging** configuration for compliance requirements
- **Datapath observability** for network traffic analysis

### Network Security
- **Master authorized networks** for API server access control
- **VPC-native networking** with secondary IP ranges
- **Firewall rules** for webhook traffic
- **DNS cache** for improved performance and security

### Operational Excellence
- **Automated maintenance windows** with configurable schedules
- **GKE Backup for Workloads** integration
- **Resource labeling** for governance and cost management
- **Service account** with minimal required permissions
- **KMS key rotation** with configurable periods

## Usage

### Basic Usage

```hcl
module "secure_gke" {
  source = "./modules/secure-gke-autopilot"

  project_id      = "your-project-id"
  region          = "us-central1"
  cluster_name    = "secure-cluster"
  environment     = "production"
  
  network_name    = "your-vpc-network"
  subnetwork_name = "your-subnet"
  
  master_authorized_networks = [
    {
      cidr_block   = "10.0.0.0/8"
      display_name = "Internal networks"
    }
  ]
}
```

### Advanced Configuration

```hcl
module "secure_gke" {
  source = "./modules/secure-gke-autopilot"

  project_id   = "your-project-id"
  region       = "us-central1"
  cluster_name = "secure-cluster"
  environment  = "production"
  
  # Network configuration
  network_name                     = "your-vpc-network"
  subnetwork_name                  = "your-subnet"
  pods_secondary_range_name        = "pods-range"
  services_secondary_range_name    = "services-range"
  
  # Private cluster settings
  enable_private_endpoint          = true
  master_ipv4_cidr_block          = "10.0.0.0/28"
  enable_master_global_access     = false
  
  # Security configuration
  binary_authorization_evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  pod_security_standard_level         = "restricted"
  kms_key_rotation_period            = "7776000s" # 90 days
  
  # Service account permissions
  additional_node_service_account_roles = [
    "roles/artifactregistry.reader"
  ]
  
  # Monitoring and logging
  enable_managed_prometheus        = true
  enable_datapath_observability   = true
  logging_components = [
    "SYSTEM_COMPONENTS",
    "WORKLOADS",
    "API_SERVER"
  ]
  
  # Maintenance window (Saturdays 2-6 AM UTC)
  maintenance_start_time = "2023-01-01T02:00:00Z"
  maintenance_end_time   = "2023-01-01T06:00:00Z"
  maintenance_recurrence = "FREQ=WEEKLY;BYDAY=SA"
  
  # Authorized networks
  master_authorized_networks = [
    {
      cidr_block   = "10.0.0.0/8"
      display_name = "Internal corporate network"
    },
    {
      cidr_block   = "192.168.1.0/24"
      display_name = "VPN access"
    }
  ]
  
  # Notification configuration
  notification_channels = [
    "projects/your-project/notificationChannels/your-channel-id"
  ]
  
  # Resource labels
  cluster_labels = {
    team        = "platform"
    cost-center = "engineering"
    compliance  = "sox"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| google | ~> 5.0 |
| google-beta | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| google | ~> 5.0 |
| google-beta | ~> 5.0 |
| kubernetes | >= 2.0 |
| random | >= 3.0 |

## Resources

| Name | Type |
|------|------|
| google_container_cluster.autopilot | resource |
| google_service_account.gke_nodes | resource |
| google_project_iam_member.gke_nodes_roles | resource |
| google_kms_key_ring.gke | resource |
| google_kms_crypto_key.gke | resource |
| google_kms_crypto_key_iam_binding.gke | resource |
| google_logging_metric.gke_security_events | resource |
| google_monitoring_alert_policy.gke_security_alerts | resource |
| google_compute_firewall.gke_webhooks | resource |
| kubernetes_config_map.security_baseline | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_id | The GCP project ID | `string` | n/a | yes |
| region | The GCP region for the cluster | `string` | n/a | yes |
| cluster_name | The name of the GKE cluster | `string` | n/a | yes |
| network_name | The VPC network name | `string` | n/a | yes |
| subnetwork_name | The subnetwork name | `string` | n/a | yes |
| environment | Environment name | `string` | `"production"` | no |
| enable_private_endpoint | Enable private endpoint for the cluster master | `bool` | `true` | no |
| master_ipv4_cidr_block | The IP range in CIDR notation for the cluster master | `string` | `"10.0.0.0/28"` | no |
| master_authorized_networks | List of master authorized networks | `list(object)` | `[]` | no |
| binary_authorization_evaluation_mode | Binary Authorization evaluation mode | `string` | `"PROJECT_SINGLETON_POLICY_ENFORCE"` | no |
| pod_security_standard_level | Pod Security Standard level to enforce | `string` | `"restricted"` | no |

## Outputs

| Name | Description |
|------|-------------|
| cluster_id | The GKE cluster ID |
| cluster_name | The GKE cluster name |
| cluster_endpoint | The GKE cluster endpoint |
| node_service_account_email | The service account email used by GKE nodes |
| kms_crypto_key_id | The KMS crypto key ID used for cluster encryption |
| kubectl_config | kubectl configuration for connecting to the cluster |
| cluster_features | Enabled cluster features and their status |

## Security Considerations

### Network Security
- The cluster is configured as a private cluster by default
- Master authorized networks should be configured to restrict API server access
- Network policies are enabled using Calico for workload isolation
- VPC-native networking with secondary IP ranges for pods and services

### Identity and Access Management
- Custom service account with minimal required permissions
- Workload Identity enabled for secure pod-to-GCP service authentication
- Binary Authorization enforces container image security policies
- Pod Security Standards restrict privileged workloads

### Data Protection
- Customer-managed encryption keys (CMEK) for etcd encryption
- KMS key rotation configured with 90-day period
- Shielded nodes with secure boot and integrity monitoring
- Security posture management with vulnerability scanning

### Monitoring and Compliance
- Comprehensive audit logging for all API server activities
- Security event monitoring with custom metrics and alerts
- Compliance with CIS Kubernetes Benchmark
- Integration with Google Cloud Security Command Center

## Post-Deployment Steps

After deploying the cluster, complete these security configuration steps:

1. **Configure kubectl access:**
   ```bash
   gcloud container clusters get-credentials CLUSTER_NAME --location=REGION --project=PROJECT_ID
   ```

2. **Apply network policies:**
   ```bash
   kubectl apply -f network-policies/
   ```

3. **Configure Binary Authorization:**
   ```bash
   gcloud container binauthz policy import policy.yaml
   ```

4. **Set up workload-specific service accounts:**
   ```bash
   kubectl create serviceaccount workload-sa
   gcloud iam service-accounts add-iam-policy-binding \
     --role roles/iam.workloadIdentityUser \
     --member "serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/workload-sa]" \
     gcp-service-account@PROJECT_ID.iam.gserviceaccount.com
   ```

5. **Enable Pod Security Standards:**
   ```bash
   kubectl label namespace default pod-security.kubernetes.io/enforce=restricted
   ```

## Monitoring and Alerting

The module creates several monitoring resources:

- **Security Events Metric**: Tracks security-related activities
- **Alert Policy**: Notifies on suspicious activity patterns
- **Managed Prometheus**: Application metrics collection
- **Datapath Observability**: Network traffic analysis

Configure notification channels to receive security alerts.

## Compliance

This module helps achieve compliance with:

- **CIS Kubernetes Benchmark**
- **PCI DSS** (Payment Card Industry)
- **SOC 2** (Service Organization Control 2)
- **ISO 27001** (Information Security Management)
- **NIST Cybersecurity Framework**

## Support

For issues and questions:
- Check the [GKE documentation](https://cloud.google.com/kubernetes-engine/docs)
- Review [GKE security best practices](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster)
- Open an issue in the repository