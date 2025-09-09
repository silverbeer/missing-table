# Variables for Secure GKE Autopilot Module

# Project and location
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for the cluster"
  type        = string
}

variable "cluster_name" {
  description = "The name of the GKE cluster"
  type        = string
  
  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,38}[a-z0-9])?$", var.cluster_name))
    error_message = "Cluster name must be 1-40 characters, start with lowercase letter, and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "production"
}

# Network configuration
variable "network_name" {
  description = "The VPC network name"
  type        = string
}

variable "subnetwork_name" {
  description = "The subnetwork name"
  type        = string
}

variable "pods_secondary_range_name" {
  description = "The name of the pods secondary IP range"
  type        = string
  default     = "pods"
}

variable "services_secondary_range_name" {
  description = "The name of the services secondary IP range"
  type        = string
  default     = "services"
}

# Private cluster configuration
variable "enable_private_endpoint" {
  description = "Enable private endpoint for the cluster master"
  type        = bool
  default     = true
}

variable "master_ipv4_cidr_block" {
  description = "The IP range in CIDR notation for the cluster master"
  type        = string
  default     = "10.0.0.0/28"
  
  validation {
    condition     = can(cidrhost(var.master_ipv4_cidr_block, 0))
    error_message = "Master CIDR block must be a valid CIDR notation."
  }
}

variable "enable_master_global_access" {
  description = "Enable global access to the cluster master"
  type        = bool
  default     = false
}

# Master authorized networks
variable "master_authorized_networks" {
  description = "List of master authorized networks"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

# Security configuration
variable "binary_authorization_evaluation_mode" {
  description = "Binary Authorization evaluation mode"
  type        = string
  default     = "PROJECT_SINGLETON_POLICY_ENFORCE"
  
  validation {
    condition = contains([
      "DISABLED",
      "PROJECT_SINGLETON_POLICY_ENFORCE",
      "POLICY_BINDINGS"
    ], var.binary_authorization_evaluation_mode)
    error_message = "Binary Authorization evaluation mode must be one of: DISABLED, PROJECT_SINGLETON_POLICY_ENFORCE, POLICY_BINDINGS."
  }
}

variable "pod_security_standard_level" {
  description = "Pod Security Standard level to enforce"
  type        = string
  default     = "restricted"
  
  validation {
    condition = contains([
      "privileged",
      "baseline", 
      "restricted"
    ], var.pod_security_standard_level)
    error_message = "Pod Security Standard level must be one of: privileged, baseline, restricted."
  }
}

# KMS configuration
variable "kms_key_rotation_period" {
  description = "Rotation period for KMS key"
  type        = string
  default     = "7776000s" # 90 days
}

# Service account configuration
variable "additional_node_service_account_roles" {
  description = "Additional IAM roles for the GKE node service account"
  type        = list(string)
  default     = []
}

# Cluster addons configuration
variable "disable_http_load_balancing" {
  description = "Disable HTTP load balancing addon"
  type        = bool
  default     = false
}

variable "enable_dns_cache" {
  description = "Enable DNS cache addon"
  type        = bool
  default     = true
}

variable "enable_backup_agent" {
  description = "Enable GKE Backup for Workloads"
  type        = bool
  default     = true
}

variable "enable_config_connector" {
  description = "Enable Config Connector addon"
  type        = bool
  default     = false
}

# Maintenance configuration
variable "maintenance_start_time" {
  description = "Start time for maintenance window (RFC 3339 format)"
  type        = string
  default     = "2023-01-01T02:00:00Z"
}

variable "maintenance_end_time" {
  description = "End time for maintenance window (RFC 3339 format)"
  type        = string
  default     = "2023-01-01T06:00:00Z"
}

variable "maintenance_recurrence" {
  description = "Recurrence rule for maintenance window (RFC 5545 format)"
  type        = string
  default     = "FREQ=WEEKLY;BYDAY=SA"
}

# Logging configuration
variable "logging_components" {
  description = "List of logging components to enable"
  type        = list(string)
  default = [
    "SYSTEM_COMPONENTS",
    "WORKLOADS",
    "API_SERVER"
  ]
  
  validation {
    condition = alltrue([
      for component in var.logging_components : contains([
        "SYSTEM_COMPONENTS",
        "WORKLOADS", 
        "API_SERVER"
      ], component)
    ])
    error_message = "Logging components must be from: SYSTEM_COMPONENTS, WORKLOADS, API_SERVER."
  }
}

# Monitoring configuration
variable "monitoring_components" {
  description = "List of monitoring components to enable"
  type        = list(string)
  default = [
    "SYSTEM_COMPONENTS",
    "WORKLOADS",
    "API_SERVER"
  ]
  
  validation {
    condition = alltrue([
      for component in var.monitoring_components : contains([
        "SYSTEM_COMPONENTS",
        "WORKLOADS",
        "API_SERVER"
      ], component)
    ])
    error_message = "Monitoring components must be from: SYSTEM_COMPONENTS, WORKLOADS, API_SERVER."
  }
}

variable "enable_managed_prometheus" {
  description = "Enable managed Prometheus"
  type        = bool
  default     = true
}

variable "enable_datapath_observability" {
  description = "Enable advanced datapath observability"
  type        = bool
  default     = false
}

# Notification configuration
variable "enable_notification_config" {
  description = "Enable cluster notifications"
  type        = bool
  default     = false
}

variable "notification_config_topic" {
  description = "Pub/Sub topic for cluster notifications"
  type        = string
  default     = ""
}

variable "notification_channels" {
  description = "List of notification channels for alerts"
  type        = list(string)
  default     = []
}

# Labels and metadata
variable "cluster_labels" {
  description = "Labels to apply to the cluster"
  type        = map(string)
  default     = {}
}

# Firewall configuration
variable "create_webhook_firewall" {
  description = "Create firewall rule for webhook traffic"
  type        = bool
  default     = true
}

# Security baseline configuration
variable "create_security_baseline" {
  description = "Create security baseline ConfigMap"
  type        = bool
  default     = true
}