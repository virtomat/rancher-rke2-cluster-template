# Rancher RKE2 Cluster Template Helm Chart

|    Type     | Chart Version |
| :---------: | :-----------: |
| application |   `1.0.5`     |

This repository contains a Rancher cluster template Helm chart for provisioning RKE2 clusters on OpenStack.

After adding the repository to Rancher, the template will be visible in `Cluster Management -> Clusters -> Create`.

## Project Status

This chart is currently under an active cleanup and alignment effort.

- Shared chart cleanup and Dev validation are expected to happen first on `dev`.
- Prod-specific adjustments are expected to follow later on `main`.
- Long-running work tracking and progress notes are maintained in [`update-plan.md`](update-plan.md).

## Maintained Files

The main files to keep in sync during this work are:

- [`README.md`](README.md): operator-facing overview, prerequisites, and usage notes
- [`update-plan.md`](update-plan.md): shared roadmap, findings, and progress for both `dev` and `main`
- [`values.yaml`](values.yaml): chart defaults
- [`questions.yaml`](questions.yaml): Rancher UI questions and defaults
- [`templates/`](templates): rendered resources and chart logic
- [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md): environment-specific troubleshooting notes under review

## Supported Providers

### Currently Maintained
- OpenStack

`Custom` still appears in parts of the chart history, but the current templates, examples, and validation focus are centered on OpenStack.

## How This Chart Works

- The chart is installed into `fleet-default`, but it creates Rancher provisioning objects in a derived `u-<suffix>` namespace.
- The namespace suffix is derived from `cluster.config.openstack.applicationCredentialSecretName` using the `os-app-cred-<suffix>` naming convention.
- MultiPool CLI overrides can set `nodePoolCounts.master` and `nodePoolCounts.worker`; `nodepools[].quantity` remains a fallback for older UI paths.
- OpenStack node configs default `configDrive` to `true` so cloud-init can bootstrap reliably even when metadata-service discovery is inconsistent.
- The zero-local-disk workload flavors boot from 40 GiB Cinder volumes by default. `volumeType` is intentionally empty so Cinder selects the target environment's default type.
- The chart supports exactly three validated RKE2 releases: `v1.33.12+rke2r2`, `v1.34.6+rke2r1`, and `v1.35.6+rke2r1` (default). The bundled OpenStack CCM image is derived automatically from the selected version (`v1.33.0`, `v1.34.0`, `v1.35.0` respectively) and is not user configurable; changing the matrix requires a chart release and validation.
- Dev and Prod use the same public workload flavor catalog. The chart defaults to `c1.medium` for control-plane nodes and `s1.medium` for workers; both flavor families have `small`, `medium`, and `large` UI options.
- Expected input secrets in that user namespace:
  - application credential secret `os-app-cred-<suffix>` with `applicationCredentialId` and `applicationCredentialSecret`
  - SSH private key secret `openstack-privatekey` with `privatekey`
  - CCM network config secret `os-ccm-net-config` with `subnetId` and `floatingNetworkId`
- High-level generated resources:
  - `provisioning.cattle.io/v1` `Cluster`
  - `rke-machine-config.cattle.io/v1` `OpenstackConfig`
  - generated `<cluster-name>-cloud-config-<suffix>` Secret
  - OpenStack CCM manifest embedded in `additionalManifest`
  - OpenStack Cinder CSI manifest (driver, sidecars, RBAC, and two StorageClasses) appended to `additionalManifest` after the CCM manifest
