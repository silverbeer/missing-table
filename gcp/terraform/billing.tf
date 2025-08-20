# Google Cloud Billing and Cost Management Configuration
# Comprehensive cost monitoring, budgets, and optimization for Missing Table application

# Data source for billing account
data "google_billing_account" "account" {
  billing_account = var.billing_account_id
}

# Budget for the project with multiple alert thresholds
resource "google_billing_budget" "main_budget" {
  billing_account = data.google_billing_account.account.id
  display_name    = "${var.app_name}-${var.environment}-budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
    
    # Filter by specific services to track costs
    services = [
      "services/6F81-5844-456A", # Compute Engine
      "services/95FF-2EF5-5EA1", # Kubernetes Engine
      "services/9662-B51E-5089", # Cloud SQL
      "services/A1E8-BE35-7EBC", # Cloud Storage
      "services/58CD-39AB-9BE4", # Cloud Load Balancing
      "services/F010-80EE-5A75", # Cloud Monitoring
      "services/5490-E034-BEAB"  # Cloud Logging
    ]

    # Track specific resource labels for better cost attribution
    labels = local.common_labels
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount)
    }
  }

  # Multiple alert thresholds for proactive cost management
  dynamic "threshold_rules" {
    for_each = var.budget_alert_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  # Forecasted spend alerts
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  # Email notifications for budget alerts
  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.billing_alerts.id
    ]
    disable_default_iam_recipients = false
    pubsub_topic                   = google_pubsub_topic.budget_alerts.id
  }

  depends_on = [google_project_service.billing_apis]
}

# Notification channel for billing alerts
resource "google_monitoring_notification_channel" "billing_alerts" {
  display_name = "Billing Alerts - ${var.app_name}"
  type         = "email"
  
  labels = {
    email_address = var.alert_email
  }

  enabled = true

  depends_on = [google_project_service.monitoring_apis]
}

# Pub/Sub topic for budget alerts automation
resource "google_pubsub_topic" "budget_alerts" {
  name = "${local.name_prefix}-budget-alerts"

  labels = local.common_labels

  depends_on = [google_project_service.core_apis]
}

# Pub/Sub subscription for budget alert processing
resource "google_pubsub_subscription" "budget_alerts" {
  name  = "${local.name_prefix}-budget-alerts-sub"
  topic = google_pubsub_topic.budget_alerts.name

  # Message retention for 7 days
  message_retention_duration = "604800s"
  
  # Acknowledge deadline
  ack_deadline_seconds = 600

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.budget_alerts_dlq.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels

  depends_on = [google_project_service.core_apis]
}

# Dead letter queue for failed budget alert processing
resource "google_pubsub_topic" "budget_alerts_dlq" {
  name = "${local.name_prefix}-budget-alerts-dlq"

  labels = local.common_labels

  depends_on = [google_project_service.core_apis]
}

# Cloud Function for automated cost optimization actions
resource "google_storage_bucket" "function_source" {
  name     = "${local.name_prefix}-function-source-${random_id.suffix.hex}"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy              = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.storage_apis]
}

# Cloud Function source code archive
data "archive_file" "cost_optimization_function" {
  type        = "zip"
  output_path = "/tmp/cost-optimization-function.zip"
  source_dir  = "${path.module}/../functions/cost-optimization"
}

# Upload function source to Cloud Storage
resource "google_storage_bucket_object" "cost_optimization_function" {
  name   = "cost-optimization-function-${data.archive_file.cost_optimization_function.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.cost_optimization_function.output_path
}

# Cloud Function for cost optimization
resource "google_cloudfunctions_function" "cost_optimization" {
  name                  = "${local.name_prefix}-cost-optimization"
  description           = "Automated cost optimization actions for budget alerts"
  runtime               = "python39"
  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.function_source.name
  source_archive_object = google_storage_bucket_object.cost_optimization_function.name
  entry_point          = "process_budget_alert"
  timeout              = 540

  environment_variables = {
    PROJECT_ID = var.project_id
    ENVIRONMENT = var.environment
    SLACK_WEBHOOK_URL = "" # Add Slack webhook URL for notifications
  }

  event_trigger {
    event_type = "providers/cloud.pubsub/eventTypes/topic.publish"
    resource   = google_pubsub_topic.budget_alerts.name
  }

  service_account_email = google_service_account.monitoring.email

  labels = local.common_labels

  depends_on = [
    google_project_service.core_apis,
    google_project_service.storage_apis
  ]
}

