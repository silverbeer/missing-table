# Secure VPC Network Module with Network Segmentation and Security Controls
# This module creates a production-ready VPC with comprehensive security hardening

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

# Random suffix for unique naming
resource "random_id" "network_suffix" {
  byte_length = 4
}

# VPC Network with security hardening
resource "google_compute_network" "vpc" {
  name                    = "${var.network_name}-${random_id.network_suffix.hex}"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode           = var.routing_mode
  mtu                    = var.mtu

  description = "Secure VPC network for ${var.environment} environment with network segmentation"

  # Enable deletion protection in production
  lifecycle {
    prevent_destroy = var.enable_deletion_protection
  }
}

# Management subnet for GKE control plane and admin access
resource "google_compute_subnetwork" "management" {
  name          = "${var.network_name}-management-${random_id.network_suffix.hex}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.management_subnet_cidr

  description = "Management subnet for control plane and administrative access"

  # Enable private Google access
  private_ip_google_access = true

  # Secondary ranges for GKE
  secondary_ip_range {
    range_name    = "management-pods"
    ip_cidr_range = var.management_pods_cidr
  }

  secondary_ip_range {
    range_name    = "management-services"
    ip_cidr_range = var.management_services_cidr
  }

  # Enable flow logs for security monitoring
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling       = 0.5
    metadata           = "INCLUDE_ALL_METADATA"
    metadata_fields    = ["src_vpc", "dest_vpc", "src_subnet", "dest_subnet"]
  }
}

# Application subnet for workloads
resource "google_compute_subnetwork" "application" {
  name          = "${var.network_name}-application-${random_id.network_suffix.hex}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.application_subnet_cidr

  description = "Application subnet for workloads and services"

  # Enable private Google access
  private_ip_google_access = true

  # Secondary ranges for GKE
  secondary_ip_range {
    range_name    = "application-pods"
    ip_cidr_range = var.application_pods_cidr
  }

  secondary_ip_range {
    range_name    = "application-services"
    ip_cidr_range = var.application_services_cidr
  }

  # Enable flow logs for security monitoring
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling       = 0.5
    metadata           = "INCLUDE_ALL_METADATA"
    metadata_fields    = ["src_vpc", "dest_vpc", "src_subnet", "dest_subnet"]
  }
}

# Data subnet for databases and persistent storage
resource "google_compute_subnetwork" "data" {
  name          = "${var.network_name}-data-${random_id.network_suffix.hex}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.data_subnet_cidr

  description = "Data subnet for databases and persistent storage"

  # Enable private Google access
  private_ip_google_access = true

  # Enable flow logs for security monitoring
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling       = 1.0  # Higher sampling for data subnet
    metadata           = "INCLUDE_ALL_METADATA"
    metadata_fields    = ["src_vpc", "dest_vpc", "src_subnet", "dest_subnet"]
  }
}

# Cloud Router for NAT gateway
resource "google_compute_router" "router" {
  name    = "${var.network_name}-router-${random_id.network_suffix.hex}"
  project = var.project_id
  region  = var.region
  network = google_compute_network.vpc.id

  description = "Cloud Router for NAT gateway and BGP routing"
}

