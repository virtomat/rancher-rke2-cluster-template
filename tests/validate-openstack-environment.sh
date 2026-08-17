#!/usr/bin/env bash
set -euo pipefail

# Statically verify the lookup-backed and topology contracts without rendering.
chart_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

helper="$chart_dir/templates/_helpers.tpl"
node_config="$chart_dir/templates/nodeconfig-openstack.yaml"
cloud_config="$chart_dir/templates/cloud-config.tpl"
values="$chart_dir/values.yaml"
questions="$chart_dir/questions.yaml"
cluster="$chart_dir/templates/cluster.yaml"
managed_charts="$chart_dir/templates/managedcharts.yaml"
cluster_role_binding="$chart_dir/templates/clusterroletemplatebinding.yaml"
ccm_manifest="$chart_dir/files/openstack-ccm-manifest.yaml"
readme="$chart_dir/README.md"
checklist="$chart_dir/rancher-ui-test-checklist.md"
update_plan="$chart_dir/update-plan.md"
security_doc="$chart_dir/troubleshooting/security-group-tuning.md"

assert_absent() {
  local pattern=$1
  shift
  if rg -q -- "$pattern" "$@"; then
    printf 'unexpected obsolete path or fallback: %s\n' "$pattern" >&2
    exit 1
  fi
}

for key in authUrl region; do
  rg -Fq "hasKey \$environment.data \"$key\"" "$helper"
  rg -Fq "OpenStack environment ConfigMap %q in namespace %q requires non-empty $key" "$helper"
done

rg -Fq 'lookup "v1" "ConfigMap" $namespace "rke2-openstack-environment"' "$helper"
if rg -Fq 'lookup "v1" "ConfigMap" .Release.Namespace' "$helper"; then
  printf '%s\n' "environment ConfigMap lookup must use the derived namespace, not .Release.Namespace" >&2
  exit 1
fi

rg -Fq 'authUrl: {{ $environment.authUrl | quote }}' "$node_config"
rg -Fq 'region: {{ $environment.region | quote }}' "$node_config"
rg -Fq '"\\$\\{AUTH_URL\\}" $cloudConf $environment.authUrl' "$cloud_config"
rg -Fq '"\\$\\{REGION\\}" $cloudConf $environment.region' "$cloud_config"

rg -Fq 'regexMatch "^os-app-cred-[a-z0-9]+(-[a-z0-9]+)*$" $appCredSecretName' "$helper"
rg -Fq 'cluster.config.openstack.applicationCredentialSecretName must match os-app-cred-<suffix>' "$helper"
rg -Fq 'define "rancher-cluster-templates.applicationCredential"' "$helper"
rg -Fq 'define "rancher-cluster-templates.ccmNetworkConfig"' "$helper"

for key in applicationCredentialId applicationCredentialSecret subnetId floatingNetworkId; do
  rg -Fq "hasKey \$secret.data \"$key\"" "$helper"
  rg -Fq "data.$key" "$helper"
done

for encoded in encodedId encodedCredentialSecret encodedSubnetId encodedFloatingNetworkId; do
  rg -Fq "regexMatch \"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?\$\" \$$encoded" "$helper"
  rg -Fq "b64dec \$$encoded" "$helper"
done

for message in \
  'OpenStack application credential Secret %q in namespace %q has malformed data.applicationCredentialId' \
  'OpenStack application credential Secret %q in namespace %q has malformed data.applicationCredentialSecret' \
  'OpenStack CCM network Secret %q in namespace %q has malformed data.subnetId' \
  'OpenStack CCM network Secret %q in namespace %q has malformed data.floatingNetworkId'; do
  rg -Fq "$message" "$helper"
done

for decoded in '$id' '$credentialSecret' '$subnetId' '$floatingNetworkId'; do
  rg -Fq "if not (trim $decoded)" "$helper"
  if rg 'fail ' "$helper" | rg -q "$decoded"; then
    printf 'Secret validation failure message exposes a decoded value variable\n' >&2
    exit 1
  fi
done

