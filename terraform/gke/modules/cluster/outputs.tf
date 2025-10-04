output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = google_container_cluster.autopilot.name
}

output "cluster_endpoint" {
  description = "Endpoint for the GKE cluster"
  value       = google_container_cluster.autopilot.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate for the GKE cluster"
  value       = google_container_cluster.autopilot.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "region" {
  description = "Region where the cluster is deployed"
  value       = google_container_cluster.autopilot.location
}

output "cluster_version" {
  description = "Current master version of the cluster"
  value       = google_container_cluster.autopilot.master_version
}
