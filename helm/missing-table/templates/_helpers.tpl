{{/*
Expand the name of the chart.
*/}}
{{- define "missing-table.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "missing-table.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "missing-table.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "missing-table.labels" -}}
helm.sh/chart: {{ include "missing-table.chart" . }}
{{ include "missing-table.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "missing-table.selectorLabels" -}}
app.kubernetes.io/name: {{ include "missing-table.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "missing-table.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "missing-table.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
sb-notify wiring shared by the backend and the flush CronJob (SB-1849).
*/}}
{{- define "missing-table.sbNotifyEnv" -}}
- name: SB_NOTIFY_CONFIG
  value: /etc/sb-notify/config.toml
- name: SB_NOTIFY_STATE
  value: /var/lib/sb-notify/state.db
# Destination for the slack-mt-scores sink. Optional: the pod starts without
# it, and each send fails with a log line until ESO populates the key.
- name: SB_NOTIFY_SLACK_MT_SCORES_WEBHOOK
  valueFrom:
    secretKeyRef:
      name: {{ include "missing-table.fullname" . }}-secrets
      key: sb-notify-slack-mt-scores-webhook
      optional: true
{{- end }}

{{- define "missing-table.sbNotifyVolumeMounts" -}}
- name: sb-notify-config
  mountPath: /etc/sb-notify
  readOnly: true
- name: sb-notify-state
  mountPath: /var/lib/sb-notify
{{- end }}

{{- define "missing-table.sbNotifyVolumes" -}}
- name: sb-notify-config
  configMap:
    name: {{ include "missing-table.fullname" . }}-sb-notify
- name: sb-notify-state
  persistentVolumeClaim:
    claimName: {{ include "missing-table.fullname" . }}-sb-notify-state
{{- end }}
