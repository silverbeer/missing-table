# Google Cloud Service Accounts with Workload Identity and Least Privilege
# Security-first configuration with minimal permissions and comprehensive monitoring

# Service Account for the backend application
resource "google_service_account" "backend" {
  account_id   = "${local.name_prefix}-backend"
  display_name = "Missing Table Backend Service Account"
  description  = "Service account for the backend application with minimal required permissions"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# Service Account for the frontend application
resource "google_service_account" "frontend" {
  account_id   = "${local.name_prefix}-frontend"
  display_name = "Missing Table Frontend Service Account"
  description  = "Service account for the frontend application with minimal required permissions"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# Service Account for CI/CD operations
resource "google_service_account" "cicd" {
  account_id   = "${local.name_prefix}-cicd"
  display_name = "Missing Table CI/CD Service Account"
  description  = "Service account for CI/CD operations with deployment permissions"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# Service Account for monitoring and logging
resource "google_service_account" "monitoring" {
  account_id   = "${local.name_prefix}-monitoring"
  display_name = "Missing Table Monitoring Service Account"
  description  = "Service account for monitoring, logging, and alerting operations"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# Service Account for backup operations
resource "google_service_account" "backup" {
  account_id   = "${local.name_prefix}-backup"
  display_name = "Missing Table Backup Service Account"
  description  = "Service account for backup and disaster recovery operations"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# Service Account for security operations
resource "google_service_account" "security" {
  account_id   = "${local.name_prefix}-security"
  display_name = "Missing Table Security Service Account"
  description  = "Service account for security scanning and compliance operations"
  project      = var.project_id

  depends_on = [google_project_service.core_apis]
}

# IAM roles for backend service account (minimal permissions)
resource "google_project_iam_member" "backend_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.objectViewer" # For reading container images
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.backend.email}"

  depends_on = [google_project_service.core_apis]
}

# IAM roles for frontend service account (minimal permissions)
resource "google_service_account_iam_member" "frontend_roles" {
  service_account_id = google_service_account.frontend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[missing-table/missing-table-frontend]"

  depends_on = [google_project_service.core_apis]
}

# IAM roles for CI/CD service account
resource "google_project_iam_member" "cicd_roles" {
  for_each = toset([
    "roles/container.developer",
    "roles/storage.admin", # For artifact storage
    "roles/cloudbuild.builds.editor",
    "roles/run.developer",
    "roles/iam.serviceAccountUser"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cicd.email}"

  depends_on = [google_project_service.core_apis]
}

# IAM roles for monitoring service account
resource "google_project_iam_member" "monitoring_roles" {
  for_each = toset([
    "roles/monitoring.admin",
    "roles/logging.admin",
    "roles/cloudtrace.admin",
    "roles/clouddebugger.user",
    "roles/cloudprofiler.agent"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.monitoring.email}"

  depends_on = [google_project_service.core_apis]
}

# IAM roles for backup service account
resource "google_project_iam_member" "backup_roles" {
  for_each = toset([
    "roles/cloudsql.admin",
    "roles/storage.admin",
    "roles/secretmanager.admin"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.backup.email}"

  depends_on = [google_project_service.core_apis]
}

# IAM roles for security service account
resource "google_project_iam_member" "security_roles" {
  for_each = toset([
    "roles/securitycenter.admin",
    "roles/binaryauthorization.attestorsAdmin",
    "roles/containeranalysis.admin",
    "roles/cloudasset.viewer"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.security.email}"

  depends_on = [google_project_service.security_apis]
}

# Custom IAM role for backend with minimal permissions
resource "google_project_iam_custom_role" "backend_minimal" {
  role_id     = "missingTableBackendMinimal"
  title       = "Missing Table Backend Minimal Role"
  description = "Custom role with minimal permissions for the backend application"
  stage       = "GA"

  permissions = [
    "cloudsql.instances.connect",
    "secretmanager.versions.access",
    "monitoring.timeSeries.create",
    "logging.logEntries.create",
    "cloudtrace.traces.patch"
  ]

  depends_on = [google_project_service.core_apis]
}

# Assign custom role to backend service account
resource "google_project_iam_member" "backend_custom_role" {
  project = var.project_id
  role    = google_project_iam_custom_role.backend_minimal.id
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Service Account Keys (disabled by organization policy, using Workload Identity instead)
# Keys are intentionally not created for security best practices

# Workload Identity binding for backend
resource "google_service_account_iam_member" "backend_workload_identity" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[missing-table/missing-table-backend]"

  depends_on = [google_project_service.core_apis]
}

# Workload Identity binding for frontend
resource "google_service_account_iam_member" "frontend_workload_identity" {
  service_account_id = google_service_account.frontend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[missing-table/missing-table-frontend]"

  depends_on = [google_project_service.core_apis]
}

# GitHub Actions Workload Identity Federation
resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions"
  disabled                  = false

  depends_on = [google_project_service.core_apis]
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC identity pool provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  depends_on = [google_project_service.core_apis]
}

# Allow GitHub Actions to use CI/CD service account
resource "google_service_account_iam_member" "github_actions_cicd" {
  service_account_id = google_service_account.cicd.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/silverbeer/missing-table"

  depends_on = [google_project_service.core_apis]
}

# Service Account monitoring and alerting
resource "google_logging_metric" "service_account_usage" {
  name   = "service_account_usage"
  filter = "protoPayload.serviceName=\"iam.googleapis.com\" AND protoPayload.methodName=\"google.iam.admin.v1.IAM.CreateServiceAccount\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Service Account Creation Events"
  }

  label_extractors = {
    "user" = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    "service_account" = "EXTRACT(protoPayload.request.accountId)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Alert for unexpected service account creation
resource "google_monitoring_alert_policy" "service_account_creation" {
  display_name = "Unexpected Service Account Creation - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Service account created"

    condition_threshold {
      filter          = "resource.type=\"global\" AND metric.type=\"logging.googleapis.com/user/service_account_usage\""
      duration        = "60s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
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

# Service Account audit logging
resource "google_project_iam_audit_config" "service_accounts" {
  project = var.project_id
  service = "iam.googleapis.com"

  audit_log_config {
    log_type = "ADMIN_READ"
  }
  
  audit_log_config {
    log_type = "DATA_READ"
  }
  
  audit_log_config {
    log_type = "DATA_WRITE"
  }

  depends_on = [google_project_service.core_apis]
}

# Service Account impersonation logging
resource "google_logging_metric" "service_account_impersonation" {
  name   = "service_account_impersonation"
  filter = "protoPayload.serviceName=\"iamcredentials.googleapis.com\" AND protoPayload.methodName=\"GenerateAccessToken\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Service Account Impersonation Events"
  }

  label_extractors = {
    "user" = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    "target_service_account" = "EXTRACT(protoPayload.resourceName)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Output service account emails for use in Kubernetes manifests
output "service_account_emails" {
  description = "Service account emails for Workload Identity configuration"
  value = {
    backend    = google_service_account.backend.email
    frontend   = google_service_account.frontend.email
    cicd       = google_service_account.cicd.email
    monitoring = google_service_account.monitoring.email
    backup     = google_service_account.backup.email
    security   = google_service_account.security.email
  }
  sensitive = false
}

output "workload_identity_pool_name" {
  description = "Workload Identity Pool name for GitHub Actions"
  value       = google_iam_workload_identity_pool.github_actions.name
  sensitive   = false
}