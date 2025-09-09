# Outputs for Secure VPC Network Module

# Network outputs
output "network_id" {
  description = "The ID of the VPC network"
  value       = google_compute_network.vpc.id
}

output "network_name" {
  description = "The name of the VPC network"
  value       = google_compute_network.vpc.name
}

output "network_self_link" {
  description = "The self link of the VPC network"
  value       = google_compute_network.vpc.self_link
}

output "network_gateway_ipv4" {
  description = "The IPv4 address of the network gateway"
  value       = google_compute_network.vpc.gateway_ipv4
}

# Subnet outputs
output "management_subnet_id" {
  description = "The ID of the management subnet"
  value       = google_compute_subnetwork.management.id
}

output "management_subnet_name" {
  description = "The name of the management subnet"
  value       = google_compute_subnetwork.management.name
}

output "management_subnet_cidr" {
  description = "The CIDR block of the management subnet"
  value       = google_compute_subnetwork.management.ip_cidr_range
}

output "management_subnet_self_link" {
  description = "The self link of the management subnet"
  value       = google_compute_subnetwork.management.self_link
}

output "application_subnet_id" {
  description = "The ID of the application subnet"
  value       = google_compute_subnetwork.application.id
}

output "application_subnet_name" {
  description = "The name of the application subnet"
  value       = google_compute_subnetwork.application.name
}

output "application_subnet_cidr" {
  description = "The CIDR block of the application subnet"
  value       = google_compute_subnetwork.application.ip_cidr_range
}

output "application_subnet_self_link" {
  description = "The self link of the application subnet"
  value       = google_compute_subnetwork.application.self_link
}

output "data_subnet_id" {
  description = "The ID of the data subnet"
  value       = google_compute_subnetwork.data.id
}

output "data_subnet_name" {
  description = "The name of the data subnet"
  value       = google_compute_subnetwork.data.name
}

output "data_subnet_cidr" {
  description = "The CIDR block of the data subnet"
  value       = google_compute_subnetwork.data.ip_cidr_range
}

output "data_subnet_self_link" {
  description = "The self link of the data subnet"
  value       = google_compute_subnetwork.data.self_link
}

# Secondary IP ranges for GKE
output "management_pods_range_name" {
  description = "The name of the management pods secondary IP range"
  value       = google_compute_subnetwork.management.secondary_ip_range[0].range_name
}

output "management_pods_cidr" {
  description = "The CIDR block of the management pods secondary IP range"
  value       = google_compute_subnetwork.management.secondary_ip_range[0].ip_cidr_range
}

output "management_services_range_name" {
  description = "The name of the management services secondary IP range"
  value       = google_compute_subnetwork.management.secondary_ip_range[1].range_name
}

output "management_services_cidr" {
  description = "The CIDR block of the management services secondary IP range"
  value       = google_compute_subnetwork.management.secondary_ip_range[1].ip_cidr_range
}

output "application_pods_range_name" {
  description = "The name of the application pods secondary IP range"
  value       = google_compute_subnetwork.application.secondary_ip_range[0].range_name
}

output "application_pods_cidr" {
  description = "The CIDR block of the application pods secondary IP range"
  value       = google_compute_subnetwork.application.secondary_ip_range[0].ip_cidr_range
}

output "application_services_range_name" {
  description = "The name of the application services secondary IP range"
  value       = google_compute_subnetwork.application.secondary_ip_range[1].range_name
}

output "application_services_cidr" {
  description = "The CIDR block of the application services secondary IP range"
  value       = google_compute_subnetwork.application.secondary_ip_range[1].ip_cidr_range
}

# NAT and Router outputs
output "router_id" {
  description = "The ID of the Cloud Router"
  value       = google_compute_router.router.id
}

output "router_name" {
  description = "The name of the Cloud Router"
  value       = google_compute_router.router.name
}

output "nat_id" {
  description = "The ID of the Cloud NAT"
  value       = google_compute_router_nat.nat.id
}

output "nat_name" {
  description = "The name of the Cloud NAT"
  value       = google_compute_router_nat.nat.name
}

output "nat_ip_addresses" {
  description = "List of static IP addresses used by Cloud NAT"
  value       = google_compute_address.nat_ips[*].address
}

output "nat_ip_self_links" {
  description = "List of self links for NAT IP addresses"
  value       = google_compute_address.nat_ips[*].self_link
}

