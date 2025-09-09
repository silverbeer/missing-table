# Google Kubernetes Engine (GKE) Configuration
# Security-hardened GKE cluster with Workload Identity and comprehensive monitoring

# GKE cluster with security best practices
resource "google_container_cluster" "main" {
  name     = "${local.name_prefix}-cluster"
  location = var.region
  
  # Remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  # Network configuration
  network    = google_compute_network.main.name
  subnetwork = google_compute_subnetwork.private.name

  # IP allocation policy for VPC-native networking
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Security: Private cluster configuration
  private_cluster_config {
    enable_private_nodes    = var.enable_private_nodes
    enable_private_endpoint = var.enable_private_nodes
    master_ipv4_cidr_block  = "172.16.0.0/28"
    
    master_global_access_config {
      enabled = true
    }
  }

  # Security: Authorized networks for master access
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Security: Workload Identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Security: Shielded nodes
  node_config {
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  # Security: Enable network policy
  network_policy {
    enabled = var.enable_network_policy
  }

  # Security: Pod Security Policy
  pod_security_policy_config {
    enabled = var.enable_pod_security_policy
  }

  # Security: Binary Authorization
  binary_authorization {
    evaluation_mode = var.enable_binary_authorization ? "PROJECT_SINGLETON_POLICY_ENFORCE" : "DISABLED"
  }

  # Monitoring and logging
  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  # Enable Google Groups for RBAC
  authenticator_groups_config {
    security_group = "gke-security-groups@${var.project_id}.iam.gserviceaccount.com"
  }

  # Cluster addons
  addons_config {
    http_load_balancing {
      disabled = false
    }

    horizontal_pod_autoscaling {
      disabled = false
    }

    network_policy_config {
      disabled = !var.enable_network_policy
    }

    cloudrun_config {
      disabled = true # Disable Cloud Run on GKE for security
    }

    istio_config {
      disabled = true # Disable Istio initially
    }

    gce_persistent_disk_csi_driver_config {
      enabled = true
    }

    gcp_filestore_csi_driver_config {
      enabled = false # Disable unless needed
    }
  }

  # Database encryption
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.main.id
  }

  # Notification configuration for cluster events
  notification_config {
    pubsub {
      enabled = true
      topic   = google_pubsub_topic.gke_notifications.id
    }
  }

  # Cluster resource labels
  resource_labels = merge(local.common_labels, local.security_labels, {
    cluster_type = "production"
  })

  # Maintenance policy
  maintenance_policy {
    recurring_window {
      start_time = "2023-01-01T02:00:00Z"
      end_time   = "2023-01-01T06:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SU"
    }
  }

  # Lifecycle management
  lifecycle {
    ignore_changes = [node_config]
  }

  depends_on = [
    google_project_service.compute_apis,
    google_compute_subnetwork.private
  ]
}

# Primary node pool with security hardening
resource "google_container_node_pool" "primary" {
  name       = "${local.name_prefix}-primary-pool"
  location   = var.region
  cluster    = google_container_cluster.main.name
  
  # Node count and autoscaling
  initial_node_count = var.gke_node_count
  
  dynamic "autoscaling" {
    for_each = var.gke_auto_scaling ? [1] : []
    content {
      min_node_count = var.gke_min_node_count
      max_node_count = var.gke_max_node_count
    }
  }

  # Node configuration
  node_config {
    preemptible  = var.environment != "production"
    machine_type = var.gke_machine_type
    disk_size_gb = var.gke_disk_size_gb
    disk_type    = var.gke_disk_type
    image_type   = "COS_CONTAINERD" # Use Container-Optimized OS

    # Security: Service account with minimal permissions
    service_account = google_service_account.gke_nodes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/devstorage.read_only"
    ]

    # Security: Shielded instance configuration
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    # Security: Workload Identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Security: Node taints for dedicated workloads
    taint {
      key    = "missing-table/dedicated"
      value  = "true"
      effect = "NO_SCHEDULE"
    }

    # Labels for node identification
    labels = merge(local.common_labels, {
      node_pool = "primary"
      workload  = "application"
    })

    # Node tags for firewall rules
    tags = ["gke-node", "missing-table-node"]

    # Security: Restrict metadata access
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  # Node management
  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # Upgrade settings
  upgrade_settings {
    strategy         = "SURGE"
    max_surge        = 1
    max_unavailable  = 0
  }

  # Node pool labels
  node_labels = merge(local.common_labels, {
    node_pool = "primary"
  })

  depends_on = [google_container_cluster.main]
}

