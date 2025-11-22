# Create folder for MT dashboards
resource "grafana_folder" "mt_dashboards" {
  title = var.folder_name
}

# MT Frontend Observability Dashboard
resource "grafana_dashboard" "mt_frontend" {
  folder      = grafana_folder.mt_dashboards.id
  config_json = templatefile("${path.module}/dashboards/mt-frontend.json", {
    datasource_uid = var.prometheus_datasource_uid
  })
}

# Output the dashboard URL
output "frontend_dashboard_url" {
  description = "URL to the MT Frontend dashboard"
  value       = "${var.grafana_url}/d/${grafana_dashboard.mt_frontend.uid}"
}
