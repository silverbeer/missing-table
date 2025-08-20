# Secure IAM Policies Module with Least Privilege Principle
# This module creates IAM policies following security best practices and principle of least privilege

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
resource "random_id" "iam_suffix" {
  byte_length = 4
}

# Data sources
data "google_project" "current" {
  project_id = var.project_id
}

data "google_client_config" "current" {}

# Custom IAM roles for fine-grained access control

# GKE Cluster Operator - minimal permissions for cluster operations
resource "google_project_iam_custom_role" "gke_cluster_operator" {
  role_id     = "gkeClusterOperator_${random_id.iam_suffix.hex}"
  project     = var.project_id
  title       = "GKE Cluster Operator"
  description = "Minimal permissions for GKE cluster operations"
  stage       = "GA"

  permissions = [
    # Container/GKE permissions
    "container.clusters.get",
    "container.clusters.list",
    "container.operations.get",
    "container.operations.list",
    
    # Node pool management
    "container.nodePools.get",
    "container.nodePools.list",
    
    # Workload management
    "container.pods.get",
    "container.pods.list",
    "container.services.get",
    "container.services.list",
    
    # Logging and monitoring
    "logging.logEntries.list",
    "monitoring.metricDescriptors.list",
    "monitoring.timeSeries.list",
    
    # Service accounts (read-only)
    "iam.serviceAccounts.get",
    "iam.serviceAccounts.list"
  ]
}

# Application Deployer - permissions for deploying applications to GKE
resource "google_project_iam_custom_role" "application_deployer" {
  role_id     = "applicationDeployer_${random_id.iam_suffix.hex}"
  project     = var.project_id
  title       = "Application Deployer"
  description = "Permissions for deploying applications to GKE clusters"
  stage       = "GA"

  permissions = [
    # Container/GKE permissions for deployment
    "container.clusters.get",
    "container.clusters.getCredentials",
    
    # Artifact Registry (for container images)
    "artifactregistry.repositories.get",
    "artifactregistry.repositories.list",
    "artifactregistry.packages.get",
    "artifactregistry.packages.list",
    "artifactregistry.versions.get",
    "artifactregistry.versions.list",
    
    # Secret Manager (read-only for application secrets)
    "secretmanager.secrets.get",
    "secretmanager.versions.get",
    "secretmanager.versions.access",
    
    # Logging (for application logs)
    "logging.logEntries.create",
    "logging.logEntries.list",
    
    # Monitoring (for application metrics)
    "monitoring.metricDescriptors.create",
    "monitoring.metricDescriptors.get",
    "monitoring.timeSeries.create"
  ]
}

# Security Auditor - read-only access for security auditing
resource "google_project_iam_custom_role" "security_auditor" {
  role_id     = "securityAuditor_${random_id.iam_suffix.hex}"
  project     = var.project_id
  title       = "Security Auditor"
  description = "Read-only access for security auditing and compliance"
  stage       = "GA"

  permissions = [
    # IAM auditing
    "iam.roles.get",
    "iam.roles.list",
    "iam.serviceAccounts.get",
    "iam.serviceAccounts.list",
    "resourcemanager.projects.getIamPolicy",
    
    # Security-related resources
    "securitycenter.assets.list",
    "securitycenter.findings.list",
    "securitycenter.sources.get",
    "securitycenter.sources.list",
    
    # Binary Authorization
    "binaryauthorization.policy.get",
    "binaryauthorization.attestors.list",
    
    # KMS auditing
    "cloudkms.cryptoKeys.get",
    "cloudkms.cryptoKeys.list",
    "cloudkms.keyRings.get",
    "cloudkms.keyRings.list",
    "cloudkms.cryptoKeys.getIamPolicy",
    
    # Network security
    "compute.networks.get",
    "compute.networks.list",
    "compute.subnetworks.get",
    "compute.subnetworks.list",
    "compute.firewalls.get",
    "compute.firewalls.list",
    
    # Logging and monitoring
    "logging.logs.list",
    "logging.logEntries.list",
    "monitoring.alertPolicies.get",
    "monitoring.alertPolicies.list"
  ]
}

# Database Administrator - minimal permissions for database operations
resource "google_project_iam_custom_role" "database_admin" {
  role_id     = "databaseAdmin_${random_id.iam_suffix.hex}"
  project     = var.project_id
  title       = "Database Administrator"
  description = "Minimal permissions for database administration"
  stage       = "GA"

  permissions = [
    # Cloud SQL
    "cloudsql.instances.get",
    "cloudsql.instances.list",
    "cloudsql.instances.connect",
    "cloudsql.databases.get",
    "cloudsql.databases.list",
    "cloudsql.users.get",
    "cloudsql.users.list",
    
    # Backup management
    "cloudsql.backupRuns.get",
    "cloudsql.backupRuns.list",
    
    # Secret Manager (for database credentials)
    "secretmanager.secrets.get",
    "secretmanager.versions.get",
    "secretmanager.versions.access",
    
    # Monitoring
    "monitoring.metricDescriptors.list",
    "monitoring.timeSeries.list",
    
    # Logging
    "logging.logEntries.list"
  ]
}

