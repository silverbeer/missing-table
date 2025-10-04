output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = module.gke_cluster.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for the GKE cluster"
  value       = module.gke_cluster.cluster_endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate for the GKE cluster"
  value       = module.gke_cluster.cluster_ca_certificate
  sensitive   = true
}

output "region" {
  description = "Region where the cluster is deployed"
  value       = module.gke_cluster.region
}

output "kubectl_config_command" {
  description = "Command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${module.gke_cluster.cluster_name} --region ${module.gke_cluster.region} --project ${var.project_id}"
}

output "cluster_version" {
  description = "Current master version of the cluster"
  value       = module.gke_cluster.cluster_version
}
