# Main GCP Terraform Configuration for Missing Table Application
# Security-first configuration with comprehensive monitoring and compliance

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }

  # Store state in Google Cloud Storage with encryption
  backend "gcs" {
    bucket         = "missing-table-terraform-state"
    prefix         = "terraform/state"
    encryption_key = "" # Use customer-managed encryption key
  }
}

# Google Provider Configuration
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  # Security: Set user project override for better billing attribution
  user_project_override = true
  billing_project       = var.project_id

  default_labels = local.common_labels
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  user_project_override = true
  billing_project       = var.project_id

  default_labels = local.common_labels
}

# Data Sources
data "google_project" "current" {
  project_id = var.project_id
}

data "google_client_config" "current" {}

data "google_client_openid_userinfo" "current" {}

data "google_billing_account" "current" {
  billing_account = var.billing_account_id
}

# Random resources for naming
resource "random_id" "suffix" {
  byte_length = 4
}

# Local Values
locals {
  name_prefix = "${var.app_name}-${var.environment}"
  
  common_labels = {
    environment   = var.environment
    application   = var.app_name
    version       = var.app_version
    managed_by    = "terraform"
    team          = "platform"
    cost_center   = "engineering"
    compliance    = "required"
    backup        = "enabled"
    monitoring    = "enabled"
    security_scan = "enabled"
  }

  # Security labels for compliance
  security_labels = {
    security_classification = "internal"
    data_classification     = "confidential"
    security_contact       = var.security_contact_email
    compliance_framework   = "cis-gcp,soc2"
  }

  # Network configuration
  network_config = {
    vpc_cidr              = "10.0.0.0/16"
    private_subnet_cidr   = "10.0.1.0/24"
    public_subnet_cidr    = "10.0.2.0/24"
    pods_cidr            = "10.1.0.0/16"
    services_cidr        = "10.2.0.0/16"
  }

  # Security configuration
  security_config = {
    enable_private_nodes         = true
    enable_private_endpoint      = true
    enable_binary_authorization  = true
    enable_network_policy       = true
    enable_pod_security_policy  = true
    enable_shielded_nodes       = true
    enable_workload_identity    = true
  }
}

# Project configuration
resource "google_project_service" "required_apis" {
  for_each = toset(var.required_apis)
  
  project = var.project_id
  service = each.key

  # Security: Disable dependent services when disabling this service
  disable_dependent_services = true
  
  # Security: Disable service on destroy to clean up resources
  disable_on_destroy = false

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }
}

# Organization policies for security
resource "google_project_organization_policy" "disable_sa_key_creation" {
  project    = var.project_id
  constraint = "iam.disableServiceAccountKeyCreation"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_project_organization_policy" "disable_sa_key_upload" {
  project    = var.project_id
  constraint = "iam.disableServiceAccountKeyUpload"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_project_organization_policy" "require_shielded_vm" {
  project    = var.project_id
  constraint = "compute.requireShieldedVm"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_project_organization_policy" "disable_guest_attributes" {
  project    = var.project_id
  constraint = "compute.disableGuestAttributesAccess"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_project_organization_policy" "disable_nested_virtualization" {
  project    = var.project_id
  constraint = "compute.disableNestedVirtualization"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_project_organization_policy" "disable_serial_port_access" {
  project    = var.project_id
  constraint = "compute.disableSerialPortAccess"

  boolean_policy {
    enforced = true
  }

  depends_on = [google_project_service.required_apis]
}

# Security: VPC SC perimeter for additional security
resource "google_access_context_manager_access_policy" "access_policy" {
  count  = var.enable_vpc_sc ? 1 : 0
  parent = "organizations/${var.organization_id}"
  title  = "${local.name_prefix}-access-policy"

  depends_on = [google_project_service.required_apis]
}

# KMS for encryption
resource "google_kms_key_ring" "main" {
  name     = "${local.name_prefix}-keyring"
  location = var.region

  depends_on = [google_project_service.required_apis]

  labels = merge(local.common_labels, local.security_labels)
}

resource "google_kms_crypto_key" "main" {
  name     = "${local.name_prefix}-key"
  key_ring = google_kms_key_ring.main.id
  purpose  = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = var.kms_protection_level
  }

  lifecycle {
    prevent_destroy = true
  }

  labels = merge(local.common_labels, local.security_labels)
}

# Audit logging configuration
resource "google_project_iam_audit_config" "main" {
  project = var.project_id
  service = "allServices"

  audit_log_config {
    log_type = "ADMIN_READ"
  }
  
  audit_log_config {
    log_type = "DATA_READ"
  }
  
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

# Essential IAM roles for the project
resource "google_project_iam_member" "essential_roles" {
  for_each = toset(var.essential_project_roles)
  
  project = var.project_id
  role    = each.key
  member  = "user:${var.admin_email}"

  depends_on = [google_project_service.required_apis]
}