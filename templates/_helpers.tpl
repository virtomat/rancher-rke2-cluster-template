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
Resolve the namespace-local OpenStack environment contract for this release.
Onboarding projects the canonical fleet-default/rke2-openstack-environment
ConfigMap into the derived user namespace; the chart reads only the local copy.
*/}}
{{- define "rancher-cluster-templates.openstackEnvironment" -}}
{{- $namespace := include "rancher-cluster-templates.derivedNamespace" . }}
{{- $environment := lookup "v1" "ConfigMap" $namespace "rke2-openstack-environment" }}
{{- if not $environment }}
{{- fail (printf "OpenStack environment ConfigMap %q is required in namespace %q" "rke2-openstack-environment" $namespace) }}
{{- end }}
{{- $authUrl := "" }}
{{- if and $environment.data (hasKey $environment.data "authUrl") }}
{{- $authUrl = trim (index $environment.data "authUrl") }}
{{- end }}
{{- if not $authUrl }}
{{- fail (printf "OpenStack environment ConfigMap %q in namespace %q requires non-empty authUrl" "rke2-openstack-environment" $namespace) }}
{{- end }}
{{- $region := "" }}
{{- if and $environment.data (hasKey $environment.data "region") }}
{{- $region = trim (index $environment.data "region") }}
{{- end }}
{{- if not $region }}
{{- fail (printf "OpenStack environment ConfigMap %q in namespace %q requires non-empty region" "rke2-openstack-environment" $namespace) }}
{{- end }}
{{- toYaml (dict "authUrl" $authUrl "region" $region) }}
{{- end }}

{{/*
Map the selected RKE2 Kubernetes version to the exact matching OpenStack CCM
image. The CCM image is derived from the RKE2 version and is not user
configurable. Supported versions are exactly the validated matrix; any other
version fails rendering with a clear error. Changing the matrix requires a
chart release and validation.
*/}}
{{- define "rancher-cluster-templates.openstackCcmImage" -}}
{{- $version := .Values.cluster.config.kubernetesVersion -}}
{{- $ccmImages := dict "v1.33.12+rke2r2" "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.33.0" "v1.34.6+rke2r1" "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.34.0" "v1.35.6+rke2r1" "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0" -}}
{{- if not (hasKey $ccmImages $version) -}}
{{- fail (printf "Unsupported RKE2 Kubernetes version %q; supported versions are v1.33.12+rke2r2, v1.34.6+rke2r1, v1.35.6+rke2r1 (changing the matrix requires a chart release and validation)" $version) -}}
{{- end -}}
{{- index $ccmImages $version -}}
{{- end -}}

{{/*
Resolve the effective master node count used to select the cluster topology.
`nodePoolCounts.master` wins when set to a non-empty, non-zero value; otherwise
the `nodepools` item named `master` provides its `quantity`. The chart supports
exactly one master (single master) or three or more masters (HA). A count of
exactly two is not supported and fails rendering with a clear message.
*/}}
{{- define "rancher-cluster-templates.masterCount" -}}
{{- $poolCount := (default dict .Values.nodePoolCounts).master | default "" -}}
{{- $count := 0 -}}
{{- if and (ne (toString $poolCount) "") (ne (toString $poolCount) "0") -}}
{{- $count = $poolCount | int -}}
{{- else -}}
{{- range .Values.nodepools -}}
{{- if eq .name "master" -}}
{{- $count = .quantity | default 0 | int -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- if eq $count 2 -}}
{{- fail "Master node count of 2 is not supported; use exactly 1 (single master) or at least 3 (HA)" -}}
{{- end -}}
{{- if and (ne $count 1) (lt $count 3) -}}
{{- fail (printf "Master node count must be exactly 1 (single master) or at least 3 (HA); got %d" $count) -}}
{{- end -}}
{{- $count -}}
{{- end -}}

{{/*
Generate a consistent 8-character string based on release context
*/}}
{{- define "rancher-cluster-templates.randomString" -}}
{{- $seed := printf "%s-%s-%s" .Release.Name .Release.Namespace .Chart.Version -}}
{{- trunc 8 (sha256sum $seed) -}}
{{- end }}
