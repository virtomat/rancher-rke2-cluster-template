# Rancher UI Test Checklist: Validated HA Cluster

Operator checklist for creating the validated HA RKE2 cluster from the Rancher UI.

## Pre-Checks

- [ ] Rancher context/environment confirmed (Dev: `virt-infra-dev-buc-hq`, Prod: `virt-infra-prod-buc-hq`)
- [ ] Application credential secret exists: `os-app-cred-<suffix>` with keys `applicationCredentialId` and `applicationCredentialSecret`
- [ ] SSH private key secret exists: `openstack-privatekey` with key `privatekey`
- [ ] CCM network config secret exists: `os-ccm-net-config` with keys `subnetId` and `floatingNetworkId`
- [ ] Dedicated OpenStack security group `k8s-rke2` exists with required rules

## Validated Defaults

| Setting | Expected Value |
| :--- | :--- |
| Kubernetes version | `v1.33.12+rke2r2` |
| `secGroups` | `k8s-rke2` |
| `configDrive` | `true` |

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
  - `configDrive` = `true`
  - Kubernetes version = `v1.33.12+rke2r2`

## Post-Create Checkpoints

- [ ] Cluster conditions: `Connected=True`, `Provisioned=True`, `Ready=True`, `Updated=True`
- [ ] Machine Deployments: `master 3/3 ready`, `worker 1/1 ready`
- [ ] All 4 Machines show `Running` status with nodeRefs assigned
- [ ] Node roles correct: 3 control-plane/etcd, 1 worker

## Troubleshooting Notes

- **Bootstrap stalls**: check whether a node fell back to `DatasourceNone` in cloud-init. If `configDrive` is not set, metadata-service discovery may be inconsistent and nodes can fail to inject the SSH authorized key.
- **Cluster agent not connecting**: distinguish this from cloud-init bootstrap. If nodes are `Running` with nodeRefs but the cluster stays on `waiting for cluster agent to connect`, the issue is agent connectivity (network/Rancher endpoint), not cloud-init bootstrap.
- **Stale Helm release**: if a previous install failed, a stale Helm release secret may block reinstall. Remove it before retrying.
