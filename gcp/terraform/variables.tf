# GCP Terraform Variables for Missing Table Application
# Security-first configuration with comprehensive settings

# Project Configuration
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Project ID must be 6-30 characters, start with a letter, and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "organization_id" {
  description = "GCP Organization ID (optional, for organization policies)"
  type        = string
  default     = ""
}

variable "billing_account_id" {
  description = "GCP Billing Account ID"
  type        = string
  validation {
    condition     = can(regex("^[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}$", var.billing_account_id))
    error_message = "Billing account ID must be in format XXXXXX-XXXXXX-XXXXXX."
  }
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
  validation {
    condition = contains([
      "us-central1", "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
      "europe-north1", "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6",
      "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", "asia-northeast3",
      "asia-south1", "asia-southeast1", "asia-southeast2"
    ], var.region)
    error_message = "Region must be a valid GCP region."
  }
}

variable "zone" {
  description = "GCP zone for zonal resources"
  type        = string
  default     = "us-central1-a"
}

variable "secondary_region" {
  description = "Secondary region for disaster recovery"
  type        = string
  default     = "us-east1"
}

# Application Configuration
variable "app_name" {
  description = "Application name"
  type        = string
  default     = "missing-table"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}[a-z0-9]$", var.app_name))
    error_message = "App name must be 4-22 characters, start with a letter, and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "app_version" {
  description = "Application version"
  type        = string
  default     = "1.4.0"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

# Contact Information
variable "admin_email" {
  description = "Administrator email address"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.admin_email))
    error_message = "Must be a valid email address."
  }
}

variable "security_contact_email" {
  description = "Security contact email address"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.security_contact_email))
    error_message = "Must be a valid email address."
  }
}

variable "devops_contact_email" {
  description = "DevOps contact email address"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.devops_contact_email))
    error_message = "Must be a valid email address."
  }
}

# Required APIs
variable "required_apis" {
  description = "List of required GCP APIs"
  type        = list(string)
  default = [
    "compute.googleapis.com",
    "container.googleapis.com",
    "containerregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com",
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "clouddebugger.googleapis.com",
    "cloudprofiler.googleapis.com",
    "securitycenter.googleapis.com",
    "binaryauthorization.googleapis.com",
    "containersecurity.googleapis.com",
    "containeranalysis.googleapis.com",
    "cloudasset.googleapis.com",
    "accesscontextmanager.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "dns.googleapis.com",
    "certificatemanager.googleapis.com",
    "networkmanagement.googleapis.com",
    "servicenetworking.googleapis.com"
  ]
}

# Essential IAM roles for project administrators
variable "essential_project_roles" {
  description = "Essential IAM roles for project administration"
  type        = list(string)
  default = [
    "roles/owner",
    "roles/iam.securityAdmin",
    "roles/logging.admin",
    "roles/monitoring.admin"
  ]
}

# Security Configuration
variable "enable_vpc_sc" {
  description = "Enable VPC Service Controls"
  type        = bool
  default     = false # Set to true for high-security environments
}

variable "kms_protection_level" {
  description = "KMS key protection level"
  type        = string
  default     = "SOFTWARE"
  validation {
    condition     = contains(["SOFTWARE", "HSM"], var.kms_protection_level)
    error_message = "KMS protection level must be SOFTWARE or HSM."
  }
}

variable "enable_binary_authorization" {
  description = "Enable Binary Authorization for container security"
  type        = bool
  default     = true
}

variable "enable_shielded_nodes" {
  description = "Enable Shielded GKE nodes"
  type        = bool
  default     = true
}

variable "enable_workload_identity" {
  description = "Enable Workload Identity for secure pod-to-GCP authentication"
  type        = bool
  default     = true
}

variable "enable_private_nodes" {
  description = "Enable private GKE nodes"
  type        = bool
  default     = true
}

variable "enable_network_policy" {
  description = "Enable Kubernetes network policies"
  type        = bool
  default     = true
}

variable "enable_pod_security_policy" {
  description = "Enable Pod Security Policy"
  type        = bool
  default     = true
}

variable "authorized_networks" {
  description = "Authorized networks for GKE cluster access"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = [
    {
      cidr_block   = "0.0.0.0/0"
      display_name = "All networks (replace with specific IPs in production)"
    }
  ]
}

