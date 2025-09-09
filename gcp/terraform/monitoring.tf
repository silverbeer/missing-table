# Google Cloud Monitoring and Alerting Configuration
# Comprehensive monitoring, logging, and alerting for Missing Table application

# Monitoring workspace (automatically created with project)
# Google Cloud Monitoring workspace is automatically created

# Log-based metrics for application monitoring
resource "google_logging_metric" "application_errors" {
  name   = "application_errors"
  filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Application Error Count"
  }

  label_extractors = {
    "container" = "EXTRACT(resource.labels.container_name)"
    "pod"       = "EXTRACT(resource.labels.pod_name)"
    "namespace" = "EXTRACT(resource.labels.namespace_name)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_logging_metric" "authentication_failures" {
  name   = "authentication_failures"
  filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=\"missing-table-backend\" AND jsonPayload.message=~\".*authentication.*failed.*|.*login.*failed.*|.*unauthorized.*\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Authentication Failure Count"
  }

  label_extractors = {
    "user_ip" = "EXTRACT(jsonPayload.remote_ip)"
    "user_agent" = "EXTRACT(jsonPayload.user_agent)"
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_logging_metric" "database_connection_errors" {
  name   = "database_connection_errors"
  filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=\"missing-table-backend\" AND jsonPayload.message=~\".*database.*connection.*error.*|.*database.*timeout.*\""

  metric_descriptor {
    metric_kind = "GAUGE"
    value_type  = "INT64"
    display_name = "Database Connection Error Count"
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Uptime checks for application availability
resource "google_monitoring_uptime_check_config" "frontend_uptime" {
  count        = var.enable_uptime_checks ? 1 : 0
  display_name = "Frontend Uptime Check - ${var.app_name}"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/"
    port         = 8080
    use_ssl      = false
    validate_ssl = false
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = "${local.name_prefix}-frontend.${var.region}.r.appspot.com"
    }
  }

  content_matchers {
    content = "Missing Table"
    matcher = "CONTAINS_STRING"
  }

  checker_type = "STATIC_IP_CHECKERS"
  
  selected_regions = ["USA", "EUROPE", "ASIA_PACIFIC"]

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_uptime_check_config" "backend_uptime" {
  count        = var.enable_uptime_checks ? 1 : 0
  display_name = "Backend API Uptime Check - ${var.app_name}"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/health"
    port         = 8000
    use_ssl      = false
    validate_ssl = false
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = "${local.name_prefix}-backend.${var.region}.r.appspot.com"
    }
  }

  content_matchers {
    content = "healthy"
    matcher = "CONTAINS_STRING"
  }

  checker_type = "STATIC_IP_CHECKERS"
  
  selected_regions = ["USA", "EUROPE", "ASIA_PACIFIC"]

  depends_on = [google_project_service.monitoring_apis]
}