- Floating-IP and ingress topology is selected by the effective master count (`nodePoolCounts.master`, falling back to the `master` nodepool `quantity`):
  - single master (count `1`): the master `OpenstackConfig` renders `floatingipPool` (default `ext_net_gts`) and appends `publicIngressSecGroups` to the baseline `secGroups`; the packaged `rke2-ingress-nginx` controller is forced onto that control-plane master with host ports `80` and `443`, tolerating `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, while its Service is disabled
  - HA (count `>= 3`): no node floating IPs are assigned; the packaged `rke2-ingress-nginx` controller service is forced to `enabled: true` with `type: LoadBalancer`, and external addresses are allocated by OpenStack CCM/Octavia from `os-ccm-net-config.floatingNetworkId`. HA relies on the onboarding-managed static `k8s-rke2` NodePort rule from the tenant subnet, so the generated `cloud.conf` sets `manage-security-groups = false` and the CCM must not create per-LB `lb-sg-*` security groups; the public ingress group is never attached in HA, and public `80`/`443` traffic reaches the Octavia floating IP, then the node NodePorts
  - a master count of exactly `2` is rejected at render time with a clear error
- Worker `OpenstackConfig` objects never render `floatingipPool`; worker nodes stay on the private tenant network (`netName`, default `local-net`).
- `os-ccm-net-config` is an input secret, while `<cluster-name>-cloud-config-*` is generated output.
- The chart requires a local `rke2-openstack-environment` ConfigMap in the derived `u-<suffix>` namespace with non-empty `authUrl` and `region` keys. Onboarding projects the canonical `fleet-default/rke2-openstack-environment` ConfigMap into the user namespace, so the chart never reads the `fleet-default` copy. All normal user Helm lookups are therefore local, and no user `fleet-default` access is needed. These values are not chart inputs and are used for both node provisioning and CCM configuration.
- Current chart behavior is RKE2/OpenStack oriented, and the first validation path is a single-node RKE2 install in Dev.
- Client-side `helm lint` and `helm template` cannot resolve the required ConfigMap lookup and are expected to fail offline. Use a server-side dry run or render against the management cluster after onboarding has projected the local ConfigMap into the user namespace.
- The offline Cinder CSI contract test is different from a plain `helm template`: `python3 tests/validate-cinder-csi.py` copies the chart to a temporary directory, replaces only the four `lookup` call sites with synthetic fixtures, and renders all other template logic unchanged. It requires `helm` and Python 3 with PyYAML, never contacts a cluster, and does not relax the production templates' fail-closed lookups.

## OpenStack Cinder CSI And Storage Classes

New clusters bootstrapped from this template install the OpenStack Cinder CSI
driver automatically: the chart appends its manifest to `additionalManifest`
after the CCM manifest, so the driver, its sidecars, RBAC, and both
StorageClasses are created with the cluster. The chart cannot distinguish a
new install from an existing release, so this add-on targets newly provisioned
clusters; do not upgrade an existing release to validate it, and existing
clusters are not changed by this task.

- Images: the driver and sidecars are derived from the same three-version RKE2
  matrix as the CCM (RKE2 `v1.33.12+rke2r2` -> driver `v1.33.0`,
  `v1.34.6+rke2r1` -> driver `v1.34.0`, `v1.35.6+rke2r1` -> driver
  `v1.35.0`) with pinned sidecar tags. There is no user image input.
- Storage classes: `cinder-delete` uses `Delete` and is the sole default;
  `cinder-retain` uses `Retain` and is not a default. Both set
  `volumeBindingMode: WaitForFirstConsumer` and `allowVolumeExpansion: true`,
  and rely on the provisioner default filesystem (ext4). No volume type or
  availability zone is hardcoded: the volume type uses the Cinder environment
  default, and the availability zone is selected through CSI topology from the
  consuming node.
- Class selection: a PVC that omits `storageClassName` gets the default
  `cinder-delete`; an explicit `storageClassName: ""` opts out and leaves the
  claim to a manually managed volume.
- `cinder-retain` keeps the PV and its backing Cinder volume after PVC
  deletion, but it does not rebind automatically. Recovering that data means
  manual PV/volume handling, and any deletion test must record the retained PV
  and volume ID and reconcile only those test resources under an authorized
  run.
- Scope of capability: plain filesystem RWO volumes for general workloads.
  This initial add-on provides no snapshot support and no shared RWX access.
- Authentication is unchanged from the CCM path. The driver mounts only the
  existing `/etc/rancher/rke2/cloud.conf` as a read-only file, so the per-user
  application credential is reused; there are no new credential inputs,
  Secrets, or embedded credentials in the manifest.
- Scheduling: one controller replica runs on a Linux control-plane node and
  tolerates the control-plane/etcd taints; the node plugin runs on every Linux
  node, including masters, with privileged CSI access and host mounts. The
  manifest assumes the default `/var/lib/kubelet`; a custom kubelet root
  directory is not supported.
- Topology caveat: the shared `cloud.conf` sets `ignore-volume-az = true`, but
  that does not by itself reconcile Nova/Cinder availability-zone mismatches.
  Upstream defaults request the node topology AZ, so validate Nova/Cinder AZ
  compatibility before acceptance. Genuinely differing zones need a separately
  designed availability/topology configuration, not blind removal of the check.
- Expansion: `allowVolumeExpansion: true` enables the CSI capability, but
  online resize still depends on backend Cinder support.

Live acceptance was run on 2026-11-06 against a newly provisioned Dev cluster
(chart `1.0.5`, first Helm revision, default RKE2 `v1.35.6+rke2r1`, one
control-plane node and two workers). Observed: controller `1/1`, node DaemonSet
`3/3`, `CSINode` registration on all three nodes, a claim omitting
`storageClassName` defaulted to `cinder-delete` at admission and stayed
`Pending` under WaitForFirstConsumer until a consumer was scheduled, mount,
write, and re-read with SHA-256 verification, a workload move between workers
with detach/reattach of the same volumes, online 1Gi -> 2Gi expansion with the
claim, PV, backend volume, and filesystem all growing, the default `Delete` path
removing PVC, PV, and Cinder volume, and the explicit `Retain` path leaving the
PV `Released` and the Cinder volume available with no attachments.

Scope of that result: a single master plus two workers on RKE2 `v1.35.6+rke2r1`
only. It is not live evidence for HA topology or for the `v1.33.12+rke2r2` and
`v1.34.6+rke2r1` matrix rows, which remain offline-render-only, and it does not
validate Rancher UI RBAC or password authentication. The test cluster and
retained PV/volume were subsequently cleaned up under explicit authorization on
2026-11-06, leaving no test resources; shared onboarding resources were
preserved. This add-on is not yet a full production-ready claim.


## Prerequisites

### OpenStack

#### Platform Environment Configuration

The canonical `rke2-openstack-environment` ConfigMap lives in `fleet-default`.
Onboarding projects it into each user's `u-<suffix>` namespace. The chart reads
only the local `u-<suffix>/rke2-openstack-environment` copy; it never looks up
the `fleet-default` original, so a normal user needs no `fleet-default` read
access. Its `data.authUrl` and `data.region` entries are required and are the
sole source for the OpenStack authentication URL and region. Do not add these
values to chart values or Rancher UI inputs.

#### Dedicated Security Group

This chart expects a pre-created OpenStack security group for Kubernetes nodes.

- Recommended name: `k8s-rke2`
- Default chart value: `cluster.config.openstack.secGroups=k8s-rke2`
- Baseline `secGroups` attach to every master and worker pool. The default `cluster.config.openstack.publicIngressSecGroups=k8s-rke2-public-ingress` is appended only to the `master` pool when the effective master count is `1`; set it empty to attach no public ingress group. In HA (`>= 3` masters) the public ingress group is never attached.
- Helm can attach named security groups to the node definition, but it does not create OpenStack security groups or rules.

For the current validation paths, the important distinction is:

- single master: the master node receives a direct floating IP from `cluster.config.openstack.floatingipPool` (default `ext_net_gts`), receives the public ingress group in addition to the baseline group, and runs the packaged `rke2-ingress-nginx` controller on the control-plane master with host ports `80` and `443`, tolerating `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, while its Service is disabled
- HA (3+ masters): no node floating IPs are assigned; the packaged `rke2-ingress-nginx` controller runs as a `LoadBalancer` service, and OpenStack CCM/Octavia allocate the external address through the `os-ccm-net-config` network Secret (`floatingNetworkId`). HA relies on the onboarding-managed static `k8s-rke2` NodePort rule from the tenant subnet; the generated `cloud.conf` sets `manage-security-groups = false`, the CCM must not create per-LB `lb-sg-*` security groups, and the public ingress group is never attached in HA. Public `80`/`443` traffic reaches the Octavia floating IP, then the node NodePorts.

