# Outputs for Secure GKE Autopilot Module

output "cluster_id" {
  description = "The GKE cluster ID"
  value       = google_container_cluster.autopilot.id
}

output "cluster_name" {
  description = "The GKE cluster name"
  value       = google_container_cluster.autopilot.name
}

output "cluster_location" {
  description = "The GKE cluster location"
  value       = google_container_cluster.autopilot.location
}

output "cluster_endpoint" {
  description = "The GKE cluster endpoint"
  value       = google_container_cluster.autopilot.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "The cluster CA certificate"
  value       = google_container_cluster.autopilot.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_master_version" {
  description = "The GKE cluster master version"
  value       = google_container_cluster.autopilot.master_version
}

output "cluster_self_link" {
  description = "The GKE cluster self link"
  value       = google_container_cluster.autopilot.self_link
}

output "cluster_services_ipv4_cidr" {
  description = "The IP range in CIDR notation used for service IPs"
  value       = google_container_cluster.autopilot.services_ipv4_cidr
}

output "cluster_operation" {
  description = "The operation that created this cluster"
  value       = google_container_cluster.autopilot.operation
}

# Network outputs
output "network" {
  description = "The network the cluster is attached to"
  value       = google_container_cluster.autopilot.network
}

output "subnetwork" {
  description = "The subnetwork the cluster is attached to"
  value       = google_container_cluster.autopilot.subnetwork
}

# Security outputs
output "node_service_account_email" {
  description = "The service account email used by GKE nodes"
  value       = google_service_account.gke_nodes.email
}

output "node_service_account_id" {
  description = "The service account ID used by GKE nodes"
  value       = google_service_account.gke_nodes.id
}

output "kms_key_ring_id" {
  description = "The KMS key ring ID used for cluster encryption"
  value       = google_kms_key_ring.gke.id
}

output "kms_crypto_key_id" {
  description = "The KMS crypto key ID used for cluster encryption"
  value       = google_kms_crypto_key.gke.id
}

# Monitoring outputs
output "security_metric_name" {
  description = "The name of the security monitoring metric"
  value       = google_logging_metric.gke_security_events.name
}

output "security_alert_policy_name" {
  description = "The name of the security alert policy"
  value       = google_monitoring_alert_policy.gke_security_alerts.name
}

# Workload Identity outputs
output "workload_identity_pool" {
  description = "The Workload Identity pool"
  value       = "${var.project_id}.svc.id.goog"
}

# Connection configuration for kubectl
output "kubectl_config" {
  description = "kubectl configuration for connecting to the cluster"
  value = {
    cluster_name        = google_container_cluster.autopilot.name
    cluster_location    = google_container_cluster.autopilot.location
    project_id         = var.project_id
    connect_command    = "gcloud container clusters get-credentials ${google_container_cluster.autopilot.name} --location=${google_container_cluster.autopilot.location} --project=${var.project_id}"
  }
  sensitive = true
}

# Cluster features status
output "cluster_features" {
  description = "Enabled cluster features and their status"
  value = {
    autopilot_enabled           = google_container_cluster.autopilot.enable_autopilot
    private_cluster             = google_container_cluster.autopilot.private_cluster_config[0].enable_private_nodes
    private_endpoint            = google_container_cluster.autopilot.private_cluster_config[0].enable_private_endpoint
    network_policy_enabled      = google_container_cluster.autopilot.network_policy[0].enabled
    binary_authorization        = google_container_cluster.autopilot.binary_authorization[0].evaluation_mode
    database_encryption_state   = google_container_cluster.autopilot.database_encryption[0].state
    workload_identity_enabled   = length(google_container_cluster.autopilot.workload_identity_config) > 0
    shielded_nodes_enabled      = google_container_cluster.autopilot.node_config[0].shielded_instance_config[0].enable_secure_boot
    security_posture_enabled    = google_container_cluster.autopilot.security_posture_config[0].mode
  }
}

# Resource labels applied to the cluster
output "cluster_labels" {
  description = "Labels applied to the cluster"
  value       = google_container_cluster.autopilot.resource_labels
}

# Maintenance window configuration
output "maintenance_window" {
  description = "Cluster maintenance window configuration"
  value = {
    start_time  = var.maintenance_start_time
    end_time    = var.maintenance_end_time
    recurrence  = var.maintenance_recurrence
  }
}