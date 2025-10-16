# Phase 5: Observability & Monitoring

**Status:** 📋 Planned | **Duration:** 3-4 days

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Available Metrics](#available-metrics)
4. [Implementation Steps](#implementation-steps)
5. [Grafana Cloud Setup](#grafana-cloud-setup)
6. [Dashboards](#dashboards)
7. [Alerting](#alerting)
8. [Testing & Validation](#testing--validation)
9. [Troubleshooting](#troubleshooting)
10. [References](#references)

---

## Overview

This phase implements comprehensive observability for the RabbitMQ/Celery messaging platform, enabling you to:

- **Monitor** system health in real-time
- **Detect** performance issues before they impact users
- **Debug** problems with detailed metrics
- **Scale** based on data-driven insights
- **Alert** on critical conditions

### Learning Objectives

By completing this phase, you will understand:

- ✅ **Prometheus fundamentals**: Scraping, remote write, metric types
- ✅ **Grafana Cloud (Mimir)**: Managed Prometheus backend
- ✅ **RabbitMQ metrics**: Queue depth, throughput, consumers
- ✅ **Celery metrics**: Task states, worker health, latency
- ✅ **Dashboard design**: Building effective visualizations
- ✅ **Alerting strategies**: When and how to alert

### Prerequisites

Before starting this phase:

- ✅ Phase 3 complete: Backend Celery workers deployed
- ✅ RabbitMQ running in K3s with management plugin
- ✅ Celery workers processing tasks
- ✅ Grafana Cloud account (free tier available)

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Local K3s Cluster                        │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │  RabbitMQ    │         │    Celery    │                 │
│  │  StatefulSet │         │  Deployment  │                 │
│  │              │         │              │                 │
│  │ Port 15692   │         │  ┌────────┐  │                 │
│  │ /metrics     │         │  │Exporter│  │                 │
│  └──────┬───────┘         │  │Port    │  │                 │
│         │                 │  │9808    │  │                 │
│         │                 │  └───┬────┘  │                 │
│         │                 └──────┼────────┘                 │
│         │                        │                          │
│         │      ┌─────────────────┘                          │
│         │      │                                            │
│         v      v                                            │
│  ┌────────────────────┐                                     │
│  │   Prometheus       │                                     │
│  │   Deployment       │                                     │
│  │                    │                                     │
│  │   - Scrape every   │                                     │
│  │     15-30 seconds  │                                     │
│  │   - Local storage  │                                     │
│  │     (7 days)       │                                     │
│  └─────────┬──────────┘                                     │
│            │                                                │
└────────────┼────────────────────────────────────────────────┘
             │
             │ remote_write (HTTPS)
             │
             v
    ┌────────────────────┐
    │  Grafana Cloud     │
    │  (Mimir Backend)   │
    │                    │
    │  - Long-term       │
    │    storage         │
    │  - Query engine    │
    │  - Alerting        │
    └─────────┬──────────┘
              │
              v
    ┌────────────────────┐
    │  Grafana           │
    │  Dashboards        │
    │                    │
    │  - Visualizations  │
    │  - Alerts          │
    │  - Annotations     │
    └────────────────────┘
```

### Data Flow

1. **Metrics Generation**
   - RabbitMQ: Built-in Prometheus plugin exposes metrics on port 15692
   - Celery: Sidecar exporter connects to RabbitMQ, exposes metrics on port 9808

2. **Local Collection**
   - Prometheus scrapes both endpoints every 15-30 seconds
   - Stores data locally for 7 days (configurable)

3. **Remote Write**
   - Prometheus forwards all metrics to Grafana Cloud via `remote_write`
   - Uses HTTPS with authentication (username/password)
   - Includes tenant ID header

4. **Storage & Querying**
   - Grafana Cloud (Mimir) stores metrics long-term
   - Provides scalable query engine for dashboards

5. **Visualization**
   - Grafana dashboards query Mimir backend
   - Real-time updates and historical analysis

### Why This Architecture?

**Local Prometheus Benefits:**
- **Reliability**: Continues collecting even if Grafana Cloud is unreachable
- **Performance**: Local queries for debugging (no network latency)
- **Cost**: Only stores recent data locally, offloads to cloud
- **Flexibility**: Can query both local and cloud data sources

**Grafana Cloud Benefits:**
- **Scalability**: Handles millions of active series
- **Durability**: Long-term storage without maintenance
- **Collaboration**: Team access to dashboards
- **Managed**: No operational burden

---

## Available Metrics

### RabbitMQ Metrics

The built-in Prometheus plugin exposes comprehensive metrics. Key categories:

#### 1. Broker Health
```
rabbitmq_up                                 # 1 if broker is up, 0 if down
rabbitmq_identity_info                      # Broker version and node info
rabbitmq_build_info                         # RabbitMQ build information
```

#### 2. Connection Metrics
```
rabbitmq_connections                        # Current connection count
rabbitmq_connections_opened_total          # Total connections opened since start
rabbitmq_connections_closed_total          # Total connections closed
rabbitmq_connection_incoming_bytes_total   # Bytes received
rabbitmq_connection_outgoing_bytes_total   # Bytes sent
rabbitmq_connection_incoming_packets_total # Packets received
rabbitmq_connection_outgoing_packets_total # Packets sent
```

#### 3. Channel Metrics
```
rabbitmq_channels                          # Current channel count
rabbitmq_channels_opened_total            # Total channels opened
rabbitmq_channels_closed_total            # Total channels closed
rabbitmq_channel_consumers                # Consumers per channel
rabbitmq_channel_messages_unacked         # Unacknowledged messages
rabbitmq_channel_messages_unconfirmed     # Unconfirmed published messages
```

#### 4. Queue Metrics (Most Important!)
```
rabbitmq_queue_messages_ready             # Messages ready for delivery
rabbitmq_queue_messages_unacked           # Messages delivered but not acked
rabbitmq_queue_messages                   # Total messages in queue
rabbitmq_queue_consumers                  # Active consumers on queue
rabbitmq_queue_consumer_utilisation       # How busy consumers are (0-1)
rabbitmq_queue_messages_published_total   # Messages published to queue
rabbitmq_queue_messages_delivered_total   # Messages delivered from queue
rabbitmq_queue_messages_acked_total       # Messages acknowledged
rabbitmq_queue_messages_redelivered_total # Messages redelivered (failed once)
```

#### 5. Memory & Disk
```
rabbitmq_node_mem_used                    # Memory used by node (bytes)
rabbitmq_node_mem_limit                   # Memory limit (bytes)
rabbitmq_node_mem_alarm                   # 1 if memory alarm triggered
rabbitmq_node_disk_free                   # Free disk space (bytes)
rabbitmq_node_disk_free_limit             # Disk free space limit (bytes)
rabbitmq_node_disk_free_alarm             # 1 if disk alarm triggered
```

#### 6. Erlang VM Metrics
```
rabbitmq_erlang_processes_used            # Current Erlang processes
rabbitmq_erlang_processes_limit           # Max Erlang processes
rabbitmq_erlang_scheduler_run_queue       # Scheduler run queue length
rabbitmq_io_read_bytes_total              # Bytes read from disk
rabbitmq_io_write_bytes_total             # Bytes written to disk
```

**Complete list:** https://github.com/rabbitmq/rabbitmq-prometheus/blob/master/metrics.md

---

### Celery Metrics

The `danihodovic/celery-exporter` provides task and worker metrics:

#### 1. Worker Metrics
```
celery_worker_up                          # 1 if worker is online, 0 if down
celery_worker_tasks_active                # Currently processing tasks
celery_workers_count                      # Total number of workers
```

#### 2. Task State Metrics
```
celery_tasks_total{state="received"}      # Tasks received by workers
celery_tasks_total{state="started"}       # Tasks that started processing
celery_tasks_total{state="succeeded"}     # Successfully completed tasks
celery_tasks_total{state="failed"}        # Failed tasks
celery_tasks_total{state="rejected"}      # Rejected tasks
celery_tasks_total{state="revoked"}       # Revoked (cancelled) tasks
celery_tasks_total{state="retried"}       # Retried tasks
```

#### 3. Task Performance Metrics
```
celery_task_latency_seconds               # Time from publish to start
celery_task_runtime_seconds               # Time to execute task
celery_task_runtime_seconds_bucket        # Histogram buckets for runtime
celery_task_runtime_seconds_sum           # Sum of all task runtimes
celery_task_runtime_seconds_count         # Count of tasks
```

#### 4. Queue Metrics
```
celery_queue_length                       # Messages waiting in queue
celery_active_consumer_count              # Active consumers per queue
celery_active_process_count               # Active worker processes
```

#### 5. Task-Specific Metrics

All metrics above can be filtered by:
- `task`: Task name (e.g., `process_match_data`)
- `queue`: Queue name (e.g., `matches`)
- `hostname`: Worker hostname

**Example queries:**
```promql
# Success rate for specific task
rate(celery_tasks_total{state="succeeded",task="process_match_data"}[5m])
/
rate(celery_tasks_total{task="process_match_data"}[5m])

# Average runtime for task
rate(celery_task_runtime_seconds_sum{task="process_match_data"}[5m])
/
rate(celery_task_runtime_seconds_count{task="process_match_data"}[5m])
```

---

## Implementation Steps

### Step 1: Enable RabbitMQ Prometheus Plugin

The plugin is already included in the `rabbitmq:3.13-management` image, but we need to expose the metrics port.

**Update Helm Chart:**

Edit `helm/messaging-platform/templates/rabbitmq-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "messaging-platform.fullname" . }}-rabbitmq
  labels:
    app: rabbitmq
spec:
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
    - name: management
      port: 15672
      targetPort: 15672
    - name: prometheus    # ADD THIS
      port: 15692
      targetPort: 15692
  selector:
    app: rabbitmq
  clusterIP: None
```

**Verify Plugin is Enabled:**

```bash
# Port-forward to RabbitMQ management
kubectl port-forward svc/messaging-rabbitmq 15672:15672 -n messaging

# Access Management UI
open http://localhost:15672
# Login: admin/admin123

# Check enabled plugins (should see rabbitmq_prometheus)
# Navigate to Admin → Cluster → Nodes → Your Node → Plugins
```

**Test Metrics Endpoint:**

```bash
# Port-forward Prometheus metrics
kubectl port-forward svc/messaging-rabbitmq 15692:15692 -n messaging

# Fetch metrics
curl http://localhost:15692/metrics

# Should see output like:
# # TYPE rabbitmq_up gauge
# rabbitmq_up 1
# # TYPE rabbitmq_connections gauge
# rabbitmq_connections 2
# ...
```

---

### Step 2: Deploy Celery Exporter

Add the exporter as a sidecar to your Celery worker deployment.

**Create Celery Exporter Deployment:**

Create `helm/messaging-platform/templates/celery-exporter-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "messaging-platform.fullname" . }}-celery-exporter
  labels:
    app: celery-exporter
spec:
  replicas: 1
  selector:
    matchLabels:
      app: celery-exporter
  template:
    metadata:
      labels:
        app: celery-exporter
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9808"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: celery-exporter
        image: danihodovic/celery-exporter:latest
        ports:
        - containerPort: 9808
          name: metrics
        env:
        - name: CELERY_BROKER_URL
          value: "amqp://{{ .Values.rabbitmq.auth.username }}:{{ .Values.rabbitmq.auth.password }}@{{ include "messaging-platform.fullname" . }}-rabbitmq:5672//"
        - name: CELERY_RESULT_BACKEND
          value: "redis://{{ include "messaging-platform.fullname" . }}-redis:6379/0"
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
```

**Create Celery Exporter Service:**

Create `helm/messaging-platform/templates/celery-exporter-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "messaging-platform.fullname" . }}-celery-exporter
  labels:
    app: celery-exporter
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9808"
spec:
  type: ClusterIP
  ports:
  - port: 9808
    targetPort: 9808
    protocol: TCP
    name: metrics
  selector:
    app: celery-exporter
```

**Deploy and Test:**

```bash
# Deploy updated Helm chart
helm upgrade --install messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  -n messaging --create-namespace

# Wait for exporter to be ready
kubectl wait --for=condition=ready pod \
  -l app=celery-exporter -n messaging --timeout=60s

# Port-forward to test
kubectl port-forward svc/messaging-celery-exporter 9808:9808 -n messaging

# Fetch metrics
curl http://localhost:9808/metrics

# Should see output like:
# # HELP celery_worker_up Indicates if a worker has recently sent a heartbeat
# # TYPE celery_worker_up gauge
# celery_worker_up{hostname="celery@worker1"} 1
# ...
```

---

### Step 3: Deploy Prometheus to K3s

**Create Prometheus ConfigMap:**

Create `helm/messaging-platform/templates/prometheus-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "messaging-platform.fullname" . }}-prometheus-config
  labels:
    app: prometheus
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
      external_labels:
        cluster: 'k3s-local'
        environment: 'development'

    # Grafana Cloud remote write (configured in Step 4)
    # remote_write:
    #   - url: https://prometheus-prod-01-us-central-0.grafana.net/api/prom/push
    #     basic_auth:
    #       username: YOUR_GRAFANA_CLOUD_USERNAME
    #       password: YOUR_GRAFANA_CLOUD_API_KEY

    scrape_configs:
      # Scrape Prometheus itself
      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9090']

      # Scrape RabbitMQ metrics
      - job_name: 'rabbitmq'
        scrape_interval: 30s
        static_configs:
          - targets: ['{{ include "messaging-platform.fullname" . }}-rabbitmq:15692']
        metrics_path: '/metrics'

      # Scrape Celery exporter
      - job_name: 'celery'
        scrape_interval: 30s
        static_configs:
          - targets: ['{{ include "messaging-platform.fullname" . }}-celery-exporter:9808']