# Cloud NAT for outbound internet access from private resources
resource "google_compute_router_nat" "nat" {
  name                               = "${var.network_name}-nat-${random_id.network_suffix.hex}"
  project                           = var.project_id
  router                            = google_compute_router.router.name
  region                            = var.region
  nat_ip_allocate_option            = "MANUAL_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  # Allocate dedicated NAT IPs
  nat_ips = google_compute_address.nat_ips[*].self_link

  # Configure subnets for NAT
  subnetwork {
    name                    = google_compute_subnetwork.management.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  subnetwork {
    name                    = google_compute_subnetwork.application.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  # Data subnet uses more restrictive NAT (if needed)
  dynamic "subnetwork" {
    for_each = var.enable_data_subnet_nat ? [1] : []
    content {
      name                    = google_compute_subnetwork.data.id
      source_ip_ranges_to_nat = ["PRIMARY_IP_RANGE"]
    }
  }

  # Logging configuration
  log_config {
    enable = true
    filter = "ALL"
  }

  # Enable endpoint independent mapping for security
  enable_endpoint_independent_mapping = false
}

# Static IP addresses for NAT
resource "google_compute_address" "nat_ips" {
  count        = var.nat_ip_count
  name         = "${var.network_name}-nat-ip-${count.index + 1}-${random_id.network_suffix.hex}"
  project      = var.project_id
  region       = var.region
  address_type = "EXTERNAL"

  description = "Static IP ${count.index + 1} for NAT gateway"
}

# Firewall rule: Deny all ingress by default
resource "google_compute_firewall" "deny_all_ingress" {
  name        = "${var.network_name}-deny-all-ingress-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Default deny all ingress traffic"

  deny {
    protocol = "all"
  }

  direction   = "INGRESS"
  priority    = 65534
  source_ranges = ["0.0.0.0/0"]
}

# Firewall rule: Allow internal communication within VPC
resource "google_compute_firewall" "allow_internal" {
  name        = "${var.network_name}-allow-internal-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Allow internal communication within VPC"

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = [
    var.management_subnet_cidr,
    var.application_subnet_cidr,
    var.data_subnet_cidr,
    var.management_pods_cidr,
    var.application_pods_cidr,
    var.management_services_cidr,
    var.application_services_cidr
  ]
}

# Firewall rule: Allow SSH from authorized networks (management subnet only)
resource "google_compute_firewall" "allow_ssh_authorized" {
  count = length(var.authorized_ssh_networks) > 0 ? 1 : 0

  name        = "${var.network_name}-allow-ssh-authorized-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Allow SSH from authorized networks to management subnet"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = var.authorized_ssh_networks
  target_tags   = ["ssh-allowed"]
}

# Firewall rule: Allow HTTPS from load balancers
resource "google_compute_firewall" "allow_lb_https" {
  name        = "${var.network_name}-allow-lb-https-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Allow HTTPS from Google Cloud Load Balancers"

  allow {
    protocol = "tcp"
    ports    = ["443", "8443"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = [
    "130.211.0.0/22",  # Google Cloud Load Balancer ranges
    "35.191.0.0/16"
  ]
  target_tags = ["lb-backend"]
}

# Firewall rule: Allow health checks from load balancers
resource "google_compute_firewall" "allow_health_checks" {
  name        = "${var.network_name}-allow-health-checks-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Allow health checks from Google Cloud Load Balancers"

  allow {
    protocol = "tcp"
    ports    = ["8080", "8443", "9000-9999"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = [
    "130.211.0.0/22",  # Google Cloud Load Balancer ranges
    "35.191.0.0/16",
    "209.85.152.0/22", # Google services
    "209.85.204.0/22"
  ]
  target_tags = ["lb-backend"]
}

# Firewall rule: Allow GKE master to nodes communication
resource "google_compute_firewall" "allow_gke_master" {
  name        = "${var.network_name}-allow-gke-master-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Allow GKE master to communicate with nodes"

  allow {
    protocol = "tcp"
    ports    = ["443", "10250", "8443", "9443"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = var.gke_master_authorized_networks
  target_tags   = ["gke-node"]
}

# Firewall rule: Deny egress to sensitive ports (security hardening)
resource "google_compute_firewall" "deny_sensitive_egress" {
  name        = "${var.network_name}-deny-sensitive-egress-${random_id.network_suffix.hex}"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Deny egress to sensitive ports for security hardening"

  deny {
    protocol = "tcp"
    ports    = ["22", "3389", "1433", "3306", "5432", "6379", "27017"]
  }

  direction        = "EGRESS"
  priority         = 1000
  destination_ranges = ["0.0.0.0/0"]
  
  # Apply to application workloads (not management or data subnets)
  target_tags = ["restrict-egress"]
}

# Private DNS zone for internal service discovery
resource "google_dns_managed_zone" "private_zone" {
  count = var.create_private_dns_zone ? 1 : 0

  name        = "${var.network_name}-private-zone-${random_id.network_suffix.hex}"
  project     = var.project_id
  dns_name    = "${var.private_dns_domain}."
  description = "Private DNS zone for internal service discovery"

  visibility = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }

  # Enable DNSSEC for security
  dnssec_config {
    state = "on"
  }
}

# Network security monitoring
resource "google_logging_metric" "network_security_events" {
  name   = "${var.network_name}-security-events"
  project = var.project_id
  filter = <<-EOT
    resource.type="gce_subnetwork"
    resource.labels.subnetwork_name=~"${var.network_name}-.*"
    (
      jsonPayload.src_vpc.vpc_name!="${google_compute_network.vpc.name}" OR
      jsonPayload.connection.dest_port="22" OR
      jsonPayload.connection.dest_port="3389" OR
      jsonPayload.connection.dest_port="1433" OR
      jsonPayload.connection.dest_port="3306" OR
      jsonPayload.reporter="DEST"
    )
  EOT

  label_extractors = {
    source_ip = "jsonPayload.connection.src_ip"
    dest_port = "jsonPayload.connection.dest_port"
  }

  metric_descriptor {
    metric_kind = "COUNTER"
    value_type  = "INT64"
    display_name = "Network Security Events"
  }
}

# Network security alerting
resource "google_monitoring_alert_policy" "network_security_alerts" {
  display_name = "${var.network_name} Network Security Alerts"
  project      = var.project_id

  conditions {
    display_name = "Suspicious network activity detected"

    condition_threshold {
      filter          = "resource.type=\"gce_subnetwork\" AND resource.label.subnetwork_name=~\"${var.network_name}-.*\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 50

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

# VPC Flow Logs export to BigQuery for analysis
resource "google_bigquery_dataset" "vpc_flow_logs" {
  count = var.enable_flow_logs_export ? 1 : 0

  dataset_id                 = "${replace(var.network_name, "-", "_")}_flow_logs_${random_id.network_suffix.hex}"
  project                    = var.project_id
  friendly_name             = "VPC Flow Logs for ${var.network_name}"
  description               = "VPC Flow Logs dataset for network security analysis"
  location                  = var.bigquery_location
  default_table_expiration_ms = var.flow_logs_retention_days * 24 * 60 * 60 * 1000

  access {
    role          = "OWNER"
    user_by_email = data.google_client_config.current.client_email
  }

  access {
    role   = "READER"
    domain = var.organization_domain
  }
}

# Log sink for VPC Flow Logs to BigQuery
resource "google_logging_project_sink" "vpc_flow_logs_sink" {
  count = var.enable_flow_logs_export ? 1 : 0

  name        = "${var.network_name}-flow-logs-sink-${random_id.network_suffix.hex}"
  project     = var.project_id
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.vpc_flow_logs[0].dataset_id}"

  filter = <<-EOT
    resource.type="gce_subnetwork"
    resource.labels.subnetwork_name=~"${var.network_name}-.*"
    logName="projects/${var.project_id}/logs/compute.googleapis.com%2Fvpc_flows"
  EOT

  unique_writer_identity = true
}

# Grant BigQuery Data Editor role to log sink service account
resource "google_project_iam_member" "flow_logs_bigquery_editor" {
  count = var.enable_flow_logs_export ? 1 : 0

  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = google_logging_project_sink.vpc_flow_logs_sink[0].writer_identity
}

# Data source for current client config
data "google_client_config" "current" {}