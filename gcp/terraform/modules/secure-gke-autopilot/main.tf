# Secure GKE Autopilot Module with Security Hardening
# This module creates a production-ready GKE Autopilot cluster with comprehensive security controls

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

# Data sources for project information
data "google_project" "current" {
  project_id = var.project_id
}

data "google_client_config" "current" {}

# Random suffix for unique naming
resource "random_id" "cluster_suffix" {
  byte_length = 4
}

# KMS key for GKE encryption
resource "google_kms_key_ring" "gke" {
  name     = "${var.cluster_name}-gke-keyring-${random_id.cluster_suffix.hex}"
  location = var.region
  project  = var.project_id
}

resource "google_kms_crypto_key" "gke" {
  name     = "${var.cluster_name}-gke-key"
  key_ring = google_kms_key_ring.gke.id
  purpose  = "ENCRYPT_DECRYPT"

  rotation_period = var.kms_key_rotation_period

  lifecycle {
    prevent_destroy = true
  }
}

# IAM binding for GKE service account to use KMS key
resource "google_kms_crypto_key_iam_binding" "gke" {
  crypto_key_id = google_kms_crypto_key.gke.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"

  members = [
    "serviceAccount:service-${data.google_project.current.number}@container-engine-robot.iam.gserviceaccount.com",
  ]
}

# Custom service account for GKE nodes
resource "google_service_account" "gke_nodes" {
  account_id   = "${var.cluster_name}-nodes-${random_id.cluster_suffix.hex}"
  display_name = "GKE Nodes Service Account for ${var.cluster_name}"
  description  = "Service account for GKE nodes with minimal required permissions"
  project      = var.project_id
}

# Minimal IAM roles for GKE nodes (principle of least privilege)
resource "google_project_iam_member" "gke_nodes_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

# Additional roles based on workload requirements
resource "google_project_iam_member" "gke_nodes_optional_roles" {
  for_each = toset(var.additional_node_service_account_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

# GKE Autopilot cluster with maximum security hardening
resource "google_container_cluster" "autopilot" {
  provider = google-beta

  name     = "${var.cluster_name}-${random_id.cluster_suffix.hex}"
  location = var.region
  project  = var.project_id

  # Enable Autopilot mode
  enable_autopilot = true

  # Network configuration
  network    = var.network_name
  subnetwork = var.subnetwork_name

  # Private cluster configuration
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = var.enable_private_endpoint
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block

    master_global_access_config {
      enabled = var.enable_master_global_access
    }
  }

  # IP allocation policy for secondary ranges
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
  }

  # Master authorized networks
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.master_authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Workload Identity configuration
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Database encryption using customer-managed encryption key
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.gke.id
  }

  # Network policy configuration
  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  # Binary Authorization configuration
  binary_authorization {
    evaluation_mode = var.binary_authorization_evaluation_mode
  }

  # Security configuration
  security_posture_config {
    mode               = "ENTERPRISE"
    vulnerability_mode = "VULNERABILITY_ENTERPRISE"
  }

  # Enable shielded nodes
  node_config {
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    # Service account for nodes
    service_account = google_service_account.gke_nodes.email

    # OAuth scopes (minimal required)
    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/devstorage.read_only"
    ]

    # Metadata configuration
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  # Cluster-level addons configuration
  addons_config {
    # Disable HTTP load balancing if not needed
    http_load_balancing {
      disabled = var.disable_http_load_balancing
    }

    # Network policy addon
    network_policy_config {
      disabled = false
    }

    # DNS cache config
    dns_cache_config {
      enabled = var.enable_dns_cache
    }

    # GKE Backup for Workloads
    gke_backup_agent_config {
      enabled = var.enable_backup_agent
    }

    # Config Connector
    config_connector_config {
      enabled = var.enable_config_connector
    }
  }

  # Maintenance policy
  maintenance_policy {
    recurring_window {
      start_time = var.maintenance_start_time
      end_time   = var.maintenance_end_time
      recurrence = var.maintenance_recurrence
    }
  }

  # Logging configuration
  logging_config {
    enable_components = var.logging_components
  }

  # Monitoring configuration  
  monitoring_config {
    enable_components = var.monitoring_components

    managed_prometheus {
      enabled = var.enable_managed_prometheus
    }

    advanced_datapath_observability_config {
      enable_metrics = var.enable_datapath_observability
      enable_relay   = var.enable_datapath_observability
    }
  }

  # Notification configuration
  notification_config {
    pubsub {
      enabled = var.enable_notification_config
      topic   = var.notification_config_topic
    }
  }

  # Resource labels
  resource_labels = merge(
    var.cluster_labels,
    {
      environment = var.environment
      managed-by  = "terraform"
      security    = "hardened"
    }
  )

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      # Ignore changes to master_auth as it's managed by GKE
      master_auth,
      # Ignore changes to node pools in Autopilot mode
      node_pool,
      initial_node_count,
    ]
  }

  # Dependency on KMS key IAM binding
  depends_on = [
    google_kms_crypto_key_iam_binding.gke,
    google_project_iam_member.gke_nodes_roles,
  ]
}

