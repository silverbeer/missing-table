# Variables for Secure IAM Policies Module

# Project configuration
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "production"
}

# User and group role assignments
variable "project_admin_members" {
  description = "List of members to assign project admin roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.project_admin_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "security_admin_members" {
  description = "List of members to assign security admin roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.security_admin_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "security_auditor_members" {
  description = "List of members to assign security auditor roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.security_auditor_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "gke_operator_members" {
  description = "List of members to assign GKE operator roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.gke_operator_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "database_admin_members" {
  description = "List of members to assign database admin roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.database_admin_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "developer_members" {
  description = "List of members to assign developer roles"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.developer_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

variable "emergency_admin_members" {
  description = "List of members to assign emergency admin roles with time-based conditions"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for member in var.emergency_admin_members : can(regex("^(user:|group:|serviceAccount:|domain:)", member))
    ])
    error_message = "All members must be prefixed with user:, group:, serviceAccount:, or domain:."
  }
}

# Emergency access configuration
variable "emergency_access_start_hour" {
  description = "Start hour for emergency access window (0-23)"
  type        = number
  default     = 0
  
  validation {
    condition     = var.emergency_access_start_hour >= 0 && var.emergency_access_start_hour <= 23
    error_message = "Emergency access start hour must be between 0 and 23."
  }
}

variable "emergency_access_end_hour" {
  description = "End hour for emergency access window (0-23)"
  type        = number
  default     = 23
  
  validation {
    condition     = var.emergency_access_end_hour >= 0 && var.emergency_access_end_hour <= 23
    error_message = "Emergency access end hour must be between 0 and 23."
  }
}

# Workload Identity configuration
variable "workload_identity_namespace" {
  description = "Kubernetes namespace for workload identity binding"
  type        = string
  default     = "default"
}

variable "workload_identity_service_account" {
  description = "Kubernetes service account name for workload identity"
  type        = string
  default     = "gke-workload-sa"
}

variable "application_namespace" {
  description = "Kubernetes namespace for application workload identity"
  type        = string
  default     = "default"
}

variable "application_service_account" {
  description = "Kubernetes service account name for application workload"
  type        = string
  default     = "application-sa"
}

# Resource-specific configurations
variable "application_secret_names" {
  description = "List of Secret Manager secret names for application access"
  type        = list(string)
  default     = []
}

variable "enable_application_encryption" {
  description = "Enable application-level encryption with KMS"
  type        = bool
  default     = false
}

variable "application_kms_key_id" {
  description = "KMS key ID for application encryption"
  type        = string
  default     = ""
}

variable "application_storage_buckets" {
  description = "List of storage bucket names for application access"
  type        = list(string)
  default     = []
}

# Monitoring and alerting
variable "iam_notification_channels" {
  description = "List of notification channels for IAM alerts"
  type        = list(string)
  default     = []
}

# Service account configuration
variable "create_gke_workload_sa" {
  description = "Create GKE workload service account"
  type        = bool
  default     = true
}

variable "create_application_sa" {
  description = "Create application service account"
  type        = bool
  default     = true
}

variable "create_cicd_sa" {
  description = "Create CI/CD service account"
  type        = bool
  default     = true
}

variable "create_monitoring_sa" {
  description = "Create monitoring service account"
  type        = bool
  default     = true
}

variable "create_backup_sa" {
  description = "Create backup service account"
  type        = bool
  default     = true
}

# Custom role configuration
variable "enable_custom_roles" {
  description = "Enable creation of custom IAM roles"
  type        = bool
  default     = true
}

variable "custom_role_permissions" {
  description = "Additional permissions for custom roles"
  type = object({
    gke_cluster_operator  = optional(list(string), [])
    application_deployer  = optional(list(string), [])
    security_auditor     = optional(list(string), [])
    database_admin       = optional(list(string), [])
  })
  default = {}
}

# Policy enforcement settings
variable "enforce_domain_restriction" {
  description = "Enforce domain restriction for user accounts"
  type        = bool
  default     = true
}

variable "allowed_domains" {
  description = "List of allowed domains for user accounts"
  type        = list(string)
  default     = []
}

variable "enforce_mfa_requirement" {
  description = "Enforce MFA requirement for privileged roles"
  type        = bool
  default     = true
}

# Audit and compliance settings
variable "enable_audit_logging" {
  description = "Enable comprehensive audit logging for IAM operations"
  type        = bool
  default     = true
}

variable "audit_log_retention_days" {
  description = "Number of days to retain audit logs"
  type        = number
  default     = 365
  
  validation {
    condition     = var.audit_log_retention_days >= 30 && var.audit_log_retention_days <= 3653
    error_message = "Audit log retention days must be between 30 and 3653 (10 years)."
  }
}

variable "enable_privileged_access_monitoring" {
  description = "Enable monitoring for privileged access activities"
  type        = bool
  default     = true
}

# Resource labels
variable "iam_labels" {
  description = "Labels to apply to IAM resources"
  type        = map(string)
  default     = {}
}