rg -Fq 'include "rancher-cluster-templates.applicationCredential" $ | fromYaml' "$node_config"
rg -Fq 'applicationCredentialId: {{ $applicationCredential.id | quote }}' "$node_config"
rg -Fq 'applicationCredentialSecret: {{ $applicationCredential.secret | quote }}' "$node_config"
rg -Fq 'include "rancher-cluster-templates.applicationCredential" . | fromYaml' "$cloud_config"
rg -Fq 'include "rancher-cluster-templates.ccmNetworkConfig" . | fromYaml' "$cloud_config"
rg -Fq '"\\$\\{SUBNET_ID\\}" $cloudConf $ccmNetworkConfig.subnetId' "$cloud_config"
rg -Fq '"\\$\\{FLOATING_NETWORK_ID\\}" $cloudConf $ccmNetworkConfig.floatingNetworkId' "$cloud_config"

assert_absent 'cloudCredentialSecretName' "$values" "$questions" "$cluster"
assert_absent 'applicationCredential(Name|Id|Secret):' "$values"
assert_absent 'applicationCredential(Name|Id|Secret) }}' "$node_config"
assert_absent 'coalesce .*subnetId|coalesce .*floatingNetworkId' "$cloud_config"
assert_absent 'subnetId:|floatingNetworkId:' "$values"
assert_absent 'variable: cluster.config.openstack.applicationCredential(Id|Secret)$' "$questions"
assert_absent 'variable: cluster.config.openstack.defaultPrivateKey' "$questions"
assert_absent 'variable: cluster.config.openstack.defaultKeypairName' "$questions"
assert_absent 'variable: .*keypairName' "$questions"

rg -Fq '{{- $pkSecretName := $.Values.cluster.config.openstack.defaultPrivateKeyFileSecretName | default "openstack-privatekey" }}' "$node_config"
rg -Fq '{{- if not $pkSecret }}' "$node_config"
rg -Fq '{{- if not (and $pkSecret.data (hasKey $pkSecret.data "privatekey")) }}' "$node_config"
rg -Fq '{{- $privateKey := b64dec (index $pkSecret.data "privatekey") }}' "$node_config"
rg -Fq '{{- if not (trim $privateKey) }}' "$node_config"
rg -Fq 'privateKeyFile: | {{ $privateKey | nindent 4 }}' "$node_config"

for message in \
  'OpenStack SSH private-key Secret %q is required in namespace %q' \
  'OpenStack SSH private-key Secret %q in namespace %q requires data.privatekey' \
  'OpenStack SSH private-key Secret %q in namespace %q has empty data.privatekey'; do
  rg -Fq "fail (printf \"$message\" \$pkSecretName \$namespace)" "$node_config"
done

rg -Fq 'defaultKeypairName: bootstrap' "$values"
rg -Fq 'defaultPrivateKeyFileSecretName: openstack-privatekey' "$values"
rg -Fq 'floatingipPool: ext_net_gts' "$values"
rg -Fq '# Rancher NodeDriver floating-IP network name; this is not the CCM network UUID.' "$values"
floating_question=$(rg -A 8 -F 'variable: cluster.config.openstack.floatingipPool' "$questions")
printf '%s\n' "$floating_question" | rg -Fq "default: 'ext_net_gts'"
printf '%s\n' "$floating_question" | rg -Fq 'Rancher NodeDriver floating-IP network name'
printf '%s\n' "$floating_question" | rg -Fq 'CCM floatingNetworkId is sourced from os-ccm-net-config'
rg -Fq 'include "rancher-cluster-templates.masterCount" $ | int' "$node_config"
rg -Fq 'floatingipPool: {{ $.Values.cluster.config.openstack.floatingipPool }}' "$node_config"
rg -Fq '{{- if and (eq $nodepool.name "master") (eq $masterCount 1) }}' "$node_config"
test "$(rg -Fc 'floatingipPool:' "$node_config")" -eq 1

# Baseline groups apply everywhere; the public ingress group is single-master only.
rg -Fq 'secGroups: k8s-rke2' "$values"
rg -Fq 'publicIngressSecGroups: k8s-rke2-public-ingress' "$values"
rg -Fq '{{- $secGroups := $.Values.cluster.config.openstack.secGroups }}' "$node_config"
rg -Fq '{{- $publicIngressSecGroups := trim (default "" $.Values.cluster.config.openstack.publicIngressSecGroups) }}' "$node_config"
rg -Fq '{{- $secGroups = printf "%s,%s" $secGroups $publicIngressSecGroups }}' "$node_config"
rg -Fq '{{- $secGroups = $publicIngressSecGroups }}' "$node_config"
rg -Fq 'secGroups: {{ $secGroups }}' "$node_config"
public_ingress_question=$(rg -A 8 -F 'variable: cluster.config.openstack.publicIngressSecGroups' "$questions")
printf '%s\n' "$public_ingress_question" | rg -Fq "default: 'k8s-rke2-public-ingress'"
printf '%s\n' "$public_ingress_question" | rg -Fq 'show_if: configMode=Advanced'
rg -Fq 'publicIngressSecGroups' "$readme"
rg -Fq 'publicIngressSecGroups' "$checklist"
rg -Fq 'publicIngressSecGroups' "$update_plan"
rg -Fq 'publicIngressSecGroups' "$security_doc"

