# Google Cloud Security Configuration
# Security Command Center, Binary Authorization, and VPC Security

# Security Command Center configuration
resource "google_security_center_notification_config" "main" {
  count           = var.organization_id != "" ? 1 : 0
  config_id       = "${local.name_prefix}-notifications"
  organization    = var.organization_id
  description     = "Security notifications for Missing Table application"
  pubsub_topic    = google_pubsub_topic.security_notifications.id
  streaming_config {
    filter = "state=\"ACTIVE\" AND (category=\"MALWARE\" OR category=\"UNAUTHORIZED_USER\" OR category=\"VULNERABLE_TO_EXPLOIT\")"
  }

  depends_on = [google_project_service.security_apis]
}

# Pub/Sub topic for security notifications
resource "google_pubsub_topic" "security_notifications" {
  name = "${local.name_prefix}-security-notifications"

  labels = merge(local.common_labels, local.security_labels)

  depends_on = [google_project_service.core_apis]
}

# Pub/Sub subscription for security notifications
resource "google_pubsub_subscription" "security_notifications" {
  name  = "${local.name_prefix}-security-notifications-sub"
  topic = google_pubsub_topic.security_notifications.name

  message_retention_duration = "604800s" # 7 days
  ack_deadline_seconds       = 600

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.security_notifications_dlq.id
    max_delivery_attempts = 5
  }

  labels = merge(local.common_labels, local.security_labels)

  depends_on = [google_project_service.core_apis]
}

# Dead letter queue for security notifications
resource "google_pubsub_topic" "security_notifications_dlq" {
  name = "${local.name_prefix}-security-notifications-dlq"

  labels = merge(local.common_labels, local.security_labels)

  depends_on = [google_project_service.core_apis]
}