# Service Accounts with minimal permissions

# GKE Workload Service Account
resource "google_service_account" "gke_workload" {
  account_id   = "gke-workload-${random_id.iam_suffix.hex}"
  display_name = "GKE Workload Service Account"
  description  = "Service account for GKE workloads with minimal required permissions"
  project      = var.project_id
}

# Application Service Account
resource "google_service_account" "application" {
  account_id   = "application-${random_id.iam_suffix.hex}"
  display_name = "Application Service Account"
  description  = "Service account for application workloads"
  project      = var.project_id
}

# CI/CD Service Account
resource "google_service_account" "cicd" {
  account_id   = "cicd-${random_id.iam_suffix.hex}"
  display_name = "CI/CD Service Account"
  description  = "Service account for CI/CD pipelines"
  project      = var.project_id
}

# Monitoring Service Account
resource "google_service_account" "monitoring" {
  account_id   = "monitoring-${random_id.iam_suffix.hex}"
  display_name = "Monitoring Service Account"
  description  = "Service account for monitoring and alerting"
  project      = var.project_id
}

# Backup Service Account
resource "google_service_account" "backup" {
  account_id   = "backup-${random_id.iam_suffix.hex}"
  display_name = "Backup Service Account"
  description  = "Service account for backup operations"
  project      = var.project_id
}

# IAM bindings for service accounts

# GKE Workload Service Account - minimal GKE permissions
resource "google_project_iam_member" "gke_workload_permissions" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_workload.email}"
}

# Application Service Account - application-specific permissions
resource "google_project_iam_member" "application_permissions" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/secretmanager.secretAccessor"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.application.email}"
}

# CI/CD Service Account - deployment permissions
resource "google_project_iam_member" "cicd_permissions" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/container.developer",
    "roles/logging.logWriter"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

# Custom role bindings for CI/CD
resource "google_project_iam_member" "cicd_custom_roles" {
  for_each = toset([
    "projects/${var.project_id}/roles/${google_project_iam_custom_role.application_deployer.role_id}"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

# Monitoring Service Account - monitoring permissions
resource "google_project_iam_member" "monitoring_permissions" {
  for_each = toset([
    "roles/monitoring.editor",
    "roles/logging.viewer",
    "roles/alerting.notificationChannelEditor"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.monitoring.email}"
}

# Backup Service Account - backup permissions
resource "google_project_iam_member" "backup_permissions" {
  for_each = toset([
    "roles/storage.admin",
    "roles/cloudsql.admin",
    "roles/logging.logWriter"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.backup.email}"
}

# Workload Identity bindings for GKE
resource "google_service_account_iam_binding" "gke_workload_identity" {
  service_account_id = google_service_account.gke_workload.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.workload_identity_namespace}/${var.workload_identity_service_account}]"
  ]
}

# Application Workload Identity binding
resource "google_service_account_iam_binding" "application_workload_identity" {
  service_account_id = google_service_account.application.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.application_namespace}/${var.application_service_account}]"
  ]
}

# User and group role assignments (if specified)

# Project administrators
resource "google_project_iam_member" "project_admins" {
  for_each = toset(var.project_admin_members)
  
  project = var.project_id
  role    = "roles/owner"
  member  = each.value
}

# Security administrators
resource "google_project_iam_member" "security_admins" {
  for_each = toset(var.security_admin_members)
  
  project = var.project_id
  role    = "roles/securitycenter.admin"
  member  = each.value
}

# Custom role assignments for security auditors
resource "google_project_iam_member" "security_auditors" {
  for_each = toset(var.security_auditor_members)
  
  project = var.project_id
  role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.security_auditor.role_id}"
  member  = each.value
}

# GKE cluster operators
resource "google_project_iam_member" "gke_operators" {
  for_each = toset(var.gke_operator_members)
  
  project = var.project_id
  role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.gke_cluster_operator.role_id}"
  member  = each.value
}

# Database administrators
resource "google_project_iam_member" "database_admins" {
  for_each = toset(var.database_admin_members)
  
  project = var.project_id
  role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.database_admin.role_id}"
  member  = each.value
}