Minimum baseline rule groups for the dedicated security group for the single-master bootstrap path are:

- all egress
- all ingress from the same security group

The single-master public ingress group needs only TCP `80` and `443` from the intended client CIDRs. Do not add other public ports to that group.

When using `all ingress from the same security group`, separate intra-cluster rules for `9345`, `2379-2380`, and `10250` are redundant because they are already covered by the self-referential rule.

For the HA ingress/`Service type=LoadBalancer` path, the onboarding-managed static `k8s-rke2` security group is the only group attached to the nodes and provides the NodePort rule (`30000-32767`) from the tenant subnet used by the Kubernetes nodes and the Octavia backend path. HA relies on that onboarding-managed rule; the generated `cloud.conf` sets `manage-security-groups = false`, so the CCM must not create per-LB `lb-sg-*` security groups. The public ingress group (`k8s-rke2-public-ingress`) is never attached in HA. Public `80`/`443` traffic reaches the Octavia floating IP first, then the node NodePorts via the amphora. Do not add public `6443` and do not alter the baseline or ingress topology behavior described here.

The chart's `rke2-ingress-nginx` controller behavior depends on topology: single master schedules it on the control-plane master with host ports `80` and `443`, tolerating `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, while disabling its Service; HA (3+ masters) enables it as a `LoadBalancer` service without the single-master host-port, selector, or toleration overrides. Octavia is therefore relevant for HA ingress validation and not for the single-master bootstrap path.