# Binary Authorization policy
resource "google_binary_authorization_policy" "main" {
  project = var.project_id

  # Default rule - require attestation
  default_admission_rule {
    evaluation_mode  = "REQUIRE_ATTESTATION"
    enforcement_mode = var.enable_binary_authorization ? "ENFORCED_BLOCK_AND_AUDIT_LOG" : "DRYRUN_AUDIT_LOG_ONLY"

    require_attestations_by = [
      google_binary_authorization_attestor.vulnerability_scanner.name,
      google_binary_authorization_attestor.quality_assurance.name
    ]
  }

  # Allow Google-built images (for system containers)
  admission_whitelist_patterns {
    name_pattern = "gcr.io/google-containers/*"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/google_containers/*"
  }

  admission_whitelist_patterns {
    name_pattern = "k8s.gcr.io/*"
  }

  admission_whitelist_patterns {
    name_pattern = "registry.k8s.io/*"
  }

  # Allow our application images with attestation
  cluster_admission_rules {
    cluster                = "projects/${var.project_id}/locations/${var.region}/clusters/${local.name_prefix}-cluster"
    evaluation_mode        = "REQUIRE_ATTESTATION"
    enforcement_mode       = var.enable_binary_authorization ? "ENFORCED_BLOCK_AND_AUDIT_LOG" : "DRYRUN_AUDIT_LOG_ONLY"
    require_attestations_by = [
      google_binary_authorization_attestor.vulnerability_scanner.name,
      google_binary_authorization_attestor.quality_assurance.name
    ]
  }

  depends_on = [google_project_service.security_apis]
}

# Binary Authorization attestor for vulnerability scanning
resource "google_binary_authorization_attestor" "vulnerability_scanner" {
  name    = "${local.name_prefix}-vulnerability-attestor"
  project = var.project_id

  attestation_authority_note {
    note_reference = google_container_analysis_note.vulnerability_note.name
    public_keys {
      id = "vulnerability-scanner-key"
      pkix_public_key {
        public_key_pem      = tls_private_key.vulnerability_attestor.public_key_pem
        signature_algorithm = "RSA_PSS_2048_SHA256"
      }
    }
  }

  description = "Attestor for vulnerability scanning results"

  depends_on = [google_project_service.security_apis]
}

# Binary Authorization attestor for quality assurance
resource "google_binary_authorization_attestor" "quality_assurance" {
  name    = "${local.name_prefix}-qa-attestor"
  project = var.project_id

  attestation_authority_note {
    note_reference = google_container_analysis_note.qa_note.name
    public_keys {
      id = "qa-key"
      pkix_public_key {
        public_key_pem      = tls_private_key.qa_attestor.public_key_pem
        signature_algorithm = "RSA_PSS_2048_SHA256"
      }
    }
  }

  description = "Attestor for quality assurance verification"

  depends_on = [google_project_service.security_apis]
}

# Container Analysis notes for attestors
resource "google_container_analysis_note" "vulnerability_note" {
  name    = "${local.name_prefix}-vulnerability-note"
  project = var.project_id

  attestation_authority {
    hint {
      human_readable_name = "Vulnerability Scanner"
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_container_analysis_note" "qa_note" {
  name    = "${local.name_prefix}-qa-note"
  project = var.project_id

  attestation_authority {
    hint {
      human_readable_name = "Quality Assurance"
    }
  }

  depends_on = [google_project_service.security_apis]
}

# TLS private keys for attestors
resource "tls_private_key" "vulnerability_attestor" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_private_key" "qa_attestor" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

# VPC for secure networking
resource "google_compute_network" "main" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode           = "REGIONAL"

  depends_on = [google_project_service.compute_apis]
}

# Private subnet for GKE cluster
resource "google_compute_subnetwork" "private" {
  name                     = "${local.name_prefix}-private-subnet"
  ip_cidr_range           = local.network_config.private_subnet_cidr
  region                  = var.region
  network                 = google_compute_network.main.id
  private_ip_google_access = true

  # Secondary IP ranges for GKE
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = local.network_config.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = local.network_config.services_cidr
  }

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata            = "INCLUDE_ALL_METADATA"
  }

  depends_on = [google_project_service.compute_apis]
}

# Public subnet for load balancers
resource "google_compute_subnetwork" "public" {
  name          = "${local.name_prefix}-public-subnet"
  ip_cidr_range = local.network_config.public_subnet_cidr
  region        = var.region
  network       = google_compute_network.main.id

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata            = "INCLUDE_ALL_METADATA"
  }

  depends_on = [google_project_service.compute_apis]
}

# Cloud NAT for outbound internet access
resource "google_compute_router" "main" {
  name    = "${local.name_prefix}-router"
  region  = var.region
  network = google_compute_network.main.id

  depends_on = [google_project_service.compute_apis]
}

resource "google_compute_router_nat" "main" {
  name                               = "${local.name_prefix}-nat"
  router                            = google_compute_router.main.name
  region                            = var.region
  nat_ip_allocate_option            = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }

  depends_on = [google_project_service.compute_apis]
}

# Firewall rules for security
resource "google_compute_firewall" "deny_all_ingress" {
  name    = "${local.name_prefix}-deny-all-ingress"
  network = google_compute_network.main.name

  deny {
    protocol = "all"
  }

  direction     = "INGRESS"
  priority      = 65534
  source_ranges = ["0.0.0.0/0"]

  depends_on = [google_project_service.compute_apis]
}

resource "google_compute_firewall" "allow_internal" {
  name    = "${local.name_prefix}-allow-internal"
  network = google_compute_network.main.name

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
  source_ranges = [local.network_config.vpc_cidr]

  depends_on = [google_project_service.compute_apis]
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "${local.name_prefix}-allow-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = var.authorized_networks[*].cidr_block
  target_tags   = ["ssh-allowed"]

  depends_on = [google_project_service.compute_apis]
}

resource "google_compute_firewall" "allow_https" {
  name    = "${local.name_prefix}-allow-https"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["443", "8443"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["https-server"]

  depends_on = [google_project_service.compute_apis]
}

resource "google_compute_firewall" "allow_http" {
  name    = "${local.name_prefix}-allow-http"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["80", "8080"]
  }

  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server"]

  depends_on = [google_project_service.compute_apis]
}

# Security monitoring alert policies
resource "google_monitoring_alert_policy" "binary_authorization_violations" {
  display_name = "Binary Authorization Violations - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Binary Authorization denial"

    condition_threshold {
      filter          = "resource.type=\"gke_cluster\" AND metric.type=\"binary_authorization.googleapis.com/policy_evaluation_count\" AND metric.label.verdict=\"DENY\""
      duration        = "60s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_alerts.id]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Security notification channel
resource "google_monitoring_notification_channel" "security_alerts" {
  display_name = "Security Alerts - ${var.app_name}"
  type         = "email"
  
  labels = {
    email_address = var.security_contact_email
  }

  enabled = true

  depends_on = [google_project_service.monitoring_apis]
}

# Security dashboard
resource "google_monitoring_dashboard" "security_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Security Monitoring - ${var.app_name}"
    mosaicLayout = {
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Binary Authorization Decisions"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"gke_cluster\" AND metric.type=\"binary_authorization.googleapis.com/policy_evaluation_count\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = ["metric.label.verdict"]
                      }
                    }
                  }
                  plotType = "STACKED_AREA"
                }
              ]
            }
          }
        },
        {
          width  = 6
          height = 4
          widget = {
            title = "VPC Flow Logs"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"gce_subnetwork\" AND metric.type=\"logging.googleapis.com/log_entry_count\" AND metric.label.log=\"vpc_flows\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
            }
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.monitoring_apis]
}

# Web Security Scanner
resource "google_security_scanner_scan_config" "main" {
  count        = var.environment == "production" ? 1 : 0
  display_name = "Missing Table Security Scan"
  
  starting_urls = [
    "https://${local.name_prefix}.${var.region}.r.appspot.com"
  ]

  auth {
    google_account {
      username = var.admin_email
    }
  }

  schedule {
    schedule_time = "2023-01-01T02:00:00Z"
    interval_duration_days = 7
  }

  target_platforms = ["APP_ENGINE", "COMPUTE"]

  depends_on = [google_project_service.security_apis]
}

# Output security information
output "vpc_network_name" {
  description = "VPC network name"
  value       = google_compute_network.main.name
  sensitive   = false
}

output "private_subnet_name" {
  description = "Private subnet name"
  value       = google_compute_subnetwork.private.name
  sensitive   = false
}

output "binary_authorization_policy_name" {
  description = "Binary Authorization policy name"
  value       = google_binary_authorization_policy.main.name
  sensitive   = false
}

output "security_dashboard_url" {
  description = "URL to the security monitoring dashboard"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.security_dashboard.id}?project=${var.project_id}"
  sensitive   = false
}