# Firewall rule outputs
output "firewall_rules" {
  description = "List of created firewall rules"
  value = {
    deny_all_ingress    = google_compute_firewall.deny_all_ingress.name
    allow_internal      = google_compute_firewall.allow_internal.name
    allow_ssh_authorized = length(google_compute_firewall.allow_ssh_authorized) > 0 ? google_compute_firewall.allow_ssh_authorized[0].name : null
    allow_lb_https      = google_compute_firewall.allow_lb_https.name
    allow_health_checks = google_compute_firewall.allow_health_checks.name
    allow_gke_master    = google_compute_firewall.allow_gke_master.name
    deny_sensitive_egress = google_compute_firewall.deny_sensitive_egress.name
  }
}

# DNS outputs
output "private_dns_zone_id" {
  description = "The ID of the private DNS zone"
  value       = length(google_dns_managed_zone.private_zone) > 0 ? google_dns_managed_zone.private_zone[0].id : null
}

output "private_dns_zone_name" {
  description = "The name of the private DNS zone"
  value       = length(google_dns_managed_zone.private_zone) > 0 ? google_dns_managed_zone.private_zone[0].name : null
}

output "private_dns_domain" {
  description = "The domain name of the private DNS zone"
  value       = length(google_dns_managed_zone.private_zone) > 0 ? google_dns_managed_zone.private_zone[0].dns_name : null
}

output "private_dns_name_servers" {
  description = "The name servers for the private DNS zone"
  value       = length(google_dns_managed_zone.private_zone) > 0 ? google_dns_managed_zone.private_zone[0].name_servers : null
}

# Monitoring outputs
output "security_metric_name" {
  description = "The name of the network security monitoring metric"
  value       = google_logging_metric.network_security_events.name
}

output "security_alert_policy_name" {
  description = "The name of the network security alert policy"
  value       = google_monitoring_alert_policy.network_security_alerts.name
}

# BigQuery outputs (for VPC Flow Logs)
output "flow_logs_dataset_id" {
  description = "The ID of the BigQuery dataset for VPC Flow Logs"
  value       = length(google_bigquery_dataset.vpc_flow_logs) > 0 ? google_bigquery_dataset.vpc_flow_logs[0].dataset_id : null
}

output "flow_logs_dataset_location" {
  description = "The location of the BigQuery dataset for VPC Flow Logs"
  value       = length(google_bigquery_dataset.vpc_flow_logs) > 0 ? google_bigquery_dataset.vpc_flow_logs[0].location : null
}

output "flow_logs_sink_name" {
  description = "The name of the log sink for VPC Flow Logs"
  value       = length(google_logging_project_sink.vpc_flow_logs_sink) > 0 ? google_logging_project_sink.vpc_flow_logs_sink[0].name : null
}

output "flow_logs_sink_writer_identity" {
  description = "The writer identity for the VPC Flow Logs sink"
  value       = length(google_logging_project_sink.vpc_flow_logs_sink) > 0 ? google_logging_project_sink.vpc_flow_logs_sink[0].writer_identity : null
  sensitive   = true
}

# Network configuration summary
output "network_configuration" {
  description = "Summary of network configuration"
  value = {
    network_name             = google_compute_network.vpc.name
    routing_mode            = google_compute_network.vpc.routing_mode
    mtu                     = google_compute_network.vpc.mtu
    management_subnet_cidr  = google_compute_subnetwork.management.ip_cidr_range
    application_subnet_cidr = google_compute_subnetwork.application.ip_cidr_range
    data_subnet_cidr       = google_compute_subnetwork.data.ip_cidr_range
    management_pods_cidr   = google_compute_subnetwork.management.secondary_ip_range[0].ip_cidr_range
    application_pods_cidr  = google_compute_subnetwork.application.secondary_ip_range[0].ip_cidr_range
    management_services_cidr = google_compute_subnetwork.management.secondary_ip_range[1].ip_cidr_range
    application_services_cidr = google_compute_subnetwork.application.secondary_ip_range[1].ip_cidr_range
    nat_ip_count           = var.nat_ip_count
    private_dns_enabled    = var.create_private_dns_zone
    flow_logs_export_enabled = var.enable_flow_logs_export
  }
}

# Security configuration summary
output "security_configuration" {
  description = "Summary of security configuration"
  value = {
    authorized_ssh_networks = var.authorized_ssh_networks
    gke_master_authorized_networks = var.gke_master_authorized_networks
    flow_logs_enabled      = true
    private_google_access  = true
    deletion_protection    = var.enable_deletion_protection
    security_monitoring    = true
    network_segmentation   = true
  }
}