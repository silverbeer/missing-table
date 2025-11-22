# Grafana Dashboards - Infrastructure as Code

Terraform configuration for managing Missing Table Grafana Cloud dashboards.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.0
- Grafana Cloud account
- API key with **Admin** role

## Setup

### 1. Get Your Grafana Credentials

1. **Grafana URL**: Go to Grafana Cloud → Your Stack → Grafana → copy the URL
2. **API Key**:
   - Grafana Cloud → Your Stack → Grafana
   - Administration → API Keys → Add API key
   - Role: **Admin**
3. **Prometheus Datasource UID**:
   - Grafana → Connections → Data sources → Prometheus
   - Settings → copy the UID

### 2. Configure Variables

```bash
cd terraform/grafana
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values.

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan Changes

```bash
terraform plan
```

### 5. Apply Changes

```bash
terraform apply
```

## Usage

### Deploy Dashboard

```bash
terraform apply
```

### Update Dashboard

Edit `dashboards/mt-frontend.json`, then:

```bash
terraform apply
```

### Destroy Dashboard

```bash
terraform destroy
```

## Dashboard Panels

The MT Frontend dashboard includes:

- **Page Views by Tab** - Traffic distribution across tabs
- **Total Page Views** - Cumulative page view count
- **Active Users by Role** - User breakdown by role
- **Login Success Rate** - Gauge showing login health
- **Auth Events** - Login/signup/logout over time
- **Login Duration P95** - Login performance
- **HTTP Error Rate** - API error percentage
- **API Requests by Endpoint** - Traffic by endpoint
- **API Latency P95** - API performance
- **Frontend Errors** - JavaScript/Vue errors
- **Web Vitals** - LCP, INP, CLS, FCP, TTFB

## Adding New Dashboards

1. Create JSON in `dashboards/` directory
2. Add resource in `main.tf`:

```hcl
resource "grafana_dashboard" "new_dashboard" {
  folder      = grafana_folder.mt_dashboards.id
  config_json = templatefile("${path.module}/dashboards/new-dashboard.json", {
    datasource_uid = var.prometheus_datasource_uid
  })
}
```

3. Run `terraform apply`

## Files

- `providers.tf` - Terraform and Grafana provider config
- `variables.tf` - Input variables
- `main.tf` - Folder and dashboard resources
- `terraform.tfvars` - Your credentials (gitignored)
- `dashboards/` - Dashboard JSON definitions
