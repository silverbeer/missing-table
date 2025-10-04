output "network_name" {
  description = "Name of the VPC network"
  value       = data.google_compute_network.network.name
}

output "subnetwork_name" {
  description = "Name of the subnetwork"
  value       = data.google_compute_subnetwork.subnetwork.name
}

output "pods_range_name" {
  description = "Name of the pods secondary IP range"
  value       = var.pods_range_name
}

output "services_range_name" {
  description = "Name of the services secondary IP range"
  value       = var.services_range_name
}

output "secondary_ranges_ready" {
  description = "Indicates that secondary IP ranges have been configured"
  value       = null_resource.add_secondary_ranges.id
}
