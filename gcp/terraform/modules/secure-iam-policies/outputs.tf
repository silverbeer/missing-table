# Outputs for Secure IAM Policies Module

# Custom role outputs
output "custom_roles" {
  description = "Custom IAM roles created by this module"
  value = var.enable_custom_roles ? {
    gke_cluster_operator = {
      id          = google_project_iam_custom_role.gke_cluster_operator.role_id
      name        = google_project_iam_custom_role.gke_cluster_operator.name
      title       = google_project_iam_custom_role.gke_cluster_operator.title
      permissions = google_project_iam_custom_role.gke_cluster_operator.permissions
    }
    application_deployer = {
      id          = google_project_iam_custom_role.application_deployer.role_id
      name        = google_project_iam_custom_role.application_deployer.name
      title       = google_project_iam_custom_role.application_deployer.title
      permissions = google_project_iam_custom_role.application_deployer.permissions
    }
    security_auditor = {
      id          = google_project_iam_custom_role.security_auditor.role_id
      name        = google_project_iam_custom_role.security_auditor.name
      title       = google_project_iam_custom_role.security_auditor.title
      permissions = google_project_iam_custom_role.security_auditor.permissions
    }
    database_admin = {
      id          = google_project_iam_custom_role.database_admin.role_id
      name        = google_project_iam_custom_role.database_admin.name
      title       = google_project_iam_custom_role.database_admin.title
      permissions = google_project_iam_custom_role.database_admin.permissions
    }
  } : {}
}

# Service account outputs
output "service_accounts" {
  description = "Service accounts created by this module"
  value = {
    gke_workload = var.create_gke_workload_sa ? {
      email       = google_service_account.gke_workload.email
      id          = google_service_account.gke_workload.id
      unique_id   = google_service_account.gke_workload.unique_id
      name        = google_service_account.gke_workload.name
      member      = "serviceAccount:${google_service_account.gke_workload.email}"
    } : null
    
    application = var.create_application_sa ? {
      email       = google_service_account.application.email
      id          = google_service_account.application.id
      unique_id   = google_service_account.application.unique_id
      name        = google_service_account.application.name
      member      = "serviceAccount:${google_service_account.application.email}"
    } : null
    
    cicd = var.create_cicd_sa ? {
      email       = google_service_account.cicd.email
      id          = google_service_account.cicd.id
      unique_id   = google_service_account.cicd.unique_id
      name        = google_service_account.cicd.name
      member      = "serviceAccount:${google_service_account.cicd.email}"
    } : null
    
    monitoring = var.create_monitoring_sa ? {
      email       = google_service_account.monitoring.email
      id          = google_service_account.monitoring.id
      unique_id   = google_service_account.monitoring.unique_id
      name        = google_service_account.monitoring.name
      member      = "serviceAccount:${google_service_account.monitoring.email}"
    } : null
    
    backup = var.create_backup_sa ? {
      email       = google_service_account.backup.email
      id          = google_service_account.backup.id
      unique_id   = google_service_account.backup.unique_id
      name        = google_service_account.backup.name
      member      = "serviceAccount:${google_service_account.backup.email}"
    } : null
  }
}

# Workload Identity configuration outputs
output "workload_identity_config" {
  description = "Workload Identity configuration for Kubernetes service accounts"
  value = {
    gke_workload = {
      gcp_service_account     = var.create_gke_workload_sa ? google_service_account.gke_workload.email : null
      kubernetes_namespace    = var.workload_identity_namespace
      kubernetes_service_account = var.workload_identity_service_account
      annotation_key         = "iam.gke.io/gcp-service-account"
      annotation_value       = var.create_gke_workload_sa ? google_service_account.gke_workload.email : null
    }
    
    application = {
      gcp_service_account     = var.create_application_sa ? google_service_account.application.email : null
      kubernetes_namespace    = var.application_namespace
      kubernetes_service_account = var.application_service_account
      annotation_key         = "iam.gke.io/gcp-service-account"
      annotation_value       = var.create_application_sa ? google_service_account.application.email : null
    }
  }
}

