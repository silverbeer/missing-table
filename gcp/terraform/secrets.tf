# Google Secret Manager Configuration with Proper IAM
# Secure secrets management with least privilege access and comprehensive auditing

# Application secrets for the backend
resource "google_secret_manager_secret" "database_url" {
  secret_id = "${local.name_prefix}-database-url"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "database"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
      replicas {
        location = var.secondary_region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "${local.name_prefix}-jwt-secret"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "authentication"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
      replicas {
        location = var.secondary_region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "app_secret_key" {
  secret_id = "${local.name_prefix}-app-secret-key"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "encryption"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
      replicas {
        location = var.secondary_region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

# Database credentials
resource "google_secret_manager_secret" "db_username" {
  secret_id = "${local.name_prefix}-db-username"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "database"
    type      = "credentials"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
      replicas {
        location = var.secondary_region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${local.name_prefix}-db-password"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "database"
    type      = "credentials"
    rotation  = "required"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
      replicas {
        location = var.secondary_region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  rotation {
    rotation_period = "7776000s" # 90 days
    next_rotation_time = timeadd(timestamp(), "7776000s")
  }

  depends_on = [google_project_service.security_apis]
}

# External service API keys
resource "google_secret_manager_secret" "supabase_url" {
  secret_id = "${local.name_prefix}-supabase-url"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "api_endpoint"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "supabase_anon_key" {
  secret_id = "${local.name_prefix}-supabase-anon-key"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "api_key"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "supabase_service_key" {
  secret_id = "${local.name_prefix}-supabase-service-key"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "backend"
    type      = "api_key"
    rotation  = "required"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  rotation {
    rotation_period = "7776000s" # 90 days
    next_rotation_time = timeadd(timestamp(), "7776000s")
  }

  depends_on = [google_project_service.security_apis]
}

# CI/CD secrets
resource "google_secret_manager_secret" "github_token" {
  secret_id = "${local.name_prefix}-github-token"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "cicd"
    type      = "api_token"
    rotation  = "required"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  rotation {
    rotation_period = "7776000s" # 90 days
    next_rotation_time = timeadd(timestamp(), "7776000s")
  }

  depends_on = [google_project_service.security_apis]
}

# Monitoring secrets
resource "google_secret_manager_secret" "slack_webhook_url" {
  secret_id = "${local.name_prefix}-slack-webhook-url"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "monitoring"
    type      = "webhook"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  depends_on = [google_project_service.security_apis]
}

# SSL/TLS certificates
resource "google_secret_manager_secret" "tls_certificate" {
  secret_id = "${local.name_prefix}-tls-certificate"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "frontend"
    type      = "certificate"
    rotation  = "required"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  rotation {
    rotation_period = "7776000s" # 90 days
    next_rotation_time = timeadd(timestamp(), "7776000s")
  }

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret" "tls_private_key" {
  secret_id = "${local.name_prefix}-tls-private-key"
  
  labels = merge(local.common_labels, local.security_labels, {
    component = "frontend"
    type      = "private_key"
    rotation  = "required"
  })

  replication {
    user_managed {
      replicas {
        location = var.region
        customer_managed_encryption {
          kms_key_name = google_kms_crypto_key.main.id
        }
      }
    }
  }

  rotation {
    rotation_period = "7776000s" # 90 days
    next_rotation_time = timeadd(timestamp(), "7776000s")
  }

  depends_on = [google_project_service.security_apis]
}

# Generate initial secret values
resource "random_password" "jwt_secret_value" {
  length  = 32
  special = true
}

resource "random_password" "app_secret_key_value" {
  length  = 32
  special = true
}

resource "random_password" "db_password_value" {
  length  = 32
  special = true
}

# Create initial secret versions
resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = random_password.jwt_secret_value.result

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret_version" "app_secret_key" {
  secret      = google_secret_manager_secret.app_secret_key.id
  secret_data = random_password.app_secret_key_value.result

  depends_on = [google_project_service.security_apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password_value.result

  depends_on = [google_project_service.security_apis]
}

# IAM permissions for secret access - Backend service account
resource "google_secret_manager_secret_iam_member" "backend_database_url" {
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_jwt_secret" {
  secret_id = google_secret_manager_secret.jwt_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_app_secret" {
  secret_id = google_secret_manager_secret.app_secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_db_credentials" {
  for_each = toset([
    google_secret_manager_secret.db_username.secret_id,
    google_secret_manager_secret.db_password.secret_id
  ])
  
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_supabase_secrets" {
  for_each = toset([
    google_secret_manager_secret.supabase_url.secret_id,
    google_secret_manager_secret.supabase_anon_key.secret_id,
    google_secret_manager_secret.supabase_service_key.secret_id
  ])
  
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

# IAM permissions for secret access - CI/CD service account
resource "google_secret_manager_secret_iam_member" "cicd_github_token" {
  secret_id = google_secret_manager_secret.github_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cicd.email}"
}

resource "google_secret_manager_secret_iam_member" "cicd_all_secrets" {
  for_each = toset([
    google_secret_manager_secret.database_url.secret_id,
    google_secret_manager_secret.jwt_secret.secret_id,
    google_secret_manager_secret.app_secret_key.secret_id,
    google_secret_manager_secret.supabase_url.secret_id,
    google_secret_manager_secret.supabase_anon_key.secret_id,
    google_secret_manager_secret.supabase_service_key.secret_id
  ])
  
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cicd.email}"
}

# IAM permissions for secret access - Frontend service account (TLS certificates)
resource "google_secret_manager_secret_iam_member" "frontend_tls_secrets" {
  for_each = toset([
    google_secret_manager_secret.tls_certificate.secret_id,
    google_secret_manager_secret.tls_private_key.secret_id
  ])
  
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

# IAM permissions for secret access - Monitoring service account
resource "google_secret_manager_secret_iam_member" "monitoring_slack_webhook" {
  secret_id = google_secret_manager_secret.slack_webhook_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.monitoring.email}"
}

# Secret access audit logging
resource "google_project_iam_audit_config" "secret_manager" {
  project = var.project_id
  service = "secretmanager.googleapis.com"

  audit_log_config {
    log_type = "ADMIN_READ"
  }
  
  audit_log_config {
    log_type = "DATA_READ"
  }
  
  audit_log_config {
    log_type = "DATA_WRITE"
  }

  depends_on = [google_project_service.security_apis]
}

# Log-based metrics for secret access monitoring
resource "google_logging_metric" "secret_access" {
  name   = "secret_access_events"
  filter = "protoPayload.serviceName=\"secretmanager.googleapis.com\" AND protoPayload.methodName=\"google.cloud.secretmanager.v1.SecretManagerService.AccessSecretVersion\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Secret Access Events"
  }

  label_extractors = {
    "user" = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    "secret" = "EXTRACT(protoPayload.resourceName)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Alert for unauthorized secret access
resource "google_monitoring_alert_policy" "unauthorized_secret_access" {
  display_name = "Unauthorized Secret Access - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Secret accessed by unknown user"

    condition_threshold {
      filter          = "resource.type=\"global\" AND metric.type=\"logging.googleapis.com/user/secret_access_events\""
      duration        = "60s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_alerts.id]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Secret rotation function
resource "google_storage_bucket_object" "secret_rotation_function" {
  name   = "secret-rotation-function-${random_id.suffix.hex}.zip"
  bucket = google_storage_bucket.function_source.name
  source = "/tmp/secret-rotation-function.zip"
}

# Cloud Function for secret rotation
resource "google_cloudfunctions_function" "secret_rotation" {
  name                  = "${local.name_prefix}-secret-rotation"
  description           = "Automated secret rotation for Missing Table application"
  runtime               = "python39"
  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.function_source.name
  source_archive_object = google_storage_bucket_object.secret_rotation_function.name
  entry_point          = "rotate_secrets"
  timeout              = 540

  environment_variables = {
    PROJECT_ID = var.project_id
    ENVIRONMENT = var.environment
  }

  # Triggered by Cloud Scheduler for automated rotation
  https_trigger {}

  service_account_email = google_service_account.security.email

  labels = merge(local.common_labels, local.security_labels)

  depends_on = [
    google_project_service.core_apis,
    google_project_service.security_apis
  ]
}

# Cloud Scheduler job for secret rotation
resource "google_cloud_scheduler_job" "secret_rotation" {
  name             = "${local.name_prefix}-secret-rotation"
  description      = "Trigger secret rotation function"
  schedule         = "0 2 * * 0" # Every Sunday at 2 AM
  time_zone        = "UTC"
  attempt_deadline = "320s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions_function.secret_rotation.https_trigger_url

    oidc_token {
      service_account_email = google_service_account.security.email
    }
  }

  depends_on = [google_project_service.core_apis]
}

# Output secret information
output "secret_names" {
  description = "Secret Manager secret names"
  value = {
    database_url        = google_secret_manager_secret.database_url.secret_id
    jwt_secret         = google_secret_manager_secret.jwt_secret.secret_id
    app_secret_key     = google_secret_manager_secret.app_secret_key.secret_id
    db_username        = google_secret_manager_secret.db_username.secret_id
    db_password        = google_secret_manager_secret.db_password.secret_id
    supabase_url       = google_secret_manager_secret.supabase_url.secret_id
    supabase_anon_key  = google_secret_manager_secret.supabase_anon_key.secret_id
    supabase_service_key = google_secret_manager_secret.supabase_service_key.secret_id
    github_token       = google_secret_manager_secret.github_token.secret_id
    slack_webhook_url  = google_secret_manager_secret.slack_webhook_url.secret_id
    tls_certificate    = google_secret_manager_secret.tls_certificate.secret_id
    tls_private_key    = google_secret_manager_secret.tls_private_key.secret_id
  }
  sensitive = false
}