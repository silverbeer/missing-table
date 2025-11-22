variable "grafana_url" {
  description = "Grafana Cloud instance URL"
  type        = string
}

variable "grafana_api_key" {
  description = "Grafana Cloud API key with Admin role"
  type        = string
  sensitive   = true
}

variable "prometheus_datasource_uid" {
  description = "UID of your Prometheus data source in Grafana"
  type        = string
  default     = "grafanacloud-prom"
}

variable "folder_name" {
  description = "Folder name for MT dashboards"
  type        = string
  default     = "Missing Table"
}
