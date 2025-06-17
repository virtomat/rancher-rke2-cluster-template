{{/*
Cloud configuration template with variable substitution
This template processes the cloud.conf file and substitutes variables from values and secrets
*/}}
{{- define "rancher-cluster-templates.cloudConfig" -}}
{{- $namespace := include "rancher-cluster-templates.derivedNamespace" . }}
{{- $val := .Values.cluster.config.openstack }}
{{- $secret := (lookup "v1" "Secret" $namespace $val.applicationCredentialSecretName) }}
{{- $ccmNetConfigSecret := (lookup "v1" "Secret" $namespace $val.ccmNetConfigSecretName) }}
{{- $cloudConf := .Files.Get "files/cloud.conf" }}

{{/* Extract application credential ID */}}
{{- $idFromSecret := "" }}
{{- if and $secret (hasKey $secret.data "applicationCredentialId") }}
{{- $idFromSecret = $secret.data.applicationCredentialId | b64dec }}
{{- end }}
{{- $appCredId := coalesce $val.applicationCredentialId $idFromSecret }}

{{/* Extract application credential secret */}}
{{- $secretFromSecret := "" }}
{{- if and $secret (hasKey $secret.data "applicationCredentialSecret") }}
{{- $secretFromSecret = $secret.data.applicationCredentialSecret | b64dec }}
{{- end }}
{{- $appCredSecret := coalesce $val.applicationCredentialSecret $secretFromSecret }}

{{/* Extract network configuration from secret */}}
{{- $subnetIdFromSecret := "" }}
{{- if and $ccmNetConfigSecret (hasKey $ccmNetConfigSecret.data "subnetId") }}
{{- $subnetIdFromSecret = $ccmNetConfigSecret.data.subnetId | b64dec }}
{{- end }}

{{- $floatingNetworkIdFromSecret := "" }}
{{- if and $ccmNetConfigSecret (hasKey $ccmNetConfigSecret.data "floatingNetworkId") }}
{{- $floatingNetworkIdFromSecret = $ccmNetConfigSecret.data.floatingNetworkId | b64dec }}
{{- end }}

{{/* Perform variable substitutions */}}
{{- $cloudConf = regexReplaceAll "\\$\\{APPLICATION_CREDENTIAL_ID\\}" $cloudConf $appCredId }}
{{- $cloudConf = regexReplaceAll "\\$\\{APPLICATION_CREDENTIAL_SECRET\\}" $cloudConf $appCredSecret }}
{{- $cloudConf = regexReplaceAll "\\$\\{AUTH_URL\\}" $cloudConf (coalesce $val.authUrl "https://cloud.virtomat.net:5000/v3") }}
{{- $cloudConf = regexReplaceAll "\\$\\{REGION\\}" $cloudConf (coalesce $val.region "RegionOne") }}
{{- $cloudConf = regexReplaceAll "\\$\\{SUBNET_ID\\}" $cloudConf (coalesce $subnetIdFromSecret $val.subnetId) }}
{{- $cloudConf = regexReplaceAll "\\$\\{FLOATING_NETWORK_ID\\}" $cloudConf (coalesce $floatingNetworkIdFromSecret $val.floatingNetworkId) }}

{{- $cloudConf -}}
{{- end -}}