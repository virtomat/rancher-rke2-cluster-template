#!/usr/bin/env bash
set -euo pipefail

# Helm client-side rendering has no lookup mock. Exercise the missing-object
# failure and statically verify the lookup-backed validation contracts.
chart_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
error_file=$(mktemp)
trap 'rm -f "$error_file"' EXIT

if helm template contract "$chart_dir" --namespace fleet-default \
  --set cluster.config.openstack.applicationCredentialSecretName=os-app-cred-test \
  >/dev/null 2>"$error_file"; then
  printf '%s\n' "expected rendering without rke2-openstack-environment to fail" >&2
  exit 1
fi

rg -Fq "rke2-openstack-environment ConfigMap is required" "$error_file"

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
  rg -Fq "rke2-openstack-environment ConfigMap requires non-empty $key" "$helper"
done

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

for decoded in '\$id' '\$credentialSecret' '\$subnetId' '\$floatingNetworkId'; do
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
rg -A 4 -F 'variable: cluster.config.openstack.floatingipPool' "$questions" | rg -Fq "default: 'ext_net_gts'"

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
version_question=$(rg -A 12 -F 'variable: cluster.config.kubernetesVersion' "$questions")
printf '%s\n' "$version_question" | rg -Fq 'default: v1.35.6+rke2r1'
printf '%s\n' "$version_question" | rg -Fq -- '- v1.35.6+rke2r1'
for retained_version in v1.31.13+rke2r1 v1.32.9+rke2r1 v1.33.12+rke2r2; do
  printf '%s\n' "$version_question" | rg -Fq -- "- $retained_version"
done

rg -Fq 'imageName: ubuntu-24.04' "$values"
image_question=$(rg -A 8 -F 'variable: cluster.config.openstack.imageName' "$questions")
printf '%s\n' "$image_question" | rg -Fq "default: 'ubuntu-24.04'"
assert_absent 'ubuntu-22\.04' "$values" "$questions"
rg -Fq 'registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0' "$ccm_manifest"
assert_absent 'openstack-cloud-controller-manager:v1\.33\.0' "$ccm_manifest"

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
  rg -Fq 'v1.35.6+rke2r1' "$document"
done
rg -Fq 'v1.35.0' "$readme"
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

if rg -Fq 'floatingipPool: office' "$values" ||
  rg -A 4 -F 'variable: cluster.config.openstack.floatingipPool' "$questions" | rg -Fq "default: 'office'"; then
  printf '%s\n' "stale floating-IP pool default found" >&2
  exit 1
fi

printf '%s\n' "OpenStack environment contract validation passed"
