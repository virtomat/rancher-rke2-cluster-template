# Rancher UI Test Checklist: HA Cluster (Pending Live Acceptance)

Operator checklist for creating and recording the HA RKE2 cluster from the Rancher UI.

## Pre-Checks

- [ ] Rancher context/environment confirmed (Dev: `virt-infra-dev-buc-hq`, Prod: `virt-infra-prod-buc-hq`)
- [ ] Application credential secret exists: `os-app-cred-<suffix>` with keys `applicationCredentialId` and `applicationCredentialSecret`
- [ ] SSH private key secret exists: `openstack-privatekey` with key `privatekey`
- [ ] CCM network config secret exists: `os-ccm-net-config` with keys `subnetId` and `floatingNetworkId`
- [ ] Local environment ConfigMap exists: `u-<suffix>/rke2-openstack-environment` with keys `authUrl` and `region` (projected by onboarding from the canonical `fleet-default` copy; no `fleet-default` read access is needed)
- [ ] Baseline OpenStack security group `k8s-rke2` exists with required rules (including the NodePort `30000-32767` rule from the tenant subnet for the HA path)
- [ ] Public ingress security group `k8s-rke2-public-ingress` exists for the single-master path
- [ ] No additional storage credential input is required: Cinder CSI reuses the per-user application credential through the node `cloud.conf`

## Expected Defaults (Offline-Verified Baseline)

| Setting | Expected Value |
| :--- | :--- |
| Kubernetes version | `v1.35.9+rke2r1` (default) |
| OpenStack CCM image | `registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0` (derived from `v1.35.9+rke2r1`) |
| OpenStack image | `ubuntu-24.04` |
| `secGroups` | `k8s-rke2` |
| `publicIngressSecGroups` | `k8s-rke2-public-ingress` (default; appended only to the master pool when the effective master count is exactly `1` and never attached in HA) |
| `configDrive` | `true` |
| `floatingipPool` | `ext_net_gts` (default; rendered on the master pool only when the effective master count is exactly `1`) |
| Ingress controller | `ingress-controller: [traefik]`; the packaged `rke2-traefik` chart owns GatewayClass `traefik`, Gateway `kube-system/shared-gateway`, and one controller Service. Single master uses host ports `80`/`443` on the control-plane master with a ClusterIP Service; HA clears host ports and uses one `LoadBalancer` Service |
| Gateway default listener | `web`: HTTP, packaged port `8000`, external `80`, namespace opt-in `gateway-access: public`. Port `443` and the `websecure` entrypoint are published, but no HTTPS listener/TLS is configured by default |

- Supported matrix (CCM image is derived from the selected RKE2 version and is not separately configurable): `v1.33.13+rke2r2` -> CCM `v1.33.0`, `v1.34.12+rke2r1` -> CCM `v1.34.0`, `v1.35.9+rke2r1` -> CCM `v1.35.0` (default). Changing the matrix requires a chart release and validation.
- The latest live Rancher observed for this workspace is 2.14.3. Its official support matrix covers Kubernetes 1.33-1.35 only; do not add 1.36/1.37 on that basis. The Gateway baseline has live acceptance on the default `v1.35.9+rke2r1` (CLI-provisioned single-node and HA); the `v1.33`/`v1.34` pins remain offline-only. See [`docs/gateway-live-acceptance.md`](docs/gateway-live-acceptance.md).
- Storage add-on for new clusters: the same manifest appends OpenStack Cinder CSI after the CCM and creates exactly two StorageClasses, `cinder-delete` (`Delete`, sole default) and `cinder-retain` (`Retain`, non-default). Both use `WaitForFirstConsumer` and `allowVolumeExpansion: true`, default to ext4 through the provisioner, and pin no volume type or availability zone.

## Single vs HA Topology

The chart selects topology from the effective master count (`nodePoolCounts.master`, falling back to the `master` nodepool `quantity`). Only `1` (single master) and `>= 3` (HA) are supported; a master count of exactly `2` is rejected at render time with a clear error.

### Single Master (count = 1)