```

**Create Prometheus Deployment:**

Create `helm/messaging-platform/templates/prometheus-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "messaging-platform.fullname" . }}-prometheus
  labels:
    app: prometheus
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:v2.48.0
        ports:
        - containerPort: 9090
          name: web
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: data
          mountPath: /prometheus
        args:
        - '--config.file=/etc/prometheus/prometheus.yml'
        - '--storage.tsdb.path=/prometheus'
        - '--storage.tsdb.retention.time=7d'
        - '--web.enable-lifecycle'
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: {{ include "messaging-platform.fullname" . }}-prometheus-config
      - name: data
        persistentVolumeClaim:
          claimName: {{ include "messaging-platform.fullname" . }}-prometheus-data
```

**Create Prometheus PVC:**

Create `helm/messaging-platform/templates/prometheus-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "messaging-platform.fullname" . }}-prometheus-data
  labels:
    app: prometheus
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

**Create Prometheus Service:**

Create `helm/messaging-platform/templates/prometheus-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "messaging-platform.fullname" . }}-prometheus
  labels:
    app: prometheus
spec:
  type: ClusterIP
  ports:
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: web
  selector:
    app: prometheus
```

**Deploy and Verify:**

```bash
# Deploy updated chart
helm upgrade --install messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  -n messaging --create-namespace

# Wait for Prometheus to be ready
kubectl wait --for=condition=ready pod \
  -l app=prometheus -n messaging --timeout=120s

# Port-forward to access Prometheus UI
kubectl port-forward svc/messaging-prometheus 9090:9090 -n messaging

# Open Prometheus UI
open http://localhost:9090

# Verify targets are up:
# Navigate to Status → Targets
# Should see 3 endpoints (prometheus, rabbitmq, celery) all UP
```

