# Rancher UI Test Checklist: Validated HA Cluster

Operator checklist for creating the validated HA RKE2 cluster from the Rancher UI.

## Pre-Checks

- [ ] Rancher context/environment confirmed (Dev: `virt-infra-dev-buc-hq`, Prod: `virt-infra-prod-buc-hq`)
- [ ] Application credential secret exists: `os-app-cred-<suffix>` with keys `applicationCredentialId` and `applicationCredentialSecret`
- [ ] SSH private key secret exists: `openstack-privatekey` with key `privatekey`
- [ ] CCM network config secret exists: `os-ccm-net-config` with keys `subnetId` and `floatingNetworkId`
- [ ] Local environment ConfigMap exists: `u-<suffix>/rke2-openstack-environment` with keys `authUrl` and `region` (projected by onboarding from the canonical `fleet-default` copy; no `fleet-default` read access is needed)
- [ ] Baseline OpenStack security group `k8s-rke2` exists with required rules (including the NodePort `30000-32767` rule from the tenant subnet for the HA path)
- [ ] Public ingress security group `k8s-rke2-public-ingress` exists for the single-master path

## Validated Defaults

| Setting | Expected Value |
| :--- | :--- |
| Kubernetes version | `v1.35.6+rke2r1` (default) |
| OpenStack CCM image | `registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0` (derived from `v1.35.6+rke2r1`) |
| OpenStack image | `ubuntu-24.04` |
| `secGroups` | `k8s-rke2` |
| `publicIngressSecGroups` | `k8s-rke2-public-ingress` (default; appended only to the master pool when the effective master count is exactly `1` and never attached in HA) |
| `configDrive` | `true` |
| `floatingipPool` | `ext_net_gts` (default; rendered on the master pool only when the effective master count is exactly `1`) |
| `rke2-ingress-nginx` controller | forced by topology: single master disables its Service and schedules the controller on the control-plane master with host ports `80`/`443`, tolerating `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`; HA enables its Service with `type: LoadBalancer` |

- Supported matrix (CCM image is derived from the selected RKE2 version and is not separately configurable): `v1.33.12+rke2r2` -> CCM `v1.33.0`, `v1.34.6+rke2r1` -> CCM `v1.34.0`, `v1.35.6+rke2r1` -> CCM `v1.35.0` (default). Changing the matrix requires a chart release and validation.

## Single vs HA Topology

The chart selects topology from the effective master count (`nodePoolCounts.master`, falling back to the `master` nodepool `quantity`). Only `1` (single master) and `>= 3` (HA) are supported; a master count of exactly `2` is rejected at render time with a clear error.

### Single Master (count = 1)

- The master `OpenstackConfig` renders `floatingipPool` (default `ext_net_gts`) and the node receives a direct floating IP.
- The master `OpenstackConfig` uses `k8s-rke2,k8s-rke2-public-ingress` by default; workers retain only the baseline `k8s-rke2` group.
- Workers never render `floatingipPool`; they stay on the private tenant network (`local-net`).
- The packaged `rke2-ingress-nginx` controller is selected onto the control-plane master, tolerates `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, and exposes host ports `80` and `443` through the floating IP while its Service is forced to `enabled: false`.
- The public ingress security group needs only TCP `80` and `443` from intended client CIDRs.

### HA (count >= 3)

- No node floating IPs are assigned.
- Masters and workers retain only the baseline `k8s-rke2` group; the public ingress group is never attached in HA.
- HA relies on the onboarding-managed static `k8s-rke2` NodePort rule (`30000-32767`) from the tenant subnet. The generated `cloud.conf` sets `manage-security-groups = false`, so the CCM must not create per-LB `lb-sg-*` security groups.
- The packaged `rke2-ingress-nginx` controller Service is forced to `enabled: true` with `type: LoadBalancer`; no single-master host-port, selector, or toleration override is applied.
- The external ingress address is allocated by OpenStack CCM/Octavia from `os-ccm-net-config.floatingNetworkId`. Public `80`/`443` traffic reaches the Octavia floating IP first, then the node NodePorts. Do not add public `6443` and do not alter the baseline or ingress topology behavior.

## UI Path

1. Rancher UI -> Cluster Management -> Clusters -> Create
2. Select the RKE2 cluster template from the template list
3. Fill in the cluster definition using the validated parameters below

## Validated HA Test Parameters

- **Provider/Template**: OpenStack
- **Node Pool Template**: `MultiPool`
- **Control-plane/etcd nodes**: 3
- **Worker nodes**: 1
- **Application credential secret name**: `os-app-cred-<suffix>` (must match the existing secret in the `u-<suffix>` namespace)
- **Advanced settings to verify** (if visible in UI):
   - `secGroups` = `k8s-rke2`
   - `publicIngressSecGroups` = `k8s-rke2-public-ingress` (single master only)
  - `configDrive` = `true`
  - Kubernetes version = `v1.35.6+rke2r1`
  - OpenStack image = `ubuntu-24.04`

## Post-Create Checkpoints

- [ ] Cluster conditions: `Connected=True`, `Provisioned=True`, `Ready=True`, `Updated=True`
- [ ] Machine Deployments: `master 3/3 ready`, `worker 1/1 ready`
- [ ] All 4 Machines show `Running` status with nodeRefs assigned
- [ ] Node roles correct: 3 control-plane/etcd, 1 worker
- [ ] Retain Octavia LB/FIP IDs before cluster deletion; if CCM exits before Service cleanup, remove only the retained test-owned monitors, members, LB, and FIP in that order.

## Troubleshooting Notes

- **Bootstrap stalls**: check whether a node fell back to `DatasourceNone` in cloud-init. If `configDrive` is not set, metadata-service discovery may be inconsistent and nodes can fail to inject the SSH authorized key.
- **Cluster agent not connecting**: distinguish this from cloud-init bootstrap. If nodes are `Running` with nodeRefs but the cluster stays on `waiting for cluster agent to connect`, the issue is agent connectivity (network/Rancher endpoint), not cloud-init bootstrap.
- **Stale Helm release**: if a previous install failed, a stale Helm release secret may block reinstall. Remove it before retrying.
