{{/*
Expand the name of the chart.
*/}}
{{- define "route-llm-gateway.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "route-llm-gateway.fullname" -}}
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
{{- define "route-llm-gateway.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "route-llm-gateway.labels" -}}
helm.sh/chart: {{ include "route-llm-gateway.chart" . }}
{{ include "route-llm-gateway.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "route-llm-gateway.selectorLabels" -}}
app.kubernetes.io/name: {{ include "route-llm-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "route-llm-gateway.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "route-llm-gateway.name" . }}-backend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "route-llm-gateway.worker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "route-llm-gateway.name" . }}-worker
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "route-llm-gateway.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "route-llm-gateway.name" . }}-frontend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