- The master `OpenstackConfig` renders `floatingipPool` (default `ext_net_gts`) and the node receives a direct floating IP.
- The master `OpenstackConfig` uses `k8s-rke2,k8s-rke2-public-ingress` by default; workers retain only the baseline `k8s-rke2` group.
- Workers never render `floatingipPool`; they stay on the private tenant network (`local-net`).
- The packaged `rke2-traefik` Gateway controller is selected onto the control-plane master, tolerates `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, and exposes host ports `80` and `443` through the floating IP while its Service is a `ClusterIP`.
- The public ingress security group needs only TCP `80` and `443` from intended client CIDRs.

### HA (count >= 3)

- No node floating IPs are assigned.
- Masters and workers retain only the baseline `k8s-rke2` group; the public ingress group is never attached in HA.
- HA relies on the onboarding-managed static `k8s-rke2` NodePort rule (`30000-32767`) from the tenant subnet. The generated `cloud.conf` sets `manage-security-groups = false`, so the CCM must not create per-LB `lb-sg-*` security groups.
- The packaged `rke2-traefik` controller keeps one `LoadBalancer` Service and clears the host ports; no single-master host-port, selector, or toleration override is applied.
- The external ingress address is allocated by OpenStack CCM/Octavia from `os-ccm-net-config.floatingNetworkId`. Public `80`/`443` traffic reaches the Octavia floating IP first, then the node NodePorts. Do not add public `6443` and do not alter the baseline or ingress topology behavior.

## UI Path

1. Rancher UI -> Cluster Management -> Clusters -> Create
2. Select the RKE2 cluster template from the template list
3. Fill in the cluster definition using the expected parameters below

## HA Test Parameters (Pending Live Acceptance)

- **Provider/Template**: OpenStack
- **Node Pool Template**: `MultiPool`
- **Control-plane/etcd nodes**: 3
- **Worker nodes**: 1
- **Application credential secret name**: `os-app-cred-<suffix>` (must match the existing secret in the `u-<suffix>` namespace)
- **Advanced settings to verify** (if visible in UI):
   - `secGroups` = `k8s-rke2`
   - `publicIngressSecGroups` = `k8s-rke2-public-ingress` (single master only)
  - `configDrive` = `true`
  - Kubernetes version = `v1.35.9+rke2r1`
  - OpenStack image = `ubuntu-24.04`

## Post-Create Checkpoints

- [ ] Cluster conditions: `Connected=True`, `Provisioned=True`, `Ready=True`, `Updated=True`
- [ ] Machine Deployments: `master 3/3 ready`, `worker 1/1 ready`
- [ ] All 4 Machines show `Running` status with nodeRefs assigned
- [ ] Node roles correct: 3 control-plane/etcd, 1 worker
- [ ] Retain Octavia LB/FIP IDs before cluster deletion. For test teardown only, merge `rke2-traefik.service.enabled: false` into this cluster's owning chartValues and remove only the test HTTPS listener (keep `web`) while CCM is live; packaged Helm then deletes the Service, CCM requests load-balancer deletion, Octavia removes the LB, VIP, service compute, and amphora, and CCM removes the FIP before the cluster is uninstalled. Rancher CAPI then removes the Kubernetes nodes, boot volumes, and ports and does not own the amphora or VIP. Do not delete the Service directly on its own, because Helm can recreate it.

## Gateway Baseline Checks

Scope: the Traefik Gateway baseline and TLS onboarding have live acceptance on
the default `v1.35.9+rke2r1` only, through CLI-provisioned single-node and HA
clusters; the `v1.33`/`v1.34` pins and the Rancher UI path itself remain
unverified. Keep these boxes unmarked until observed on the target UI-created
cluster. This section does not test TLS onboarding; see
[`docs/gateway-api.md`](docs/gateway-api.md) for the workflow and
[`docs/gateway-live-acceptance.md`](docs/gateway-live-acceptance.md) for the
2026-11-06 results and limits.

- [ ] The rendered `Cluster` selects `ingress-controller: [traefik]` and has no legacy `rke2-ingress-nginx` chartValues
- [ ] GatewayClass `traefik` exists and is accepted by controller `traefik.io/gateway-controller`
- [ ] Gateway `kube-system/shared-gateway` exists; its default listener set is exactly `web` with protocol `HTTP`, port `8000`, and namespace selector `gateway-access: public`
- [ ] The Gateway does not fabricate `spec.addresses` or `status`; in single-master host-port mode status addresses may be empty and DNS remains manual against the master floating IP
- [ ] External `80` and `443` are published by the controller Service/host ports or the HA LoadBalancer, but only HTTP is served until an HTTPS listener is added
- [ ] A labeled application namespace can attach an HTTPRoute to `web`; an unlabeled namespace cannot
- [ ] HA has one Traefik `LoadBalancer` Service with host ports cleared; single master has a `ClusterIP` Service with host ports `80`/`443` on the control-plane master
- [ ] No cert-manager, ClusterIssuer, Certificate, TLS Secret, or HTTPS listener is installed by the template

## Cinder CSI And Storage Checks

Scope: Cinder CSI is installed for new clusters only. Do not upgrade an existing release to exercise it, and select the Dev target explicitly before running these checks. Keep this checklist generic and unmarked; record results only from an observed run.

Historical tested scope note (2026-11-06): the checks below were observed once on a newly provisioned Dev cluster running the default RKE2 `v1.35.6+rke2r1` with one control-plane and two workers, chart `1.0.5` revision `1`. Controller `1/1`, node DaemonSet `3/3`, `CSINode` registration, WaitForFirstConsumer, default-class selection, mount/write/read, cross-worker detach/reattach, online expansion, `Delete`, and `Retain` all behaved as described. The HA topology and the `v1.33.12+rke2r2`/`v1.34.6+rke2r1` rows were not exercised live and remain unverified; that run also did not test Rancher UI RBAC or password login. The retained PV and Cinder volume were subsequently cleaned up under explicit authorization on 2026-11-06, so no test resources remain. That run predates the `1.1.0` patch matrix and Gateway baseline; fresh live acceptance is required.

- [ ] CSI controller Deployment `cinder-csi-controller` is available (1/1) and the `cinder-csi-node` DaemonSet is ready on every Linux node, including control-plane nodes
- [ ] Every node has a `CSINode` object registering `cinder.csi.openstack.org`
- [ ] Exactly two StorageClasses exist; `cinder-delete` has `storageclass.kubernetes.io/is-default-class: "true"` and `cinder-retain` has it set to `"false"` (not default)
- [ ] A PVC that omits `storageClassName` stays `Pending` until a consuming Pod is scheduled (WaitForFirstConsumer), then binds through `cinder-delete`; an explicit `storageClassName: ""` opts out of dynamic provisioning
- [ ] Pod mount, write, and read succeed; where a second worker exists, move the Pod and confirm detach/reattach
- [ ] Expanding the PVC request grows both the claim and the filesystem when the backend supports it
- [ ] Delete path: after PVC deletion, the PV follows the `Delete` policy and the Cinder volume is removed
- [ ] Retain path: with `storageClassName: cinder-retain`, PVC deletion leaves the PV `Released` and the backing Cinder volume present; record the PV name and Cinder volume ID
- [ ] Retain does not rebind automatically; recovering the data requires manual PV/volume handling, and cleanup removes only the recorded test PV/volume under an authorized run
- [ ] Snapshots and shared RWX access are not part of this initial add-on and are not expected to work

## Troubleshooting Notes

- **Bootstrap stalls**: check whether a node fell back to `DatasourceNone` in cloud-init. If `configDrive` is not set, metadata-service discovery may be inconsistent and nodes can fail to inject the SSH authorized key.
- **Cluster agent not connecting**: distinguish this from cloud-init bootstrap. If nodes are `Running` with nodeRefs but the cluster stays on `waiting for cluster agent to connect`, the issue is agent connectivity (network/Rancher endpoint), not cloud-init bootstrap.
- **Stale Helm release**: if a previous install failed, a stale Helm release secret may block reinstall. Remove it before retrying.
