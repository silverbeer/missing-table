# Variables for Secure VPC Network Module

# Project and location
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for the network resources"
  type        = string
}

variable "network_name" {
  description = "Name of the VPC network"
  type        = string
  
  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", var.network_name))
    error_message = "Network name must be 1-63 characters, start with lowercase letter, and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "production"
}

# Network configuration
variable "routing_mode" {
  description = "Network routing mode"
  type        = string
  default     = "REGIONAL"
  
  validation {
    condition = contains([
      "REGIONAL",
      "GLOBAL"
    ], var.routing_mode)
    error_message = "Routing mode must be REGIONAL or GLOBAL."
  }
}

variable "mtu" {
  description = "Maximum Transmission Unit in bytes"
  type        = number
  default     = 1460
  
  validation {
    condition     = var.mtu >= 1460 && var.mtu <= 1500
    error_message = "MTU must be between 1460 and 1500."
  }
}

# Subnet CIDR blocks
variable "management_subnet_cidr" {
  description = "CIDR block for management subnet"
  type        = string
  default     = "10.0.1.0/24"
  
  validation {
    condition     = can(cidrhost(var.management_subnet_cidr, 0))
    error_message = "Management subnet CIDR must be a valid CIDR notation."
  }
}

variable "application_subnet_cidr" {
  description = "CIDR block for application subnet"
  type        = string
  default     = "10.0.2.0/24"
  
  validation {
    condition     = can(cidrhost(var.application_subnet_cidr, 0))
    error_message = "Application subnet CIDR must be a valid CIDR notation."
  }
}

variable "data_subnet_cidr" {
  description = "CIDR block for data subnet"
  type        = string
  default     = "10.0.3.0/24"
  
  validation {
    condition     = can(cidrhost(var.data_subnet_cidr, 0))
    error_message = "Data subnet CIDR must be a valid CIDR notation."
  }
}

# Secondary IP ranges for GKE
variable "management_pods_cidr" {
  description = "CIDR block for management subnet pods"
  type        = string
  default     = "10.1.0.0/16"
  
  validation {
    condition     = can(cidrhost(var.management_pods_cidr, 0))
    error_message = "Management pods CIDR must be a valid CIDR notation."
  }
}

variable "management_services_cidr" {
  description = "CIDR block for management subnet services"
  type        = string
  default     = "10.2.0.0/20"
  
  validation {
    condition     = can(cidrhost(var.management_services_cidr, 0))
    error_message = "Management services CIDR must be a valid CIDR notation."
  }
}

variable "application_pods_cidr" {
  description = "CIDR block for application subnet pods"
  type        = string
  default     = "10.3.0.0/16"
  
  validation {
    condition     = can(cidrhost(var.application_pods_cidr, 0))
    error_message = "Application pods CIDR must be a valid CIDR notation."
  }
}

variable "application_services_cidr" {
  description = "CIDR block for application subnet services"
  type        = string
  default     = "10.4.0.0/20"
  
  validation {
    condition     = can(cidrhost(var.application_services_cidr, 0))
    error_message = "Application services CIDR must be a valid CIDR notation."
  }
}

# NAT configuration
variable "nat_ip_count" {
  description = "Number of static IP addresses for NAT gateway"
  type        = number
  default     = 2
  
  validation {
    condition     = var.nat_ip_count >= 1 && var.nat_ip_count <= 10
    error_message = "NAT IP count must be between 1 and 10."
  }
}

variable "enable_data_subnet_nat" {
  description = "Enable NAT for data subnet"
  type        = bool
  default     = false
}

# Security configuration
variable "authorized_ssh_networks" {
  description = "List of CIDR blocks authorized for SSH access"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for cidr in var.authorized_ssh_networks : can(cidrhost(cidr, 0))
    ])
    error_message = "All SSH authorized networks must be valid CIDR blocks."
  }
}

variable "gke_master_authorized_networks" {
  description = "List of CIDR blocks for GKE master authorized networks"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for cidr in var.gke_master_authorized_networks : can(cidrhost(cidr, 0))
    ])
    error_message = "All GKE master authorized networks must be valid CIDR blocks."
  }
}

# DNS configuration
variable "create_private_dns_zone" {
  description = "Create private DNS zone for internal service discovery"
  type        = bool
  default     = true
}

variable "private_dns_domain" {
  description = "Domain name for private DNS zone"
  type        = string
  default     = "internal.local"
  
  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.private_dns_domain))
    error_message = "Private DNS domain must contain only lowercase letters, numbers, dots, and hyphens."
  }
}

variable "organization_domain" {
  description = "Organization domain for BigQuery access control"
  type        = string
  default     = ""
}

# Monitoring and logging
variable "notification_channels" {
  description = "List of notification channels for security alerts"
  type        = list(string)
  default     = []
}

variable "enable_flow_logs_export" {
  description = "Enable VPC Flow Logs export to BigQuery"
  type        = bool
  default     = true
}

variable "bigquery_location" {
  description = "Location for BigQuery dataset"
  type        = string
  default     = "US"
  
  validation {
    condition = contains([
      "US", "EU", "asia-east1", "asia-northeast1", "asia-southeast1",
      "australia-southeast1", "europe-north1", "europe-west1", "europe-west2",
      "europe-west3", "europe-west4", "europe-west6", "northamerica-northeast1",
      "southamerica-east1", "us-central1", "us-east1", "us-east4",
      "us-west1", "us-west2", "us-west3", "us-west4"
    ], var.bigquery_location)
    error_message = "BigQuery location must be a valid location."
  }
}

variable "flow_logs_retention_days" {
  description = "Number of days to retain VPC Flow Logs in BigQuery"
  type        = number
  default     = 90
  
  validation {
    condition     = var.flow_logs_retention_days >= 1 && var.flow_logs_retention_days <= 365
    error_message = "Flow logs retention days must be between 1 and 365."
  }
}

# Lifecycle management
variable "enable_deletion_protection" {
  description = "Enable deletion protection for the VPC network"
  type        = bool
  default     = true
}