# Alert policies for application monitoring
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "High Error Rate - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Error rate above threshold"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/application_errors\""
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 10

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.ops_alerts.id,
    google_monitoring_notification_channel.security_alerts.id
  ]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "authentication_attack" {
  display_name = "Potential Authentication Attack - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "High authentication failure rate"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/authentication_failures\""
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 20

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_alerts.id]

  alert_strategy {
    auto_close = "3600s" # 1 hour
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "database_connectivity" {
  display_name = "Database Connectivity Issues - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Database connection errors"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/database_connection_errors\""
      duration        = "180s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 5

      aggregations {
        alignment_period   = "180s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "3600s" # 1 hour
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "high_memory_usage" {
  display_name = "High Memory Usage - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Container memory usage high"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"kubernetes.io/container/memory/used_bytes\""
      duration        = "600s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 1073741824 # 1GB

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "3600s" # 1 hour
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "high_cpu_usage" {
  display_name = "High CPU Usage - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Container CPU usage high"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"kubernetes.io/container/cpu/core_usage_time\""
      duration        = "600s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 0.8

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "3600s" # 1 hour
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "pod_restart_loops" {
  display_name = "Pod Restart Loops - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Pod restarting frequently"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"kubernetes.io/container/restart_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 5

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_alerts.id]

  alert_strategy {
    auto_close = "1800s" # 30 minutes
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Uptime check alert policies
resource "google_monitoring_alert_policy" "frontend_down" {
  count        = var.enable_uptime_checks ? 1 : 0
  display_name = "Frontend Down - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Frontend uptime check failed"

    condition_threshold {
      filter          = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\""
      duration        = "300s"
      comparison      = "COMPARISON_LESS_THAN"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_FRACTION_TRUE"
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.ops_alerts.id,
    google_monitoring_notification_channel.security_alerts.id
  ]

  alert_strategy {
    auto_close = "1800s" # 30 minutes
  }

  depends_on = [google_project_service.monitoring_apis]
}

resource "google_monitoring_alert_policy" "backend_down" {
  count        = var.enable_uptime_checks ? 1 : 0
  display_name = "Backend API Down - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Backend uptime check failed"

    condition_threshold {
      filter          = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\""
      duration        = "300s"
      comparison      = "COMPARISON_LESS_THAN"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_FRACTION_TRUE"
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.ops_alerts.id,
    google_monitoring_notification_channel.security_alerts.id
  ]

  alert_strategy {
    auto_close = "1800s" # 30 minutes
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Comprehensive monitoring dashboard
resource "google_monitoring_dashboard" "application_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Missing Table Application Dashboard"
    mosaicLayout = {
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Application Error Rate"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/application_errors\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = ["resource.label.container_name"]
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
              yAxis = {
                label = "Errors per second"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          widget = {
            title = "Authentication Failures"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/authentication_failures\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
              yAxis = {
                label = "Failures per second"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          widget = {
            title = "Container Memory Usage"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"kubernetes.io/container/memory/used_bytes\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_MEAN"
                        crossSeriesReducer = "REDUCE_MEAN"
                        groupByFields      = ["resource.label.container_name"]
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
              yAxis = {
                label = "Memory Usage (bytes)"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          widget = {
            title = "Container CPU Usage"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"kubernetes.io/container/cpu/core_usage_time\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_MEAN"
                        groupByFields      = ["resource.label.container_name"]
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
              yAxis = {
                label = "CPU Usage (cores)"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 12
          height = 4
          widget = {
            title = "GKE Cluster Health"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/ready\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_MEAN"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                  plotType = "STACKED_AREA"
                }
              ]
              yAxis = {
                label = "Ready Nodes"
                scale = "LINEAR"
              }
            }
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.monitoring_apis]
}

# SLO configuration for application availability
resource "google_monitoring_slo" "application_availability" {
  service         = google_monitoring_service.main.service_id
  slo_id          = "application-availability"
  display_name    = "Application Availability SLO"
  goal            = 0.999 # 99.9% availability
  calendar_period = "MONTH"

  request_based_sli {
    good_total_ratio {
      total_service_filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\""
      good_service_filter  = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\" AND metric.type=\"logging.googleapis.com/log_entry_count\" AND NOT (severity>=ERROR)"
    }
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Service for SLO monitoring
resource "google_monitoring_service" "main" {
  service_id   = "missing-table-application"
  display_name = "Missing Table Application"

  user_labels = merge(local.common_labels, {
    service_type = "web_application"
  })

  depends_on = [google_project_service.monitoring_apis]
}

# Error budget alert for SLO
resource "google_monitoring_alert_policy" "slo_burn_rate" {
  display_name = "SLO Error Budget Burn Rate - ${var.app_name}"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Error budget burning too fast"

    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.application_availability.name}\", \"3600s\")"
      duration        = "300s"
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 10

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.ops_alerts.id,
    google_monitoring_notification_channel.security_alerts.id
  ]

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  depends_on = [google_project_service.monitoring_apis]
}

# Log retention configuration
resource "google_logging_project_sink" "application_logs" {
  name        = "${local.name_prefix}-application-logs"
  destination = "storage.googleapis.com/${google_storage_bucket.log_archive.name}"
  
  filter = "resource.type=\"k8s_container\" AND resource.labels.container_name=~\"missing-table-.*\""

  unique_writer_identity = true

  depends_on = [google_project_service.monitoring_apis]
}

# Storage bucket for log archival
resource "google_storage_bucket" "log_archive" {
  name     = "${local.name_prefix}-log-archive-${random_id.suffix.hex}"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy              = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = var.log_retention_days
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.main.id
  }

  labels = merge(local.common_labels, local.security_labels)

  depends_on = [google_project_service.storage_apis]
}

# IAM for log sink
resource "google_storage_bucket_iam_member" "log_sink_writer" {
  bucket = google_storage_bucket.log_archive.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.application_logs.writer_identity
}

# Output monitoring information
output "monitoring_dashboard_url" {
  description = "URL to the monitoring dashboard"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.application_dashboard.id}?project=${var.project_id}"
  sensitive   = false
}

output "slo_name" {
  description = "SLO resource name"
  value       = google_monitoring_slo.application_availability.name
  sensitive   = false
}