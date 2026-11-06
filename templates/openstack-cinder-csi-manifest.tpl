{{/*
OpenStack Cinder CSI manifest template
This template processes the openstack-cinder-csi-manifest.yaml file and renders
it with proper templating. The image bundle is derived from the RKE2 version.
*/}}
{{- define "rancher-cluster-templates.openstackCinderCsiManifest" -}}
{{- $manifest := .Files.Get "files/openstack-cinder-csi-manifest.yaml" }}
{{- tpl $manifest . -}}
{{- end -}}