# HA relies on the onboarding-managed static `k8s-rke2` NodePort rule from the tenant subnet;
# CCM security-group management must be disabled so it never creates per-LB `lb-sg-*` groups.
cloud_conf="$chart_dir/files/cloud.conf"
rg -Fq 'manage-security-groups = false' "$cloud_conf"
if rg -Fq 'manage-security-groups = true' "$cloud_conf"; then
  printf '%s\n' "CCM security-group management must be disabled (manage-security-groups = false)" >&2
  exit 1
fi
for document in "$readme" "$checklist" "$update_plan" "$security_doc"; do
  rg -Fq 'manage-security-groups = false' "$document"
  rg -Fq 'lb-sg-*' "$document"
  rg -Fq 'never attached in HA' "$document"
  rg -Fq 'public `6443`' "$document"
  rg -Fq 'reaches the Octavia floating IP' "$document"
  rg -Fq 'NodePort rule' "$document"
  rg -Fq 'onboarding-managed' "$document"
done

rg -Fq 'masterFlavorName: c1.medium' "$values"
rg -Fq 'workerFlavorName: s1.medium' "$values"

master_question=$(rg -A 10 -F 'variable: cluster.config.openstack.masterFlavorName' "$questions")
worker_question=$(rg -A 10 -F 'variable: cluster.config.openstack.workerFlavorName' "$questions")

printf '%s\n' "$master_question" | rg -Fq "default: 'c1.medium'"
printf '%s\n' "$worker_question" | rg -Fq "default: 's1.medium'"

for flavor in c1.small c1.medium c1.large; do
  printf '%s\n' "$master_question" | rg -Fq -- "- $flavor"
done

for flavor in s1.small s1.medium s1.large; do
  printf '%s\n' "$worker_question" | rg -Fq -- "- $flavor"
done

rg -Fq 'bootFromVolume: true' "$values"
rg -Fq 'configDrive: true' "$values"
rg -Fq 'volumeSize: 40' "$values"
rg -Fq 'volumeType: ""' "$values"

for field in bootFromVolume configDrive volumeSize; do
  rg -Fq "hasKey \$nodepool.openstackconfig \"$field\"" "$node_config"
done

rg -Fq '{{- if and (hasKey $nodepool.openstackconfig "bootFromVolume") (eq (toString $nodepool.openstackconfig.bootFromVolume) "false") }}' "$node_config"
rg -Fq '{{- fail "Zero-local-disk workload flavors require bootFromVolume=true" }}' "$node_config"
test "$(rg -Fc 'bootFromVolume: true' "$node_config")" -eq 1
if rg -Fq 'bootFromVolume: {{' "$node_config"; then
  printf '%s\n' "bootFromVolume must not pass through a node-pool override" >&2
  exit 1
fi
rg -Fq 'configDrive: true' "$node_config"
rg -Fq 'volumeSize: "40"' "$node_config"

for pool in 0 1; do
  for field in bootFromVolume configDrive volumeSize volumeType; do
    test "$(rg -Fc "variable: nodepools.$pool.openstackconfig.$field" "$questions")" -eq 1
    question=$(rg -A 9 -F "variable: nodepools.$pool.openstackconfig.$field" "$questions")
    if [ "$field" = volumeSize ]; then
      printf '%s\n' "$question" | rg -Fq "default: '40'"
    elif [ "$field" = volumeType ]; then
      printf '%s\n' "$question" | rg -Fq "default: ''"
    else
      printf '%s\n' "$question" | rg -Fq "default: 'true'"
      if [ "$field" = bootFromVolume ]; then
        printf '%s\n' "$question" | rg -Fq 'false is rejected'
      fi
    fi
  done
done

