terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Optional: Enable remote state storage
  # backend "gcs" {
  #   bucket = "YOUR-TERRAFORM-STATE-BUCKET"
  #   prefix = "terraform/state/gke/dev"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Setup network with secondary IP ranges for GKE
module "network" {
  source = "../../modules/network"

  region                = var.region
  network_name          = var.network_name
  subnetwork_name       = var.subnetwork_name
  pods_range_name       = var.pods_range_name
  pods_cidr_range       = var.pods_cidr_range
  services_range_name   = var.services_range_name
  services_cidr_range   = var.services_cidr_range
}

# Create GKE Autopilot cluster
module "gke_cluster" {
  source = "../../modules/cluster"

  # Ensure network is ready before creating cluster
  depends_on = [module.network]

  project_id              = var.project_id
  cluster_name            = var.cluster_name
  region                  = var.region
  network_name            = module.network.network_name
  subnetwork_name         = module.network.subnetwork_name
  pods_range_name         = module.network.pods_range_name
  services_range_name     = module.network.services_range_name
  release_channel         = var.release_channel
  maintenance_start_time  = var.maintenance_start_time
  labels                  = var.labels
}