**Test Queries in Prometheus:**

```promql
# Test RabbitMQ metrics
rabbitmq_up

# Test Celery metrics
celery_worker_up

# Queue depth
rabbitmq_queue_messages

# Task success rate (last 5 minutes)
rate(celery_tasks_total{state="succeeded"}[5m])
```

---

### Step 4: Configure Grafana Cloud Remote Write

**Get Grafana Cloud Credentials:**

1. **Sign up for Grafana Cloud** (free tier available)
   - Go to https://grafana.com/auth/sign-up/create-user
   - Free tier includes:
     - 10,000 series (plenty for this setup)
     - 14-day retention
     - 3 users

2. **Get Prometheus Remote Write Details:**
   - Log into Grafana Cloud
   - Navigate to "Connections" → "Add new connection"
   - Search for "Hosted Prometheus metrics"
   - Click "Configure"
   - Note these values:
     - **Remote Write Endpoint**: `https://prometheus-prod-XX-XX.grafana.net/api/prom/push`
     - **Username**: Your instance ID (e.g., `123456`)
     - **Password**: Generate an API key

3. **Create Kubernetes Secret:**

```bash
# Replace with your actual values
GRAFANA_CLOUD_URL="https://prometheus-prod-01-us-central-0.grafana.net/api/prom/push"
GRAFANA_CLOUD_USERNAME="123456"
GRAFANA_CLOUD_PASSWORD="YOUR_API_KEY_HERE"

kubectl create secret generic grafana-cloud-credentials \
  --from-literal=url="${GRAFANA_CLOUD_URL}" \
  --from-literal=username="${GRAFANA_CLOUD_USERNAME}" \
  --from-literal=password="${GRAFANA_CLOUD_PASSWORD}" \
  -n messaging
```