# Application developers (read-only access to application resources)
resource "google_project_iam_member" "developers" {
  for_each = toset(var.developer_members)
  
  project = var.project_id
  role    = "roles/viewer"
  member  = each.value
}

# Additional developer permissions for specific resources
resource "google_project_iam_member" "developer_container_access" {
  for_each = toset(var.developer_members)
  
  project = var.project_id
  role    = "roles/container.viewer"
  member  = each.value
}

# Conditional IAM policies for enhanced security

# Time-based access for emergency administrators
resource "google_project_iam_member" "emergency_admin_conditional" {
  count = length(var.emergency_admin_members) > 0 ? 1 : 0
  
  project = var.project_id
  role    = "roles/editor"
  member  = var.emergency_admin_members[0]
  
  condition {
    title       = "Emergency Access Window"
    description = "Allow emergency admin access only during defined time windows"
    expression  = "request.time.getHours() >= ${var.emergency_access_start_hour} && request.time.getHours() <= ${var.emergency_access_end_hour}"
  }
}

# Resource-specific IAM policies

# Secret Manager access policies (fine-grained)
resource "google_secret_manager_secret_iam_binding" "application_secrets" {
  for_each = toset(var.application_secret_names)
  
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  
  members = [
    "serviceAccount:${google_service_account.application.email}",
    "serviceAccount:${google_service_account.gke_workload.email}"
  ]
}

# KMS key access policies
resource "google_kms_crypto_key_iam_binding" "application_encryption" {
  count = var.enable_application_encryption ? 1 : 0
  
  crypto_key_id = var.application_kms_key_id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  
  members = [
    "serviceAccount:${google_service_account.application.email}"
  ]
}

# Storage bucket access policies (if specified)
resource "google_storage_bucket_iam_binding" "application_storage" {
  for_each = toset(var.application_storage_buckets)
  
  bucket = each.value
  role   = "roles/storage.objectUser"
  
  members = [
    "serviceAccount:${google_service_account.application.email}",
    "serviceAccount:${google_service_account.backup.email}"
  ]
}

# IAM policy monitoring and alerting

# IAM policy changes monitoring
resource "google_logging_metric" "iam_policy_changes" {
  name   = "iam-policy-changes-${random_id.iam_suffix.hex}"
  project = var.project_id
  filter = <<-EOT
    resource.type="project"
    protoPayload.serviceName="cloudresourcemanager.googleapis.com"
    (
      protoPayload.methodName="SetIamPolicy" OR
      protoPayload.methodName="google.iam.admin.v1.CreateServiceAccount" OR
      protoPayload.methodName="google.iam.admin.v1.DeleteServiceAccount" OR
      protoPayload.methodName="google.iam.admin.v1.CreateRole" OR
      protoPayload.methodName="google.iam.admin.v1.DeleteRole"
    )
  EOT

  label_extractors = {
    user   = "protoPayload.authenticationInfo.principalEmail"
    method = "protoPayload.methodName"
  }

  metric_descriptor {
    metric_kind = "COUNTER"
    value_type  = "INT64"
    display_name = "IAM Policy Changes"
  }
}

# Alert policy for IAM changes
resource "google_monitoring_alert_policy" "iam_policy_alerts" {
  display_name = "IAM Policy Changes Alert"
  project      = var.project_id

  conditions {
    display_name = "Unauthorized IAM policy changes detected"

    condition_threshold {
      filter          = "resource.type=\"project\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.iam_policy_changes.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.iam_notification_channels

  alert_strategy {
    auto_close = "1800s"
  }
}

# Service account key monitoring (security best practice: avoid service account keys)
resource "google_logging_metric" "service_account_key_creation" {
  name   = "service-account-key-creation-${random_id.iam_suffix.hex}"
  project = var.project_id
  filter = <<-EOT
    resource.type="service_account"
    protoPayload.serviceName="iam.googleapis.com"
    protoPayload.methodName="google.iam.admin.v1.CreateServiceAccountKey"
  EOT

  label_extractors = {
    user            = "protoPayload.authenticationInfo.principalEmail"
    service_account = "protoPayload.resourceName"
  }

  metric_descriptor {
    metric_kind = "COUNTER"
    value_type  = "INT64"
    display_name = "Service Account Key Creation"
  }
}

# Alert for service account key creation (should be avoided)
resource "google_monitoring_alert_policy" "service_account_key_alerts" {
  display_name = "Service Account Key Creation Alert"
  project      = var.project_id

  conditions {
    display_name = "Service account key created (security risk)"

    condition_threshold {
      filter          = "resource.type=\"service_account\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.service_account_key_creation.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.iam_notification_channels

  alert_strategy {
    auto_close = "3600s"
  }
}