for field in bootFromVolume configDrive; do
  if rg -A 6 -F "variable: nodepools.1.openstackconfig.$field" "$questions" | rg -Fq "default: 'false'"; then
    printf '%s\n' "worker $field default must not be false" >&2
    exit 1
  fi
done

if rg -A 6 -F 'variable: nodepools.0.openstackconfig.volumeSize' "$questions" | rg -Fq 'show_if:'; then
  printf '%s\n' "SinglePool volume size must be visible without an extra toggle" >&2
  exit 1
fi

rg -Fq '{{- if $nodepool.openstackconfig.volumeType }}' "$node_config"

rg -Fq 'kubernetesVersion: "v1.35.6+rke2r1"' "$values"
version_question=$(rg -A 14 -F 'variable: cluster.config.kubernetesVersion' "$questions")
printf '%s\n' "$version_question" | rg -Fq 'default: v1.35.6+rke2r1'
for supported_version in v1.33.12+rke2r2 v1.34.6+rke2r1 v1.35.6+rke2r1; do
  printf '%s\n' "$version_question" | rg -Fq -- "- $supported_version"
done
for dropped_version in v1.31.13+rke2r1 v1.32.9+rke2r1; do
  if printf '%s\n' "$version_question" | rg -Fq -- "- $dropped_version"; then
    printf 'unsupported RKE2 version still offered: %s\n' "$dropped_version" >&2
    exit 1
  fi
done
printf '%s\n' "$version_question" | rg -Fq 'CCM image is derived automatically'

schema="$chart_dir/values.schema.json"
rg -Fq '"kubernetesVersion"' "$schema"
rg -Fq '"enum"' "$schema"
for supported_version in v1.33.12+rke2r2 v1.34.6+rke2r1 v1.35.6+rke2r1; do
  rg -Fq "\"$supported_version\"" "$schema"
done
assert_absent 'v1\.31|v1\.32' "$schema"

rg -Fq 'imageName: ubuntu-24.04' "$values"
image_question=$(rg -A 8 -F 'variable: cluster.config.openstack.imageName' "$questions")
printf '%s\n' "$image_question" | rg -Fq "default: 'ubuntu-24.04'"
printf '%s\n' "$image_question" | rg -Fq 'show_if: configMode=Advanced'
if printf '%s\n' "$image_question" | rg -Fq 'show_if: nodePoolTemplate=SinglePool'; then
  printf '%s\n' "image question must not be gated to SinglePool" >&2
  exit 1