**Update Prometheus ConfigMap:**

Edit the ConfigMap to enable remote_write:

```yaml
# In prometheus-configmap.yaml, uncomment and update:
remote_write:
  - url: {{ .Values.grafanaCloud.remoteWriteUrl }}
    basic_auth:
      username: {{ .Values.grafanaCloud.username }}
      password: {{ .Values.grafanaCloud.password }}
    queue_config:
      capacity: 10000
      max_shards: 10
      min_shards: 1
      max_samples_per_send: 500
      batch_send_deadline: 5s
```

**Update values-local.yaml:**

Add Grafana Cloud configuration:

```yaml
# Add to helm/messaging-platform/values-local.yaml

grafanaCloud:
  enabled: true
  # These will be populated from the secret
  remoteWriteUrl: ""
  username: ""
  password: ""
```

**Update Prometheus Deployment to Use Secret:**

Modify the deployment to inject credentials:

```yaml
# In prometheus-deployment.yaml
env:
- name: GRAFANA_CLOUD_URL
  valueFrom:
    secretKeyRef:
      name: grafana-cloud-credentials
      key: url
- name: GRAFANA_CLOUD_USERNAME
  valueFrom:
    secretKeyRef:
      name: grafana-cloud-credentials
      key: username
- name: GRAFANA_CLOUD_PASSWORD
  valueFrom:
    secretKeyRef:
      name: grafana-cloud-credentials
      key: password
```

**Apply Changes:**

```bash
# Upgrade Helm release
helm upgrade messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  -n messaging

# Restart Prometheus to reload config
kubectl rollout restart deployment/messaging-prometheus -n messaging

# Check logs for successful remote write
kubectl logs -f deployment/messaging-prometheus -n messaging | grep "remote_write"

# Should see successful writes, no errors
```

**Verify in Grafana Cloud:**

1. Log into your Grafana Cloud instance
2. Go to "Explore"
3. Select your Prometheus data source
4. Run test query: `rabbitmq_up`
5. Should see data (may take 1-2 minutes for first data to arrive)

---

## Grafana Cloud Setup

### Accessing Grafana

1. Log into your Grafana Cloud instance
   - URL: `https://YOUR_INSTANCE.grafana.net`

2. Navigate to dashboards
   - Click "Dashboards" in left sidebar

### Data Source Configuration

The Prometheus data source is automatically configured when you set up Grafana Cloud. To verify:

1. Go to "Connections" → "Data sources"
2. Click on "grafanacloud-YOUR_INSTANCE-prom"
3. Click "Save & test" to verify connection

---

## Dashboards

### Importing Pre-Built Dashboards

Grafana Labs provides excellent community dashboards:

#### Dashboard 1: RabbitMQ Monitoring (ID: 10120)

**Import Steps:**

1. In Grafana, click "+" → "Import"
2. Enter dashboard ID: `10120`
3. Click "Load"
4. Select your Prometheus data source
5. Click "Import"