# IAM permissions for cost optimization function
resource "google_project_iam_member" "function_permissions" {
  for_each = toset([
    "roles/compute.instanceAdmin",
    "roles/container.clusterAdmin",
    "roles/monitoring.editor",
    "roles/logging.logWriter"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.monitoring.email}"
}

# Cost anomaly detection using Cloud Monitoring
resource "google_monitoring_alert_policy" "cost_anomaly" {
  display_name = "Cost Anomaly Detection - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Unusual cost increase"

    condition_threshold {
      filter         = "resource.type=\"billing_account\" AND metric.type=\"billing.googleapis.com/billing/total_cost\""
      duration       = "3600s"
      comparison     = "COMPARISON_GREATER_THAN"
      threshold_value = var.budget_amount * 0.1 # Alert if daily cost exceeds 10% of monthly budget

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.billing_alerts.id]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Resource quotas to prevent cost overruns
resource "google_compute_project_metadata_item" "enable_oslogin" {
  key   = "enable-oslogin"
  value = "TRUE"

  depends_on = [google_project_service.compute_apis]
}

# Monitoring dashboard for cost analysis
resource "google_monitoring_dashboard" "cost_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Cost Analysis - ${var.app_name}"
    mosaicLayout = {
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Daily Spend by Service"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"billing_account\" AND metric.type=\"billing.googleapis.com/billing/total_cost\""
                      aggregation = {
                        alignmentPeriod    = "86400s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields = ["metric.label.service"]
                      }
                    }
                  }
                  plotType = "STACKED_AREA"
                }
              ]
            }
          }
        },
        {
          width  = 6
          height = 4
          widget = {
            title = "Budget Utilization"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"billing_account\" AND metric.type=\"billing.googleapis.com/billing/total_cost\""
                      aggregation = {
                        alignmentPeriod    = "3600s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
            }
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.monitoring_apis]
}

# Export billing data to BigQuery for advanced analysis
resource "google_bigquery_dataset" "billing_export" {
  dataset_id  = "billing_export"
  description = "Dataset for billing data export and cost analysis"
  location    = var.region

  access {
    role          = "OWNER"
    user_by_email = var.admin_email
  }

  access {
    role          = "READER"
    user_by_email = google_service_account.monitoring.email
  }

  labels = local.common_labels

  depends_on = [google_project_service.core_apis]
}

# Billing export configuration
resource "google_billing_account_iam_member" "billing_export" {
  billing_account_id = data.google_billing_account.account.id
  role               = "roles/billing.viewer"
  member             = "serviceAccount:${google_service_account.monitoring.email}"
}

# Scheduled queries for cost optimization insights
resource "google_bigquery_data_transfer_config" "cost_analysis" {
  display_name   = "Cost Analysis Transfer - ${var.app_name}"
  location       = var.region
  data_source_id = "scheduled_query"
  schedule       = "every day 06:00"
  
  destination_dataset_id = google_bigquery_dataset.billing_export.dataset_id
  
  params = {
    query = <<-SQL
      SELECT 
        service.description as service_name,
        project.id as project_id,
        DATE(usage_start_time) as usage_date,
        SUM(cost) as daily_cost,
        currency
      FROM `${var.project_id}.billing_export.gcp_billing_export_v1_${replace(data.google_billing_account.account.id, "-", "_")}`
      WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        AND project.id = '${var.project_id}'
      GROUP BY service_name, project_id, usage_date, currency
      ORDER BY usage_date DESC, daily_cost DESC
    SQL
    destination_table_name_template = "daily_cost_analysis_{run_date}"
    write_disposition = "WRITE_TRUNCATE"
  }

  depends_on = [google_project_service.core_apis]
}

# Cost optimization recommendations using Cloud Asset Inventory
resource "google_cloud_asset_project_feed" "cost_optimization" {
  project     = var.project_id
  feed_id     = "cost-optimization-feed"
  content_type = "RESOURCE"

  asset_types = [
    "compute.googleapis.com/Instance",
    "compute.googleapis.com/Disk",
    "sql.googleapis.com/DatabaseInstance",
    "storage.googleapis.com/Bucket"
  ]

  feed_output_config {
    pubsub_destination {
      topic = google_pubsub_topic.asset_changes.id
    }
  }

  depends_on = [google_project_service.security_apis]
}

# Pub/Sub topic for asset changes
resource "google_pubsub_topic" "asset_changes" {
  name = "${local.name_prefix}-asset-changes"

  labels = local.common_labels

  depends_on = [google_project_service.core_apis]
}

# Output billing information
output "billing_account_id" {
  description = "Billing account ID"
  value       = data.google_billing_account.account.id
  sensitive   = false
}

output "budget_name" {
  description = "Budget resource name"
  value       = google_billing_budget.main_budget.name
  sensitive   = false
}

output "cost_dashboard_url" {
  description = "URL to the cost monitoring dashboard"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.cost_dashboard.id}?project=${var.project_id}"
  sensitive   = false
}