{{/*
OpenStack CCM manifest template
This template processes the openstack-ccm-manifest.yaml file and renders it with proper templating
*/}}
{{- define "rancher-cluster-templates.openstackCcmManifest" -}}
{{- $manifest := .Files.Get "files/openstack-ccm-manifest.yaml" }}
{{- $manifest -}}
{{- end -}}