**What You'll See:**
- Broker overview (version, uptime, node status)
- Message rates (publish, deliver, ack)
- Queue depth and consumer count
- Memory and disk usage
- Connection and channel counts

#### Dashboard 2: Celery Monitoring (ID: 10026)

**Import Steps:**

1. Click "+" → "Import"
2. Enter dashboard ID: `10026`
3. Select Prometheus data source
4. Import

**What You'll See:**
- Worker status and count
- Task events by state (rate)
- Task events by task name
- Task runtime heatmaps
- Queue length

### Creating Custom Dashboards

**Example: Match Processing Dashboard**

Create a dashboard specifically for monitoring match data processing:

1. **Create New Dashboard**
   - Click "+" → "Dashboard"
   - Click "Add visualization"

2. **Panel 1: Worker Health**
```promql
# Metric: celery_worker_up
# Panel type: Stat
# Title: Online Workers
# Query:
sum(celery_worker_up)

# Thresholds:
# Green: >= 1
# Red: < 1
```

3. **Panel 2: Task Success Rate**
```promql
# Panel type: Time series
# Title: Match Processing Success Rate (%)
# Query:
(
  rate(celery_tasks_total{state="succeeded",task="process_match_data"}[5m])
  /
  rate(celery_tasks_total{task="process_match_data"}[5m])
) * 100

# Unit: Percent (0-100)
# Thresholds:
# Green: > 95
# Yellow: 90-95
# Red: < 90
```

4. **Panel 3: Queue Depth**
```promql
# Panel type: Time series
# Title: Matches Queue Depth
# Query:
rabbitmq_queue_messages{queue="matches"}

# Thresholds:
# Green: < 100
# Yellow: 100-500
# Red: > 500
```

5. **Panel 4: Task Processing Time**
```promql
# Panel type: Time series
# Title: Average Task Runtime (seconds)
# Query:
rate(celery_task_runtime_seconds_sum{task="process_match_data"}[5m])
/
rate(celery_task_runtime_seconds_count{task="process_match_data"}[5m])

# Unit: Seconds
```

6. **Panel 5: Failed Tasks**
```promql
# Panel type: Stat
# Title: Failed Tasks (Last Hour)
# Query:
increase(celery_tasks_total{state="failed",task="process_match_data"}[1h])

# Color: Red if > 0
```

7. **Panel 6: Message Throughput**
```promql
# Panel type: Time series
# Title: Messages per Second
# Query:
rate(rabbitmq_queue_messages_published_total{queue="matches"}[5m])

# Unit: ops/s
```

**Save Dashboard:**
- Click "Save dashboard" icon
- Name: "Match Processing Monitoring"
- Save

### Dashboard Best Practices

1. **Organization**
   - Group related metrics together
   - Use rows to separate categories
   - Put most important metrics at top

2. **Visualization Types**
   - **Stat**: Single value (worker count, current queue depth)
   - **Time series**: Trends over time (rates, latencies)
   - **Gauge**: Percentage values (CPU, memory, success rate)
   - **Heatmap**: Distribution (task runtime distribution)

3. **Colors & Thresholds**
   - Use consistent color scheme
   - Set meaningful thresholds
   - Green = good, Yellow = warning, Red = critical

4. **Time Range**
   - Default to last 1 hour for real-time monitoring
   - Provide quick ranges (15m, 1h, 6h, 24h, 7d)

5. **Refresh Rate**
   - Set auto-refresh for monitoring dashboards
   - 30s or 1m for real-time, 5m for overview

6. **Variables**
   - Use variables for filtering (task name, queue, worker)
   - Makes dashboards reusable

**Example Variable:**
```
Name: task
Type: Query
Query: label_values(celery_tasks_total, task)
```

Then use in queries: `celery_tasks_total{task="$task"}`

---

## Alerting

### Alert Strategies

**Philosophy:**
- Alert on **symptoms**, not causes (user impact)
- Page for things that require immediate action
- Use different severity levels

**Severity Levels:**
- **Critical (P1)**: Paging alert, immediate action required
- **Warning (P2)**: Non-urgent, address during business hours
- **Info (P3)**: FYI, tracked but not alerted

### Creating Alert Rules in Grafana

**Example Alert 1: RabbitMQ Down**

1. Navigate to "Alerting" → "Alert rules"
2. Click "New alert rule"
3. Configure:

```yaml
Alert name: RabbitMQ Broker Down
Query:
  - Metric: rabbitmq_up
  - Expression: rabbitmq_up == 0

Conditions:
  - When: avg() IS BELOW 1
  - For: 1m

Labels:
  severity: critical
  service: rabbitmq

Annotations:
  summary: RabbitMQ broker is down
  description: The RabbitMQ broker at {{ $labels.instance }} has been down for more than 1 minute.
```

**Example Alert 2: High Queue Depth**

```yaml
Alert name: High Queue Depth
Query:
  - Metric: rabbitmq_queue_messages
  - Expression: rabbitmq_queue_messages{queue="matches"}

Conditions:
  - When: avg() IS ABOVE 1000
  - For: 10m

Labels:
  severity: warning
  service: rabbitmq
  queue: matches

Annotations:
  summary: High message queue depth
  description: Queue {{ $labels.queue }} has {{ $value }} messages (threshold: 1000) for more than 10 minutes. Workers may be struggling to keep up.
```

