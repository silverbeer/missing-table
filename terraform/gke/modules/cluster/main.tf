terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# GKE Autopilot Cluster
resource "google_container_cluster" "autopilot" {
  name     = var.cluster_name
  location = var.region

  # Enable Autopilot mode
  enable_autopilot = true

  # Allow deletion via Terraform (set to true for production)
  deletion_protection = false

  # Network configuration
  network    = var.network_name
  subnetwork = var.subnetwork_name

  # IP allocation policy (required for Autopilot)
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  # Release channel for automatic updates
  release_channel {
    channel = var.release_channel
  }

  # Maintenance window
  maintenance_policy {
    daily_maintenance_window {
      start_time = var.maintenance_start_time
    }
  }

  # Enable Workload Identity (recommended for security)
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Resource labels
  resource_labels = var.labels
}
