variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
}

variable "region" {
  description = "GCP region for the cluster"
  type        = string
}

variable "network_name" {
  description = "VPC network name"
  type        = string
  default     = "default"
}

variable "subnetwork_name" {
  description = "VPC subnetwork name"
  type        = string
  default     = "default"
}

variable "pods_range_name" {
  description = "Secondary range name for pods"
  type        = string
  default     = "gke-pods"
}

variable "services_range_name" {
  description = "Secondary range name for services"
  type        = string
  default     = "gke-services"
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
  default     = {}
}
