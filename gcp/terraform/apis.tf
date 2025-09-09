# Google Cloud APIs Configuration with Security Controls
# Enable required APIs with proper quotas and security constraints

# Enable required APIs with dependency management
locals {
  # Core APIs required for basic functionality
  core_apis = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudbilling.googleapis.com"
  ]

  # Security APIs
  security_apis = [
    "securitycenter.googleapis.com",
    "binaryauthorization.googleapis.com",
    "containersecurity.googleapis.com",
    "containeranalysis.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "accesscontextmanager.googleapis.com",
    "cloudasset.googleapis.com"
  ]

  # Compute and container APIs
  compute_apis = [
    "compute.googleapis.com",
    "container.googleapis.com",
    "containerregistry.googleapis.com",
    "artifactregistry.googleapis.com"
  ]

  # Storage and database APIs
  storage_apis = [
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com"
  ]

  # Networking APIs
  networking_apis = [
    "dns.googleapis.com",
    "certificatemanager.googleapis.com",
    "networkmanagement.googleapis.com",
    "servicenetworking.googleapis.com"
  ]

  # Monitoring and logging APIs
  monitoring_apis = [
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "clouddebugger.googleapis.com",
    "cloudprofiler.googleapis.com"
  ]

  # Billing and budgets APIs
  billing_apis = [
    "billingbudgets.googleapis.com"
  ]

  # All APIs organized by dependency order
  all_apis = concat(
    local.core_apis,
    local.security_apis,
    local.compute_apis,
    local.storage_apis,
    local.networking_apis,
    local.monitoring_apis,
    local.billing_apis
  )
}

# Enable core APIs first
resource "google_project_service" "core_apis" {
  for_each = toset(local.core_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable security APIs after core APIs
resource "google_project_service" "security_apis" {
  for_each = toset(local.security_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.core_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable compute APIs after security APIs
resource "google_project_service" "compute_apis" {
  for_each = toset(local.compute_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.security_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable storage APIs
resource "google_project_service" "storage_apis" {
  for_each = toset(local.storage_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.core_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable networking APIs
resource "google_project_service" "networking_apis" {
  for_each = toset(local.networking_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.compute_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable monitoring APIs
resource "google_project_service" "monitoring_apis" {
  for_each = toset(local.monitoring_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.core_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Enable billing APIs
resource "google_project_service" "billing_apis" {
  for_each = toset(local.billing_apis)
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false

  depends_on = [google_project_service.core_apis]

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# API security constraints
resource "google_project_organization_policy" "restrict_protocol_forwarding" {
  project    = var.project_id
  constraint = "compute.restrictProtocolForwardingCreationForTypes"

  list_policy {
    allow {
      all = false
    }
    deny {
      values = ["ESP"]
    }
  }

  depends_on = [google_project_service.core_apis]
}

resource "google_project_organization_policy" "require_ssl_certificates" {
  project    = var.project_id
  constraint = "compute.requireSslCertificates"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.core_apis]
}

# Consumer quota overrides for API usage limits
resource "google_service_usage_consumer_quota_override" "compute_api_quota" {
  project        = var.project_id
  service        = "compute.googleapis.com"
  metric         = "compute.googleapis.com/instances"
  limit          = "/min/project"
  override_value = "1000"

  depends_on = [google_project_service.compute_apis]
}

resource "google_service_usage_consumer_quota_override" "container_api_quota" {
  project        = var.project_id
  service        = "container.googleapis.com"
  metric         = "container.googleapis.com/cluster_create_requests"
  limit          = "/min/project"
  override_value = "60"

  depends_on = [google_project_service.compute_apis]
}

# API monitoring and alerting
resource "google_monitoring_notification_channel" "api_alerts" {
  display_name = "API Alerts - ${var.app_name}"
  type         = "email"
  
  labels = {
    email_address = var.alert_email
  }

  enabled = true

  depends_on = [google_project_service.monitoring_apis]
}

# Alert policy for API quota exhaustion
resource "google_monitoring_alert_policy" "api_quota_exhaustion" {
  display_name = "API Quota Exhaustion - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "API quota usage high"

    condition_threshold {
      filter          = "resource.type=\"api\" AND metric.type=\"serviceruntime.googleapis.com/api/request_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 800

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.api_alerts.id]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Alert policy for API errors
resource "google_monitoring_alert_policy" "api_errors" {
  display_name = "API Errors - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "High API error rate"

    condition_threshold {
      filter          = "resource.type=\"api\" AND metric.type=\"serviceruntime.googleapis.com/api/request_count\" AND metric.label.response_code!=\"200\""
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 10

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.api_alerts.id]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Log-based metrics for API usage
resource "google_logging_metric" "api_security_events" {
  name   = "api_security_events"
  filter = "protoPayload.serviceName=\"compute.googleapis.com\" AND protoPayload.methodName=~\".*create.*|.*delete.*|.*update.*\" AND severity=\"ERROR\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "API Security Events"
  }

  label_extractors = {
    "user" = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    "method" = "EXTRACT(protoPayload.methodName)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Security scanning for enabled APIs
resource "google_security_scanner_scan_config" "api_scan" {
  count        = var.environment == "production" ? 1 : 0
  display_name = "API Security Scan - ${var.app_name}"
  
  starting_urls = [
    "https://${var.app_name}-${var.environment}.${var.region}.r.appspot.com"
  ]

  auth {
    google_account {
      username = var.admin_email
    }
  }

  schedule {
    schedule_time = "2023-01-01T00:00:00Z"
    interval_duration_days = 7
  }

  depends_on = [google_project_service.security_apis]
}