fi
assert_absent 'ubuntu-22\.04' "$values" "$questions"
ccm_helper="$chart_dir/templates/openstack-ccm-manifest.tpl"
rg -Fq 'tpl $manifest .' "$ccm_helper"
rg -Fq 'image: {{ include "rancher-cluster-templates.openstackCcmImage" . }}' "$ccm_manifest"
assert_absent 'openstack-cloud-controller-manager:v1\.3[345]\.0' "$ccm_manifest"
rg -Fq 'define "rancher-cluster-templates.openstackCcmImage"' "$helper"
for pair in v1.33.12+rke2r2:v1.33.0 v1.34.6+rke2r1:v1.34.0 v1.35.6+rke2r1:v1.35.0; do
  version=${pair%%:*}
  tag=${pair#*:}
  rg -Fq "$version" "$helper"
  rg -Fq "openstack-cloud-controller-manager:$tag" "$helper"
done
rg -Fq 'Unsupported RKE2 Kubernetes version' "$helper"

rg -Fq 'define "rancher-cluster-templates.masterCount"' "$helper"
rg -Fq '(default dict .Values.nodePoolCounts).master' "$helper"
rg -Fq 'eq .name "master"' "$helper"
rg -Fq 'Master node count of 2 is not supported' "$helper"
rg -Fq 'Master node count must be exactly 1 (single master) or at least 3 (HA)' "$helper"

rg -Fq 'include "rancher-cluster-templates.masterCount" $ | int' "$cluster"
rg -Fq 'deepCopy' "$cluster"
rg -Fq 'mergeOverwrite' "$cluster"
rg -Fq 'rke2-ingress-nginx' "$cluster"
rg -Fq 'dict "enabled" false' "$cluster"
rg -Fq '"hostPort" (dict "enabled" true "ports" (dict "http" 80 "https" 443))' "$cluster"
rg -Fq '"nodeSelector" (dict "kubernetes.io/os" "linux" "node.kubernetes.io/control-plane" "true")' "$cluster"
rg -Fq '"tolerations" (list (dict "key" "node-role.kubernetes.io/control-plane" "operator" "Exists" "effect" "NoSchedule") (dict "key" "node-role.kubernetes.io/etcd" "operator" "Exists" "effect" "NoExecute"))' "$cluster"
rg -Fq 'dict "enabled" true "type" "LoadBalancer"' "$cluster"
ha_ingress_values=$(rg -F 'dict "enabled" true "type" "LoadBalancer"' "$cluster")
if printf '%s\n' "$ha_ingress_values" | rg -q -e 'hostPort|nodeSelector|tolerations'; then
  printf '%s\n' "HA ingress values must not override hostPort, nodeSelector, or tolerations" >&2
  exit 1
fi

rg -Fq 'variable: cluster.config.localClusterAuthEndpoint.fqdn' "$questions"
rg -Fq 'variable: cluster.config.localClusterAuthEndpoint.caCerts' "$questions"
assert_absent 'variable: localClusterAuthEndpoint\.' "$questions"
rg -Fq 'variable: addons.monitoring.version' "$questions"
rg -Fq 'variable: addons.monitoring.values' "$questions"
assert_absent 'variable: monitoring\.(version|values)' "$questions"

rg -Fq 'namespace: {{ $namespace }}' "$managed_charts"
test "$(rg -Fc 'namespace: {{ $namespace }}' "$managed_charts")" -eq 2
rg -Fq '{{ toYaml .Values.addons.monitoring.values | nindent 4 }}' "$managed_charts"
rg -Fq '    - clusterName: {{ .Values.cluster.name }}' "$managed_charts"
rg -Fq 'include "rancher-cluster-templates.derivedNamespace" $root' "$cluster_role_binding"
assert_absent 'include "rancher-cluster-templates\.derivedNamespace" \.' "$cluster_role_binding"

for document in "$readme" "$checklist" "$update_plan"; do
  rg -Fq 'v1.33.12+rke2r2' "$document"
  rg -Fq 'v1.34.6+rke2r1' "$document"
  rg -Fq 'v1.35.6+rke2r1' "$document"
done
rg -Fq 'changing the matrix requires a chart release' "$readme"
assert_absent 'username/password authentication|cluster\.config\.cloudCredentialSecretName' "$readme"

if rg -Fq 'volumeType: rbd1' "$values" "$node_config" ||
  rg -Fq "default: 'rbd1'" "$questions"; then
  printf '%s\n' "Cinder volume type must remain environment-default" >&2
  exit 1
fi

if printf '%s\n%s\n' "$master_question" "$worker_question" | rg -Fq 'c1e.' ||
  printf '%s\n%s\n' "$master_question" "$worker_question" | rg -Fq 's1e.'; then
  printf '%s\n' "obsolete flavor default or option found" >&2
  exit 1
fi

rg -Fq 'single master (count `1`)' "$readme"
rg -Fq 'HA (count `>= 3`)' "$readme"
rg -Fq 'floatingipPool' "$readme"
rg -Fq 'floatingNetworkId' "$readme"
rg -Fq 'exactly `2` is rejected' "$readme"
rg -Fq 'Single vs HA Topology' "$checklist"
rg -Fq 'ext_net_gts' "$checklist"
rg -Fq 'masterCount' "$update_plan"
rg -Fq 'single master (count `1`)' "$update_plan"
rg -Fq 'HA (count `>= 3`)' "$update_plan"
rg -Fq 'floatingipPool' "$update_plan"
rg -Fq 'Scope note: this document is about the OpenStack CCM / Octavia / `Service type=LoadBalancer` path used by HA clusters (3+ masters)' "$security_doc"
rg -Fq 'floatingipPool' "$security_doc"
for document in "$readme" "$checklist" "$update_plan" "$security_doc"; do
  rg -Fq 'host ports `80` and `443`' "$document"
  rg -Fq 'control-plane master' "$document"
  rg -Fq 'node-role.kubernetes.io/etcd:NoExecute' "$document"
done
for document in "$readme" "$checklist" "$update_plan" "$security_doc"; do
  rg -Fq 'only TCP `80` and `443`' "$document"
done

printf '%s\n' "OpenStack environment contract validation passed"