# GKE Configuration
variable "gke_node_count" {
  description = "Number of nodes in the GKE cluster"
  type        = number
  default     = 3
  validation {
    condition     = var.gke_node_count >= 1 && var.gke_node_count <= 100
    error_message = "Node count must be between 1 and 100."
  }
}

variable "gke_machine_type" {
  description = "Machine type for GKE nodes"
  type        = string
  default     = "e2-standard-2"
}

variable "gke_disk_size_gb" {
  description = "Disk size for GKE nodes"
  type        = number
  default     = 50
  validation {
    condition     = var.gke_disk_size_gb >= 20 && var.gke_disk_size_gb <= 1000
    error_message = "Disk size must be between 20 and 1000 GB."
  }
}

variable "gke_disk_type" {
  description = "Disk type for GKE nodes"
  type        = string
  default     = "pd-ssd"
  validation {
    condition     = contains(["pd-standard", "pd-ssd", "pd-balanced"], var.gke_disk_type)
    error_message = "Disk type must be pd-standard, pd-ssd, or pd-balanced."
  }
}

variable "gke_auto_scaling" {
  description = "Enable auto-scaling for GKE cluster"
  type        = bool
  default     = true
}

variable "gke_min_node_count" {
  description = "Minimum number of nodes in auto-scaling"
  type        = number
  default     = 1
}

variable "gke_max_node_count" {
  description = "Maximum number of nodes in auto-scaling"
  type        = number
  default     = 10
}

# Cloud SQL Configuration
variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_disk_size" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 20
  validation {
    condition     = var.db_disk_size >= 10 && var.db_disk_size <= 30720
    error_message = "Database disk size must be between 10 and 30720 GB."
  }
}

variable "db_backup_enabled" {
  description = "Enable automated backups for Cloud SQL"
  type        = bool
  default     = true
}

variable "db_backup_start_time" {
  description = "Start time for automated backups (HH:MM format)"
  type        = string
  default     = "03:00"
}

variable "db_maintenance_window_day" {
  description = "Day of week for maintenance window (1=Monday, 7=Sunday)"
  type        = number
  default     = 7
  validation {
    condition     = var.db_maintenance_window_day >= 1 && var.db_maintenance_window_day <= 7
    error_message = "Maintenance window day must be between 1 (Monday) and 7 (Sunday)."
  }
}

variable "db_maintenance_window_hour" {
  description = "Hour for maintenance window (0-23)"
  type        = number
  default     = 4
  validation {
    condition     = var.db_maintenance_window_hour >= 0 && var.db_maintenance_window_hour <= 23
    error_message = "Maintenance window hour must be between 0 and 23."
  }
}

# Monitoring Configuration
variable "log_retention_days" {
  description = "Log retention period in days"
  type        = number
  default     = 30
  validation {
    condition     = var.log_retention_days >= 1 && var.log_retention_days <= 3653
    error_message = "Log retention must be between 1 and 3653 days."
  }
}

variable "enable_uptime_checks" {
  description = "Enable uptime monitoring checks"
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.alert_email))
    error_message = "Must be a valid email address."
  }
}

# Billing Configuration
variable "budget_amount" {
  description = "Monthly budget amount in USD"
  type        = number
  default     = 100
  validation {
    condition     = var.budget_amount > 0
    error_message = "Budget amount must be greater than 0."
  }
}

variable "budget_alert_thresholds" {
  description = "Budget alert thresholds as percentages"
  type        = list(number)
  default     = [0.5, 0.75, 0.9, 1.0]
  validation {
    condition     = alltrue([for threshold in var.budget_alert_thresholds : threshold > 0 && threshold <= 1])
    error_message = "Budget thresholds must be between 0 and 1 (representing percentages)."
  }
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block."
  }
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = true
}

variable "enable_dns_logging" {
  description = "Enable DNS logging"
  type        = bool
  default     = true
}

# Labels
variable "additional_labels" {
  description = "Additional labels to apply to resources"
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([
      for k, v in var.additional_labels : can(regex("^[a-z0-9_-]{1,63}$", k)) && can(regex("^[a-z0-9_-]{0,63}$", v))
    ])
    error_message = "Label keys and values must contain only lowercase letters, numbers, underscores, and hyphens, and be 1-63 characters long."
  }
}