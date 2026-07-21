{{/*
Cloud configuration template with variable substitution
This template processes the cloud.conf file and substitutes variables from values and secrets
*/}}
{{- define "rancher-cluster-templates.cloudConfig" -}}
{{- $environment := include "rancher-cluster-templates.openstackEnvironment" . | fromYaml }}
{{- $applicationCredential := include "rancher-cluster-templates.applicationCredential" . | fromYaml }}
{{- $ccmNetworkConfig := include "rancher-cluster-templates.ccmNetworkConfig" . | fromYaml }}
{{- $cloudConf := .Files.Get "files/cloud.conf" }}

{{/* Perform variable substitutions */}}
{{- $cloudConf = regexReplaceAll "\\$\\{APPLICATION_CREDENTIAL_ID\\}" $cloudConf $applicationCredential.id }}
{{- $cloudConf = regexReplaceAll "\\$\\{APPLICATION_CREDENTIAL_SECRET\\}" $cloudConf $applicationCredential.secret }}
{{- $cloudConf = regexReplaceAll "\\$\\{AUTH_URL\\}" $cloudConf $environment.authUrl }}
{{- $cloudConf = regexReplaceAll "\\$\\{REGION\\}" $cloudConf $environment.region }}
{{- $cloudConf = regexReplaceAll "\\$\\{SUBNET_ID\\}" $cloudConf $ccmNetworkConfig.subnetId }}
{{- $cloudConf = regexReplaceAll "\\$\\{FLOATING_NETWORK_ID\\}" $cloudConf $ccmNetworkConfig.floatingNetworkId }}

{{- $cloudConf -}}
{{- end -}}
