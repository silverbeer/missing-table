terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Get the default network
data "google_compute_network" "network" {
  name = var.network_name
}

# Get the default subnetwork
data "google_compute_subnetwork" "subnetwork" {
  name   = var.subnetwork_name
  region = var.region
}

# Add secondary IP ranges using gcloud (idempotent)
# This checks if ranges exist before adding them
resource "null_resource" "add_secondary_ranges" {
  triggers = {
    subnetwork          = data.google_compute_subnetwork.subnetwork.self_link
    pods_range_name     = var.pods_range_name
    pods_cidr_range     = var.pods_cidr_range
    services_range_name = var.services_range_name
    services_cidr_range = var.services_cidr_range
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Check if pods range already exists
      EXISTING_PODS=$(gcloud compute networks subnets describe ${var.subnetwork_name} \
        --region=${var.region} \
        --format="value(secondaryIpRanges.filter(rangeName=${var.pods_range_name}).rangeName)" 2>/dev/null || echo "")

      # Check if services range already exists
      EXISTING_SERVICES=$(gcloud compute networks subnets describe ${var.subnetwork_name} \
        --region=${var.region} \
        --format="value(secondaryIpRanges.filter(rangeName=${var.services_range_name}).rangeName)" 2>/dev/null || echo "")

      # Build the update command if ranges don't exist
      if [ -z "$EXISTING_PODS" ] && [ -z "$EXISTING_SERVICES" ]; then
        echo "Adding both secondary IP ranges..."
        gcloud compute networks subnets update ${var.subnetwork_name} \
          --region=${var.region} \
          --add-secondary-ranges=${var.pods_range_name}=${var.pods_cidr_range},${var.services_range_name}=${var.services_cidr_range}
      elif [ -z "$EXISTING_PODS" ]; then
        echo "Adding pods secondary IP range..."
        gcloud compute networks subnets update ${var.subnetwork_name} \
          --region=${var.region} \
          --add-secondary-ranges=${var.pods_range_name}=${var.pods_cidr_range}
      elif [ -z "$EXISTING_SERVICES" ]; then
        echo "Adding services secondary IP range..."
        gcloud compute networks subnets update ${var.subnetwork_name} \
          --region=${var.region} \
          --add-secondary-ranges=${var.services_range_name}=${var.services_cidr_range}
      else
        echo "Secondary IP ranges already exist, skipping..."
      fi
    EOT
  }
}