**Example Alert 3: No Active Workers**

```yaml
Alert name: No Active Celery Workers
Query:
  - Metric: celery_worker_up
  - Expression: sum(celery_worker_up)

Conditions:
  - When: avg() IS BELOW 1
  - For: 5m

Labels:
  severity: critical
  service: celery

Annotations:
  summary: No active Celery workers
  description: No Celery workers are online. Task processing has stopped.
```

**Example Alert 4: High Task Failure Rate**

```yaml
Alert name: High Task Failure Rate
Query:
  - A: rate(celery_tasks_total{state="failed",task="process_match_data"}[5m])
  - B: rate(celery_tasks_total{task="process_match_data"}[5m])
  - Expression: (A / B) * 100

Conditions:
  - When: avg() IS ABOVE 5
  - For: 10m

Labels:
  severity: warning
  service: celery
  task: process_match_data

Annotations:
  summary: High task failure rate
  description: Task {{ $labels.task }} is failing at {{ $value | humanize }}% (threshold: 5%) for more than 10 minutes.
```

**Example Alert 5: Task Processing Slow**

```yaml
Alert name: Slow Task Processing
Query:
  - A: rate(celery_task_runtime_seconds_sum{task="process_match_data"}[5m])
  - B: rate(celery_task_runtime_seconds_count{task="process_match_data"}[5m])
  - Expression: A / B

Conditions:
  - When: avg() IS ABOVE 5
  - For: 15m

Labels:
  severity: warning
  service: celery
  task: process_match_data

Annotations:
  summary: Task processing is slow
  description: Average task runtime for {{ $labels.task }} is {{ $value | humanize }}s (threshold: 5s) for more than 15 minutes.
```

### Notification Channels

**Configure Notifications:**

1. Go to "Alerting" → "Contact points"
2. Click "New contact point"

**Option 1: Email**
```yaml
Name: Email - On Call
Type: Email
Addresses: your-email@example.com
```

**Option 2: Slack**
```yaml
Name: Slack - Alerts
Type: Slack
Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
Channel: #alerts
```

**Option 3: PagerDuty** (for critical alerts)
```yaml
Name: PagerDuty - Critical
Type: PagerDuty
Integration Key: YOUR_INTEGRATION_KEY
```

### Notification Policies

Create policies to route alerts by severity:

1. Go to "Alerting" → "Notification policies"
2. Edit default policy or create new:

```yaml
# Critical alerts → PagerDuty
Matching labels:
  severity: critical
Contact point: PagerDuty - Critical
Repeat interval: 5m

# Warning alerts → Slack
Matching labels:
  severity: warning
Contact point: Slack - Alerts
Repeat interval: 1h

# Info alerts → Email
Matching labels:
  severity: info
Contact point: Email - On Call
Repeat interval: 12h
```

### Alert Testing

**Test alerts manually:**

1. Go to your alert rule
2. Click "Evaluate"
3. Check if condition would trigger
4. Send test notification

**Simulate conditions:**

```bash
# Simulate high queue depth
kubectl exec -it deployment/messaging-rabbitmq -n messaging -- \
  rabbitmqadmin publish routing_key=matches payload="test message" count=2000

# Simulate worker down
kubectl scale deployment/celery-worker --replicas=0 -n messaging

# Wait for alert to fire (check "Firing" tab in Grafana)

# Restore
kubectl scale deployment/celery-worker --replicas=2 -n messaging
```

---

## Testing & Validation

### Smoke Tests

**Test 1: Metrics Collection**

```bash
# Check Prometheus targets
kubectl port-forward svc/messaging-prometheus 9090:9090 -n messaging &
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Expected output:
# {"job":"prometheus","health":"up"}
# {"job":"rabbitmq","health":"up"}
# {"job":"celery","health":"up"}
```

**Test 2: Remote Write**

```bash
# Check Prometheus logs for remote write errors
kubectl logs -l app=prometheus -n messaging | grep remote_write

# Should NOT see errors like:
# "remote_write: Failed to send batch"
# "context deadline exceeded"
```

**Test 3: Data in Grafana Cloud**

```bash
# Query Grafana Cloud API
curl -u "${GRAFANA_CLOUD_USERNAME}:${GRAFANA_CLOUD_PASSWORD}" \
  "https://prometheus-prod-XX.grafana.net/api/prom/api/v1/query?query=rabbitmq_up"

# Should return: {"status":"success","data":{"resultType":"vector",...}}
```

### Load Testing

**Generate Task Load:**

Create a test script to generate tasks:

```python
# backend/test_task_load.py
from celery_app import celery_app

@celery_app.task
def test_task(n):
    """Simple test task"""
    return n * n

if __name__ == "__main__":
    # Send 1000 tasks
    for i in range(1000):
        test_task.delay(i)
    print("Sent 1000 test tasks")
```

Run and monitor:

```bash
# Generate load
cd backend && uv run python test_task_load.py

# Watch metrics in Grafana
# - Queue depth should spike then decrease
# - Task success rate should stay high (>95%)
# - Worker CPU/memory should increase but stay within limits
```