When deleting an HA cluster, retain the Octavia load balancer and floating-IP IDs before removing the Rancher cluster. CCM can exit before it reconciles the `LoadBalancer` Service deletion, leaving those cloud resources behind. Delete any retained test-owned health monitors and members, cascade-delete the load balancer, then delete its floating IP; do not delete unrelated tenant resources.

For temporary Dev debugging only, it can also be useful to allow:

- SSH on `22`
- direct API access on `6443` (single-master bootstrap only)

Those temporary debug rules should be treated as Dev-only and tightened or removed later. Do not add public `6443` for the HA path, and do not alter the baseline or ingress topology behavior described here.

See [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md) for background and examples.

#### Node Driver
Enable the OpenStack node driver in the Rancher Manager UI:
- Cluster Management -> Drivers -> Node Drivers -> OpenStack -> Activate

The chart uses the enabled built-in driver with the onboarding application credential Secret; it does not configure an alternate Rancher credential resource.


#### Secrets
To use `OpenStack` as the cloud provider, you first have to create some secrets on the Rancher management cluster.

The chart derives `u-<suffix>` from `cluster.config.openstack.applicationCredentialSecretName`. This is the only authentication value entered through the chart. It must match `os-app-cred-<suffix>` exactly, and the chart fails before rendering if the required Secret or data keys are absent or empty.

- The onboarding application credential Secret:
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: os-app-cred-<user-suffix>
    namespace: u-<user-suffix>
  data:
    applicationCredentialId: <base64-encoded-application-credential-id>
    applicationCredentialSecret: <base64-encoded-application-credential-secret>
  ```

- The onboarding SSH private-key Secret:
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: openstack-privatekey
    namespace: u-<user-suffix>
  data:
    privatekey: <base64-encoded-private-key-file>
  ```

- The onboarding CCM network Secret:
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: os-ccm-net-config
    namespace: u-<user-suffix>
  data:
    subnetId: <base64-encoded-subnet-id>
    floatingNetworkId: <base64-encoded-floating-network-id>
  ```


### ETCD S3 backup
To enable ETCD backup to S3, create cloud credentials on the Rancher management cluster beforehand:
```yaml
apiVersion: v1
kind: Secret
metadata:
  labels:
    cattle.io/creator: norman
  name: cc-etcd-s3-backup
  namespace: cattle-global-data
