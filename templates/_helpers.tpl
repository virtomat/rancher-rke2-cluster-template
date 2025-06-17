{{/*
Expand the name of the chart.
*/}}
{{- define "rancher-cluster-templates.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "rancher-cluster-templates.fullname" -}}
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
{{- define "rancher-cluster-templates.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rancher-cluster-templates.labels" -}}
helm.sh/chart: {{ include "rancher-cluster-templates.chart" . }}
{{ include "rancher-cluster-templates.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rancher-cluster-templates.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rancher-cluster-templates.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "rancher-cluster-templates.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "rancher-cluster-templates.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "rancher-cluster-templates.derivedNamespace" -}}
{{- $appCredSecretName := .Values.cluster.config.openstack.applicationCredentialSecretName }}
{{- $suffix := regexReplaceAll "^os-app-cred-" $appCredSecretName "" }}
{{- printf "u-%s" $suffix }}
{{- end }}

{{/*
Generate a consistent 8-character string based on release context
*/}}
{{- define "rancher-cluster-templates.randomString" -}}
{{- $seed := printf "%s-%s-%s" .Release.Name .Release.Namespace .Chart.Version -}}
{{- trunc 8 (sha256sum $seed) -}}
{{- end }}