### Validation Checklist

- [ ] RabbitMQ metrics endpoint responding (port 15692)
- [ ] Celery exporter metrics endpoint responding (port 9808)
- [ ] Prometheus scraping both targets successfully
- [ ] Prometheus remote write to Grafana Cloud working
- [ ] Data visible in Grafana Cloud within 2 minutes
- [ ] RabbitMQ dashboard showing correct queue depths
- [ ] Celery dashboard showing worker counts
- [ ] Custom dashboard panels rendering correctly
- [ ] Alerts created and in "OK" state
- [ ] Test alert fires when condition met
- [ ] Notification delivered to contact point
- [ ] Dashboard auto-refresh working
- [ ] Historical data queryable (test after 24 hours)

---

## Troubleshooting

### Issue 1: RabbitMQ Metrics Not Available

**Symptoms:**
- Prometheus target shows "Down" for rabbitmq
- `curl http://rabbitmq:15692/metrics` fails

**Debugging:**

```bash
# Check if plugin is enabled
kubectl exec -it statefulset/messaging-rabbitmq -n messaging -- \
  rabbitmq-plugins list

# Should see:
# [E*] rabbitmq_prometheus

# If not enabled, enable it
kubectl exec -it statefulset/messaging-rabbitmq -n messaging -- \
  rabbitmq-plugins enable rabbitmq_prometheus

# Check service has port exposed
kubectl get svc messaging-rabbitmq -n messaging -o yaml | grep 15692

# Test directly from Prometheus pod
kubectl exec -it deployment/messaging-prometheus -n messaging -- \
  wget -qO- http://messaging-rabbitmq:15692/metrics
```

**Solutions:**
- Ensure plugin is enabled (it should be by default in management image)
- Verify service has port 15692 exposed
- Check RabbitMQ logs for errors

---

### Issue 2: Celery Exporter Not Starting

**Symptoms:**
- Pod in CrashLoopBackOff
- Logs show connection errors

**Debugging:**

```bash
# Check exporter logs
kubectl logs -l app=celery-exporter -n messaging

# Common errors:
# "Error connecting to broker" → RabbitMQ not accessible
# "Authentication failed" → Wrong credentials

# Test broker connectivity
kubectl run -it --rm debug --image=alpine --restart=Never -n messaging -- sh
apk add --no-cache curl
curl -u admin:admin123 http://messaging-rabbitmq:15672/api/overview

# Should return JSON with RabbitMQ stats
```

**Solutions:**
- Verify `CELERY_BROKER_URL` env var is correct
- Check RabbitMQ credentials match
- Ensure exporter can reach RabbitMQ service

---

### Issue 3: Prometheus Not Scraping

**Symptoms:**
- Targets show "Down" in Prometheus UI
- No data in time series

**Debugging:**

```bash
# Check Prometheus config
kubectl get configmap messaging-prometheus-config -n messaging -o yaml

# View Prometheus logs
kubectl logs -l app=prometheus -n messaging

# Look for scrape errors:
# "context deadline exceeded" → Target not responding in time
# "connection refused" → Target not accessible

# Test scrape from Prometheus pod
kubectl exec -it deployment/messaging-prometheus -n messaging -- \
  wget -qO- http://messaging-rabbitmq:15692/metrics

kubectl exec -it deployment/messaging-prometheus -n messaging -- \
  wget -qO- http://messaging-celery-exporter:9808/metrics
```

**Solutions:**
- Verify target URLs in prometheus.yml
- Check network policies (if any)
- Increase scrape_timeout if targets are slow

---

### Issue 4: Remote Write Failing

**Symptoms:**
- Prometheus logs show remote write errors
- Data not appearing in Grafana Cloud

**Debugging:**

```bash
# Check Prometheus logs
kubectl logs -l app=prometheus -n messaging | grep -A 5 remote_write

# Common errors:
# "401 Unauthorized" → Wrong username/password
# "429 Too Many Requests" → Rate limited (free tier limits)
# "context deadline exceeded" → Network issues

# Verify credentials
kubectl get secret grafana-cloud-credentials -n messaging -o yaml

# Test remote write endpoint manually
curl -u "USERNAME:PASSWORD" \
  -X POST \
  "https://prometheus-prod-XX.grafana.net/api/prom/push" \
  --data-binary '@-' <<EOF
# TYPE test_metric gauge
test_metric 42
EOF
```

**Solutions:**
- Verify Grafana Cloud credentials are correct
- Check you haven't exceeded free tier limits (10k series)
- Ensure network can reach Grafana Cloud (test with curl)
- Check Grafana Cloud status page for outages

---

### Issue 5: Missing Metrics in Dashboards

**Symptoms:**
- Dashboard panels show "No data"
- Queries return no results

**Debugging:**

```bash
# Test query directly in Prometheus
kubectl port-forward svc/messaging-prometheus 9090:9090 -n messaging
open http://localhost:9090

# Try query: rabbitmq_up
# If returns data → Problem is with Grafana Cloud
# If no data → Problem is with scraping

# Check metric exists
curl -s http://localhost:9090/api/v1/label/__name__/values | jq '.data' | grep rabbitmq

# Check Grafana data source
# In Grafana Cloud, go to data source settings
# Click "Save & test"
```