data:
  s3credentialConfig-accessKey: <base64-encoded-s3-accessKey>
  s3credentialConfig-secretKey: <base64-encoded-s3-secretKey>
  # Optional
  # s3credentialConfig-defaultBucket: <base64-encoded-s3-defaultBucket>
  # s3credentialConfig-defaultEndpoint: <base64-encoded-s3-defaultEndpoint>
  # s3credentialConfig-defaultFolder: <base64-encoded-s3-defaultFolder>
  # s3credentialConfig-defaultRegion: <base64-encoded-s3-defaultRegion>
  # s3credentialConfig-defaultSkipSSLVerify: <base64-encoded-s3-defaultSkipSSLVerify>
type: Opaque
```
The ID of the created cloud credentials needs to be added in `cluster.config.etcd.s3.cloudCredentialName` like `cattle-global-data:cc-etcd-s3-backup`.


## Installing the Chart

### Helm Install From A Local Checkout

```sh
helm upgrade -i <cluster-name> . -n fleet-default -f values.yaml
```

### Helm Install From A Published Repository

```sh
# Replace <repo-alias> with the Helm repository alias configured in your environment.
helm repo update
helm search repo <repo-alias> --versions
helm install <cluster-name> <repo-alias>/rke2-cluster-templates --version <x.x.x> -n fleet-default -f values.yaml
```

## Helm Chart Deployment Status

```sh
helm status <cluster-name> -n fleet-default
```

## Uninstalling the Chart

```sh
helm delete <cluster-name> -n fleet-default
```


## Known Issues

### Certificate Validation Error When Creating A Downstream Cluster Via Rancher

If a downstream cluster remains in the `Updating` state and `/var/log/cloud-init-output.log` on the nodes contains:

`[FATAL]  Aborting system-agent installation due to requested strict CA verification with no CA checksum provided`

the issue is usually related to the Rancher `agentTLSMode` setting introduced in Rancher 2.8.0. Starting with Rancher 2.9+, the option defaults to `strict`, which can trigger this behavior when `ingress.tls.source` is set to `letsEncrypt` or `secret` instead of `rancher`.

Possible solutions:
1. Upload the CA Certificates to rancher: `kubectl -n cattle-system create secret generic tls-ca --from-file=cacerts.pem=./cacerts.pem`  
  This also requires the configuration option `privateCA=true` for rancher.  
  e.g.: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system --set hostname=rancher.my.org --set bootstrapPassword=admin --set ingress.tls.source=secret --set privateCA=true`

2. Set `agentTLSMode` to `system-store` in Rancher, which can be done in two ways:
   - UI setting: Global Settings -> agent-tls-mode -> Edit Setting -> System Store
   - During Install: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system ... --set agentTLSMode="system-store" ...`

Please check [Release v2.9.0 Changes](https://github.com/rancher/rancher/releases/tag/v2.9.0), [rancher helm-chart](https://github.com/rancher/rancher/blob/main/chart/values.yaml) or the documentation ([TLS Settings](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/installation-references/tls-settings.md), [Adding TLS Secrets](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/add-tls-secrets.md) and [Updating a Private CA Certificate](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/update-rancher-certificate.md#2-createupdate-the-ca-certificate-secret-object)) for more information.

### Kube API Server Audit Log Path

When configuring `audit-log-path` in `cluster.config.machineGlobalConfig.kube_apiserver_arg`, the value must be a file path. If a directory is specified instead, the API server will fail to start. When a file path is provided, the base directory of the file will be automatically created and mounted into the kube-apiserver pod.

## References
- [`rancher-ui-test-checklist.md`](rancher-ui-test-checklist.md): operator checklist for creating the validated HA cluster from the Rancher UI
- [`update-plan.md`](update-plan.md)
- [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md)
- [Hardened Rancher Cluster Templates by Rancher Government Solutions](https://artifacthub.io/packages/helm/rancher-cluster-templates/rancher-cluster-templates)
- [rancher cluster-template-examples](https://github.com/rancher/cluster-template-examples/tree/main)
