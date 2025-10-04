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

variable "region" {
  description = "GCP region"
  type        = string
}

variable "pods_range_name" {
  description = "Name for the pods secondary IP range"
  type        = string
}

variable "pods_cidr_range" {
  description = "CIDR range for pods"
  type        = string
}

variable "services_range_name" {
  description = "Name for the services secondary IP range"
  type        = string
}

variable "services_cidr_range" {
  description = "CIDR range for services"
  type        = string
}