**Solutions:**
- Verify metric name is spelled correctly
- Check metric has data with correct labels
- Ensure Grafana Cloud data source is configured
- Try query in Grafana Explore first before adding to dashboard

---

### Issue 6: Alerts Not Firing

**Symptoms:**
- Condition is met but alert stays in "Pending" or "OK"
- No notifications received

**Debugging:**

```bash
# Check alert evaluation in Grafana
# Go to alert rule → "See evaluation behavior"

# Check notification policy
# Alerting → Notification policies
# Verify labels match

# Test contact point
# Contact points → Your channel → "Test"
# Should receive test notification

# Check alert state history
# Alert rule → "State history"
# Shows transitions and evaluations
```

**Solutions:**
- Verify query returns expected values
- Check "For" duration (alert must be in breach for this long)
- Ensure labels match notification policy
- Test contact point independently
- Check notification channel logs (Slack, email, etc.)

---

### Useful Commands

```bash
# View all monitoring components
kubectl get all -n messaging -l 'app in (prometheus,rabbitmq,celery-exporter)'

# Restart Prometheus (reload config)
kubectl rollout restart deployment/messaging-prometheus -n messaging

# View Prometheus config
kubectl get configmap messaging-prometheus-config -n messaging -o yaml

# Check disk usage for Prometheus
kubectl exec -it deployment/messaging-prometheus -n messaging -- \
  df -h /prometheus

# Force scrape in Prometheus
# Navigate to http://localhost:9090/targets
# Click "Unhealthy" → "Force scrape"

# Export metrics to file for debugging
kubectl port-forward svc/messaging-rabbitmq 15692:15692 -n messaging &
curl http://localhost:15692/metrics > rabbitmq-metrics.txt

kubectl port-forward svc/messaging-celery-exporter 9808:9808 -n messaging &
curl http://localhost:9808/metrics > celery-metrics.txt
```

---

## References

### Official Documentation

- **RabbitMQ Prometheus**: https://www.rabbitmq.com/prometheus.html
- **RabbitMQ Metrics**: https://github.com/rabbitmq/rabbitmq-prometheus/blob/master/metrics.md
- **Celery Exporter**: https://github.com/danihodovic/celery-exporter
- **Prometheus**: https://prometheus.io/docs/
- **Grafana Cloud**: https://grafana.com/docs/grafana-cloud/
- **PromQL**: https://prometheus.io/docs/prometheus/latest/querying/basics/

### Dashboard Templates

- **RabbitMQ Dashboard (10120)**: https://grafana.com/grafana/dashboards/10120
- **Celery Monitoring (10026)**: https://grafana.com/grafana/dashboards/10026
- **Browse All Dashboards**: https://grafana.com/grafana/dashboards/

### Blog Posts & Tutorials

- **Celery Monitoring with Prometheus**: https://hodovi.cc/blog/celery-monitoring-with-prometheus-and-grafana/
- **RabbitMQ Best Practices**: https://www.cloudamqp.com/blog/part1-rabbitmq-best-practice.html
- **Prometheus Remote Write**: https://grafana.com/blog/2021/05/26/the-future-of-prometheus-remote-write/

### Related Project Docs

- [00-PHASE-0-SETUP.md](./00-PHASE-0-SETUP.md) - Environment setup
- [01-PHASE-1-MESSAGE-QUEUE-BASICS.md](./01-PHASE-1-MESSAGE-QUEUE-BASICS.md) - RabbitMQ fundamentals
- [02-PHASE-2-HELM-CHARTS.md](./02-PHASE-2-HELM-CHARTS.md) - Helm chart development
- [03-PHASE-3-BACKEND-INTEGRATION.md](./03-PHASE-3-BACKEND-INTEGRATION.md) - Celery backend
- [04-PHASE-4-MATCH-SCRAPER.md](./04-PHASE-4-MATCH-SCRAPER.md) - Publisher integration
- [99-TROUBLESHOOTING.md](./99-TROUBLESHOOTING.md) - General troubleshooting

---

## Next Steps

After completing this phase:

1. **Move to Phase 6**: [Migration & Validation](./06-PHASE-6-MIGRATION.md)
2. **Create Runbook**: Document operational procedures
3. **Train Team**: Share dashboards and alert response procedures
4. **Iterate**: Refine dashboards and alerts based on real usage

---

**Congratulations!** 🎉

You now have world-class observability for your distributed messaging system. You can:

- ✅ Monitor system health in real-time
- ✅ Debug issues with detailed metrics
- ✅ Receive alerts before users notice problems
- ✅ Make data-driven scaling decisions
- ✅ Demonstrate system reliability

**Remember**: Observability is not a one-time setup. Continuously refine your dashboards, alerts, and metrics as you learn more about your system's behavior.

---

**Last Updated:** 2025-10-14
**Phase Status:** 📋 Planned
**Prerequisites:** Phase 3 complete
**Next Phase:** [06-PHASE-6-MIGRATION.md](./06-PHASE-6-MIGRATION.md)
