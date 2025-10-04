variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the cluster"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "missing-table-dev"
}

variable "network_name" {
  description = "VPC network name (use 'default' for default network)"
  type        = string
  default     = "default"
}

variable "subnetwork_name" {
  description = "VPC subnetwork name (use 'default' for default subnetwork)"
  type        = string
  default     = "default"
}

variable "pods_range_name" {
  description = "Secondary range name for pods"
  type        = string
  default     = "gke-pods-dev"
}

variable "pods_cidr_range" {
  description = "CIDR range for pods"
  type        = string
  default     = "10.4.0.0/14"
}

variable "services_range_name" {
  description = "Secondary range name for services"
  type        = string
  default     = "gke-services-dev"
}

variable "services_cidr_range" {
  description = "CIDR range for services"
  type        = string
  default     = "10.0.32.0/20"
}

variable "release_channel" {
  description = "GKE release channel (RAPID, REGULAR, STABLE)"
  type        = string
  default     = "REGULAR"
}

variable "maintenance_start_time" {
  description = "Start time for daily maintenance window (HH:MM format)"
  type        = string
  default     = "03:00"
}

variable "labels" {
  description = "Resource labels for the cluster"
  type        = map(string)
  default = {
    app         = "missing-table"
    environment = "dev"
    managed_by  = "terraform"
  }
}