# Role assignments summary
output "role_assignments" {
  description = "Summary of role assignments by member type"
  value = {
    project_admins = {
      role    = "roles/owner"
      members = var.project_admin_members
    }
    
    security_admins = {
      role    = "roles/securitycenter.admin"
      members = var.security_admin_members
    }
    
    security_auditors = var.enable_custom_roles ? {
      role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.security_auditor.role_id}"
      members = var.security_auditor_members
    } : null
    
    gke_operators = var.enable_custom_roles ? {
      role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.gke_cluster_operator.role_id}"
      members = var.gke_operator_members
    } : null
    
    database_admins = var.enable_custom_roles ? {
      role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.database_admin.role_id}"
      members = var.database_admin_members
    } : null
    
    developers = {
      roles = [
        "roles/viewer",
        "roles/container.viewer"
      ]
      members = var.developer_members
    }
  }
}

# Monitoring outputs
output "iam_monitoring" {
  description = "IAM monitoring and alerting resources"
  value = {
    policy_changes_metric = {
      name = google_logging_metric.iam_policy_changes.name
      id   = google_logging_metric.iam_policy_changes.id
    }
    
    service_account_key_metric = {
      name = google_logging_metric.service_account_key_creation.name
      id   = google_logging_metric.service_account_key_creation.id
    }
    
    policy_changes_alert = {
      name = google_monitoring_alert_policy.iam_policy_alerts.name
      id   = google_monitoring_alert_policy.iam_policy_alerts.id
    }
    
    service_account_key_alert = {
      name = google_monitoring_alert_policy.service_account_key_alerts.name
      id   = google_monitoring_alert_policy.service_account_key_alerts.id
    }
  }
}

# Security configuration summary
output "security_configuration" {
  description = "Summary of security configuration applied"
  value = {
    custom_roles_enabled           = var.enable_custom_roles
    domain_restriction_enforced    = var.enforce_domain_restriction
    allowed_domains               = var.allowed_domains
    mfa_requirement_enforced      = var.enforce_mfa_requirement
    audit_logging_enabled         = var.enable_audit_logging
    audit_log_retention_days      = var.audit_log_retention_days
    privileged_access_monitoring  = var.enable_privileged_access_monitoring
    workload_identity_enabled     = true
    service_account_keys_monitored = true
    iam_policy_changes_monitored  = true
  }
}

# Kubernetes service account annotations for Workload Identity
output "kubernetes_service_account_annotations" {
  description = "Annotations to apply to Kubernetes service accounts for Workload Identity"
  value = {
    gke_workload = var.create_gke_workload_sa ? {
      "iam.gke.io/gcp-service-account" = google_service_account.gke_workload.email
    } : {}
    
    application = var.create_application_sa ? {
      "iam.gke.io/gcp-service-account" = google_service_account.application.email
    } : {}
  }
}

# Resource access configuration
output "resource_access_configuration" {
  description = "Configuration for resource-specific access controls"
  value = {
    secret_manager_secrets = var.application_secret_names
    kms_encryption_enabled = var.enable_application_encryption
    kms_key_id            = var.application_kms_key_id
    storage_buckets       = var.application_storage_buckets
  }
}

# Emergency access configuration
output "emergency_access_configuration" {
  description = "Emergency access configuration and time windows"
  value = {
    emergency_admin_members = var.emergency_admin_members
    access_window = {
      start_hour = var.emergency_access_start_hour
      end_hour   = var.emergency_access_end_hour
    }
    conditional_access_enabled = length(var.emergency_admin_members) > 0
  }
}

# Compliance and audit information
output "compliance_information" {
  description = "Information for compliance and audit purposes"
  value = {
    principle_of_least_privilege = "Implemented through custom roles with minimal required permissions"
    separation_of_duties         = "Implemented through role-based access control and custom roles"
    audit_trail                 = "All IAM operations logged and monitored with alerts"
    access_reviews              = "Roles and permissions defined in code for regular review"
    workload_identity           = "Eliminates need for service account keys in GKE"
    
    compliance_frameworks = [
      "SOC 2 Type II",
      "ISO 27001",
      "NIST Cybersecurity Framework",
      "CIS Controls"
    ]
    
    security_controls = [
      "CIS-IAM-1: Ensure security contact information is provided",
      "CIS-IAM-2: Ensure that multi-factor authentication is enabled",
      "CIS-IAM-3: Ensure that there are only GCP-managed service account keys",
      "CIS-IAM-4: Ensure that ServiceAccount has no Admin privileges",
      "CIS-IAM-5: Ensure that IAM users are not assigned Service Account User role",
      "CIS-IAM-6: Ensure that IAM users are not assigned Service Account Token Creator role"
    ]
  }
}