# Dedicated node pool for system workloads
resource "google_container_node_pool" "system" {
  name       = "${local.name_prefix}-system-pool"
  location   = var.region
  cluster    = google_container_cluster.main.name
  
  initial_node_count = 1
  
  autoscaling {
    min_node_count = 1
    max_node_count = 3
  }

  node_config {
    preemptible  = false # System workloads should not be preemptible
    machine_type = "e2-medium"
    disk_size_gb = 30
    disk_type    = "pd-ssd"
    image_type   = "COS_CONTAINERD"

    service_account = google_service_account.gke_nodes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/devstorage.read_only"
    ]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Taints for system workloads only
    taint {
      key    = "missing-table/system"
      value  = "true"
      effect = "NO_SCHEDULE"
    }

    labels = merge(local.common_labels, {
      node_pool = "system"
      workload  = "system"
    })

    tags = ["gke-node", "missing-table-system-node"]

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  upgrade_settings {
    strategy         = "SURGE"
    max_surge        = 1
    max_unavailable  = 0
  }

  depends_on = [google_container_cluster.main]
}

# Service account for GKE nodes
resource "google_service_account" "gke_nodes" {
  account_id   = "${local.name_prefix}-gke-nodes"
  display_name = "GKE Nodes Service Account"
  description  = "Service account for GKE nodes with minimal required permissions"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# IAM roles for GKE nodes service account
resource "google_project_iam_member" "gke_nodes_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"

  depends_on = [google_project_service.core_apis]
}

# Pub/Sub topic for GKE notifications
resource "google_pubsub_topic" "gke_notifications" {
  name = "${local.name_prefix}-gke-notifications"

  labels = merge(local.common_labels, {
    component = "gke"
  })

  depends_on = [google_project_service.core_apis]
}

# Pub/Sub subscription for GKE notifications
resource "google_pubsub_subscription" "gke_notifications" {
  name  = "${local.name_prefix}-gke-notifications-sub"
  topic = google_pubsub_topic.gke_notifications.name

  message_retention_duration = "604800s" # 7 days
  ack_deadline_seconds       = 600

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = merge(local.common_labels, {
    component = "gke"
  })

  depends_on = [google_project_service.core_apis]
}

# GKE cluster monitoring alerts
resource "google_monitoring_alert_policy" "gke_node_not_ready" {
  display_name = "GKE Node Not Ready - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Node not ready"

    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/ready\""
      duration        = "300s"
      comparison      = "COMPARISON_LESS_THAN"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "1800s" # 30 minutes
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "gke_cluster_unhealthy" {
  display_name = "GKE Cluster Unhealthy - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Cluster health issues"

    condition_threshold {
      filter          = "resource.type=\"gke_cluster\" AND metric.type=\"container.googleapis.com/cluster/up\""
      duration        = "300s"
      comparison      = "COMPARISON_LESS_THAN"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "1800s" # 30 minutes
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Operations notification channel
resource "google_monitoring_notification_channel" "ops_alerts" {
  display_name = "Operations Alerts - ${var.app_name}"
  type         = "email"
  
  labels = {
    email_address = var.devops_contact_email
  }

  enabled = true

  depends_on = [google_project_service.monitoring_apis]
}

# Output GKE cluster information
output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.main.name
  sensitive   = false
}

output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.main.endpoint
  sensitive   = true
}

output "gke_cluster_ca_certificate" {
  description = "GKE cluster CA certificate"
  value       = google_container_cluster.main.master_auth.0.cluster_ca_certificate
  sensitive   = true
}

output "gke_cluster_location" {
  description = "GKE cluster location"
  value       = google_container_cluster.main.location
  sensitive   = false
}