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
{{- $appCredSecretName := required "cluster.config.openstack.applicationCredentialSecretName is required" .Values.cluster.config.openstack.applicationCredentialSecretName }}
{{- if not (regexMatch "^os-app-cred-[a-z0-9]+(-[a-z0-9]+)*$" $appCredSecretName) }}
{{- fail "cluster.config.openstack.applicationCredentialSecretName must match os-app-cred-<suffix>" }}
{{- end }}
{{- $suffix := trimPrefix "os-app-cred-" $appCredSecretName }}
{{- printf "u-%s" $suffix }}
{{- end }}

{{/*
Resolve the application credential Secret required by the onboarding contract.
*/}}
{{- define "rancher-cluster-templates.applicationCredential" -}}
{{- $namespace := include "rancher-cluster-templates.derivedNamespace" . }}
{{- $appCredSecretName := .Values.cluster.config.openstack.applicationCredentialSecretName }}
{{- $secret := lookup "v1" "Secret" $namespace $appCredSecretName }}
{{- if not $secret }}
{{- fail (printf "OpenStack application credential Secret %q is required in namespace %q" $appCredSecretName $namespace) }}
{{- end }}
{{- if not (and $secret.data (hasKey $secret.data "applicationCredentialId")) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q requires data.applicationCredentialId" $appCredSecretName $namespace) }}
{{- end }}
{{- if not (and $secret.data (hasKey $secret.data "applicationCredentialSecret")) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q requires data.applicationCredentialSecret" $appCredSecretName $namespace) }}
{{- end }}
{{- $encodedId := index $secret.data "applicationCredentialId" }}
{{- if not (regexMatch "^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$" $encodedId) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q has malformed data.applicationCredentialId" $appCredSecretName $namespace) }}
{{- end }}
{{- $id := b64dec $encodedId }}
{{- if not (trim $id) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q has empty data.applicationCredentialId" $appCredSecretName $namespace) }}
{{- end }}
{{- $encodedCredentialSecret := index $secret.data "applicationCredentialSecret" }}
{{- if not (regexMatch "^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$" $encodedCredentialSecret) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q has malformed data.applicationCredentialSecret" $appCredSecretName $namespace) }}
{{- end }}
{{- $credentialSecret := b64dec $encodedCredentialSecret }}
{{- if not (trim $credentialSecret) }}
{{- fail (printf "OpenStack application credential Secret %q in namespace %q has empty data.applicationCredentialSecret" $appCredSecretName $namespace) }}
{{- end }}
{{- toYaml (dict "id" $id "secret" $credentialSecret) }}
{{- end }}

{{/*
Resolve the CCM network Secret required by the onboarding contract.
*/}}
{{- define "rancher-cluster-templates.ccmNetworkConfig" -}}
{{- $namespace := include "rancher-cluster-templates.derivedNamespace" . }}
{{- $ccmNetConfigSecretName := .Values.cluster.config.openstack.ccmNetConfigSecretName | default "os-ccm-net-config" }}
{{- $secret := lookup "v1" "Secret" $namespace $ccmNetConfigSecretName }}
{{- if not $secret }}
{{- fail (printf "OpenStack CCM network Secret %q is required in namespace %q" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- if not (and $secret.data (hasKey $secret.data "subnetId")) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q requires data.subnetId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- if not (and $secret.data (hasKey $secret.data "floatingNetworkId")) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q requires data.floatingNetworkId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- $encodedSubnetId := index $secret.data "subnetId" }}
{{- if not (regexMatch "^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$" $encodedSubnetId) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q has malformed data.subnetId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- $subnetId := b64dec $encodedSubnetId }}
{{- if not (trim $subnetId) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q has empty data.subnetId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- $encodedFloatingNetworkId := index $secret.data "floatingNetworkId" }}
{{- if not (regexMatch "^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$" $encodedFloatingNetworkId) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q has malformed data.floatingNetworkId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- $floatingNetworkId := b64dec $encodedFloatingNetworkId }}
{{- if not (trim $floatingNetworkId) }}
{{- fail (printf "OpenStack CCM network Secret %q in namespace %q has empty data.floatingNetworkId" $ccmNetConfigSecretName $namespace) }}
{{- end }}
{{- toYaml (dict "subnetId" $subnetId "floatingNetworkId" $floatingNetworkId) }}
{{- end }}

{{/*
Resolve the platform-owned OpenStack environment contract for this release.
*/}}
{{- define "rancher-cluster-templates.openstackEnvironment" -}}
{{- $environment := lookup "v1" "ConfigMap" .Release.Namespace "rke2-openstack-environment" }}
{{- if not $environment }}
{{- fail "rke2-openstack-environment ConfigMap is required" }}
{{- end }}
{{- $authUrl := "" }}
{{- if and $environment.data (hasKey $environment.data "authUrl") }}
{{- $authUrl = trim (index $environment.data "authUrl") }}
{{- end }}
{{- if not $authUrl }}
{{- fail "rke2-openstack-environment ConfigMap requires non-empty authUrl" }}
{{- end }}
{{- $region := "" }}
{{- if and $environment.data (hasKey $environment.data "region") }}
{{- $region = trim (index $environment.data "region") }}
{{- end }}
{{- if not $region }}
{{- fail "rke2-openstack-environment ConfigMap requires non-empty region" }}
{{- end }}
{{- toYaml (dict "authUrl" $authUrl "region" $region) }}
{{- end }}

{{/*
Generate a consistent 8-character string based on release context
*/}}
{{- define "rancher-cluster-templates.randomString" -}}
{{- $seed := printf "%s-%s-%s" .Release.Name .Release.Namespace .Chart.Version -}}
{{- trunc 8 (sha256sum $seed) -}}
{{- end }}