# Security monitoring for the cluster
resource "google_logging_metric" "gke_security_events" {
  name   = "${var.cluster_name}-security-events"
  filter = <<-EOT
    resource.type="k8s_cluster"
    resource.labels.cluster_name="${google_container_cluster.autopilot.name}"
    (
      protoPayload.methodName="io.k8s.core.v1.Pod.create" OR
      protoPayload.methodName="io.k8s.apps.v1.Deployment.create" OR
      protoPayload.methodName="io.k8s.core.v1.Secret.create" OR
      severity>=ERROR
    )
  EOT

  label_extractors = {
    user = "protoPayload.authenticationInfo.principalEmail"
  }

  metric_descriptor {
    metric_kind = "COUNTER"
    value_type  = "INT64"
    display_name = "GKE Security Events"
  }

  project = var.project_id
}

# Alerting policy for security events
resource "google_monitoring_alert_policy" "gke_security_alerts" {
  display_name = "${var.cluster_name} Security Alerts"
  project      = var.project_id

  conditions {
    display_name = "High rate of security events"

    condition_threshold {
      filter          = "resource.type=\"k8s_cluster\" AND resource.label.cluster_name=\"${google_container_cluster.autopilot.name}\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 10

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }
}

# Output cluster endpoint for security auditing
output "cluster_ca_certificate" {
  description = "Cluster CA certificate (base64 encoded)"
  value       = google_container_cluster.autopilot.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

# Network security policies (if using Calico)
resource "google_compute_firewall" "gke_webhooks" {
  count = var.create_webhook_firewall ? 1 : 0

  name    = "${var.cluster_name}-webhooks"
  network = var.network_name
  project = var.project_id

  description = "Allow webhook traffic for GKE admission controllers"

  allow {
    protocol = "tcp"
    ports    = ["8443", "9443", "10250"]
  }

  source_ranges = [var.master_ipv4_cidr_block]
  target_tags   = ["gke-${google_container_cluster.autopilot.name}"]

  direction = "INGRESS"
}

# Security baseline ConfigMap for cluster
resource "kubernetes_config_map" "security_baseline" {
  count = var.create_security_baseline ? 1 : 0

  metadata {
    name      = "security-baseline"
    namespace = "kube-system"
    labels = {
      "security.gke.io/baseline" = "true"
    }
  }

  data = {
    "pod-security-standards" = jsonencode({
      enforce = var.pod_security_standard_level
      audit   = var.pod_security_standard_level
      warn    = var.pod_security_standard_level
    })

    "network-policies" = jsonencode({
      default_deny_ingress = true
      default_deny_egress  = false
      allow_dns           = true
      allow_kube_api      = true
    })

    "security-context-constraints" = jsonencode({
      run_as_non_root             = true
      run_as_user_required        = true
      fs_group_required          = true
      supplemental_groups_required = true
      read_only_root_filesystem   = true
      allow_privilege_escalation  = false
      required_drop_capabilities  = ["ALL"]
    })
  }

  depends_on = [google_container_cluster.autopilot]
}