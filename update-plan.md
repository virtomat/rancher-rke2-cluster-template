# Rancher RKE2 Cluster Template Update Plan

Goal: improve chart consistency, maintainability, and documentation while preserving Dev deployability first; later prepare and track Prod-specific adaptation.

## Working Model

- `dev`: shared cleanup and Dev-validated improvements
- `main`: shared baseline first, Prod-specific patches later
- This file is intended to be kept on both branches and to track work affecting both environments.
- Shared generic fixes should remain small and cherry-pickable between branches.

## Current Status

- Phase: Traefik Gateway baseline and `1.1.0` documentation/examples implemented; offline verification and default-pin live acceptance completed, while the full patch matrix and Rancher UI path remain open
- Current baseline: chart `1.1.0` with RKE2 `v1.33.13+rke2r2`, `v1.34.12+rke2r1`, and `v1.35.9+rke2r1` (default)
- Current validation target: Dev. Live acceptance covers the Gateway baseline and TLS on default `v1.35.9+rke2r1` for single-node and 3CP+2W HA; `v1.33.13+rke2r2` and `v1.34.12+rke2r1` remain offline-render-only
- Branch split status: `dev` branch; no existing cluster upgrade or migration is part of this baseline
- Release status: `1.1.0` is an unreleased source baseline; no tag, artifact publication, or Git commit/push is implied by the live acceptance

## Progress

- [x] Create `dev` branch from current `main`
- [x] Add a shared `update-plan.md` tracker for both branches
- [x] Add a README status note and maintained-files index
- [x] Align current documentation with the Traefik Gateway baseline and patch matrix
- [ ] Fix `values.yaml`, `questions.yaml`, and `templates/` mismatches
- [ ] Validate generic cleanup in Dev
- [x] Run default-pin Gateway/TLS live acceptance for single-node and 3CP+2W HA with qualified availability
- [ ] Run live coverage for the remaining `v1.33.13+rke2r2` and `v1.34.12+rke2r1` pins
- [ ] Merge shared cleanup baseline into `main`
- [ ] Start Prod-specific adaptation on `main`

## Scope

### In Scope Now

- documentation cleanup
- chart consistency fixes
- generic template and schema fixes
- Dev validation of shared improvements

### Out Of Scope For Now

- Prod-only defaults
- Prod-only network, storage, image, or flavor changes
- intentional branch-specific divergence

## Known Issues And Findings

- `README.md`, `values.yaml`, and `questions.yaml` currently contain inconsistent defaults.
- Top-level documentation and chart metadata are not fully aligned.
- Some addon question paths appear misaligned with the values consumed by templates.
- Some documentation and troubleshooting content is environment-specific or stale.
- Secret key naming is not fully consistent between documentation and templates.

## Cleanup Phase Analysis Snapshot

This section preserves the current cleanup analysis so work can resume in a later session without rediscovering the same context.

### Confirmed Direction

- Work continues on `dev` first.
- Cleanup is generic and Dev-validated.
- Prod-specific patches come later, after the cleaned shared baseline is merged to `main`.
- Avoid environment-specific behavior changes during this phase unless they are only documentation notes.
- Prefer shrinking and clarifying the chart before adding new behavior.

### Current Cleanup Goals

- Remove stale or unrelated content.
- Fix mismatches between `values.yaml`, `questions.yaml`, and templates.
- Keep only the Rancher/OpenStack/RKE2 paths we actively support.
- Improve documentation enough that another session can continue safely.
- Define a repeatable chart validation procedure before Prod-specific patches.

## Cleanup Findings

### Safe Removal Candidates

- `systemprompt.md`
  - Confirmed unrelated to this Helm chart (no functional references found).
  - Removed.
- `questions.yaml`: `masternode.extraConfigs`
  - UI-only visibility toggle.
  - Does not affect rendered templates.
  - Candidate for removal or simplification.
- `questions.yaml`: `workernode.extraConfigs`
  - UI-only visibility toggle.
  - Does not affect rendered templates.
  - Candidate for removal or simplification.

### Confirm Before Removing Or Moving

- `CHANGELOG.md`
  - Contains historical release notes and old forge links.
  - Version history does not match current `Chart.yaml`.
  - Decision needed: keep, reset, or replace with `update-plan.md` history.
- `troubleshooting/security-group-tuning.md`
  - Contains useful operational knowledge.
  - Also contains environment-specific examples.
  - Decision needed: keep as internal troubleshooting, move, or trim into generic guidance.
- README NodeDriver manifest
  - Current example includes generated Kubernetes noise like `managedFields`.
  - Should be reduced to minimal useful guidance or replaced by UI/API notes.
- `templates/cloud-config.tpl`
  - Thin wrapper around `files/cloud.conf`.
  - Keep for now if templating is expected to grow.
  - Simplify later if it remains only a wrapper.
- `templates/openstack-ccm-manifest.tpl`
  - Thin wrapper around `files/openstack-ccm-manifest.yaml`.
  - Keep for now if templating is expected to grow.
  - Simplify later if it remains only a wrapper.

### Concrete Bugs And Mismatches

- `templates/managedcharts.yaml`
  - Uses literal `namespace: $namespace`.
  - Should render the namespace variable.
  - This is a real template bug.
- `templates/clusterroletemplatebinding.yaml`
  - Calls the namespace helper inside a `range` with the wrong context.
  - Likely needs root context passed explicitly.
- Addon question paths are misaligned.
  - `questions.yaml` writes to `monitoring.version`.
  - Templates read `addons.monitoring.version`.
- `localClusterAuthEndpoint` question paths are misaligned.
  - Questions use paths without the `cluster.config.` prefix.
  - Templates use `cluster.config.localClusterAuthEndpoint.*`.
- `cluster.config.openstack.enabled`
  - Present in `questions.yaml`.
  - Not consumed by templates.
  - Candidate for removal unless behavior is implemented behind it.
- Worker OpenStack advanced questions appear incorrectly gated.
  - Worker section uses `nodePoolTemplate=SinglePool`.
  - Likely should be `MultiPool`, or the section should be simplified.
- Default drift exists between `values.yaml` and `questions.yaml`.
   - Kubernetes version, OpenStack authentication source, and image default were aligned at `v1.35.6+rke2r1`, the platform ConfigMap, and `ubuntu-24.04`.
   - Flavor defaults use the parity catalog: master=`c1.medium`, worker=`s1.medium`.
- README secret examples needed alignment.
  - `privateKeyFile` in docs did not match current template lookup of `privatekey`.
  - This has started being corrected in README.

## Cleanup Backlog

### P0: Fix Real Chart Bugs

- [x] Fix `templates/managedcharts.yaml` namespace rendering.
- [x] Fix `templates/clusterroletemplatebinding.yaml` root context handling.
- [x] Align addon question paths with `addons.*`.
- [x] Align `localClusterAuthEndpoint.*` question paths with values/templates.
- [x] Resolve defaults drift between `values.yaml` and `questions.yaml`.

### P1: Shrink Rancher UI Surface

- [ ] Remove or justify `cluster.config.openstack.enabled`.
- [ ] Remove or simplify `masternode.extraConfigs`.
- [ ] Remove or simplify `workernode.extraConfigs`.
- [ ] Review advanced OpenStack pass-through fields and keep only fields we actively support.
- [ ] Fix or remove incorrectly gated worker OpenStack advanced fields.

### P2: Documentation Cleanup

- [ ] Trim README NodeDriver manifest to minimal guidance.
- [ ] Decide what to do with `CHANGELOG.md`.
- [ ] Decide what to do with `troubleshooting/security-group-tuning.md`.
- [x] Remove `systemprompt.md` (confirmed unrelated, removed).
- [ ] Keep README focused on usage, prerequisites, and links to deeper notes.

### P3: Validation Procedure

- [ ] Define `helm lint` procedure.
- [ ] Define `helm template` procedure for `SinglePool`.
- [ ] Define `helm template` procedure for `MultiPool`.
- [ ] Define Rancher UI question wiring checks.
- [ ] Define read-only Rancher management namespace inspection.
- [ ] Validate expected secret and namespace shape in Dev before Prod-specific changes.

## Environment Notes

### Dev

- Keep deployability intact during shared cleanup.
- Use Dev as the validation target for generic improvements.
- Dev Rancher is deployed in Kubernetes context `virt-infra-dev-buc-hq`.
- Dev Rancher management namespaces such as `cattle-system`, `fleet-default`, `cattle-global-data`, and user namespaces like `u-<user-suffix>` should be inspected in `virt-infra-dev-buc-hq`.

### Prod

- Prod-specific changes start only after the shared baseline is cleaned up and merged.
- Known likely differences include external network settings, flavors, images, and possibly storage-related behavior.
- Prod Rancher is deployed in Kubernetes context `virt-infra-prod-buc-hq`.
- Prod Rancher management namespaces such as `cattle-system`, `fleet-default`, `cattle-global-data`, and user namespaces in the derived `u-<suffix>` form are expected in `virt-infra-prod-buc-hq`.
- Prod-specific validation and patches start only after the shared baseline is cleaned up and validated in Dev.
- The shared `c1.*`, `s1.*`, and `m1.*` workload flavors have zero local disk. Node pools must therefore boot from a 40 GiB Cinder volume; leave `volumeType` empty so each environment selects its own Cinder default.

## Dev Inspection Findings

- Active Dev context verified: `virt-infra-dev-buc-hq`.
- Rancher management namespaces present: `cattle-system`, `fleet-default`, `cattle-global-data`, and the derived user namespace.
- Rancher pods observed ready in `cattle-system`: `rancher`, `rancher-webhook`.
- OpenStack NodeDriver is active.
- Existing user namespace secret names and key names only:
  - `os-app-cred-<suffix>`: `applicationCredentialId`, `applicationCredentialSecret`
  - `openstack-privatekey`: `privatekey`
  - `os-ccm-net-config`: `subnetId`, `floatingNetworkId`
- `test-cloud-config-f0ace93f` appears to be old chart-rendered output owned by Helm release `rke2-cluster-templates-1-1772183441` for cluster `test`; do not delete until confirmed unused.
- Existing chart Helm releases are in `fleet-default`.

## First Live Helm Test Plan

- First live target is single-node RKE2, not k3s.
- Use a live Helm install after confirming the input secrets exist in Dev.
- `nodepools[0].quantity=1` is already the default and does not need to be set for the first minimal command.
- `defaultPrivateKeyFileSecretName=openstack-privatekey` and `ccmNetConfigSecretName=os-ccm-net-config` are already defaults and do not need to be set unless testing overrides.
- `os-ccm-net-config` is an input secret used to render `<cluster-name>-cloud-config-<suffix>`, not the Rancher cloud credential secret and not generated by the chart.
- Minimal intended live command:

```bash
helm upgrade --install dev-rke2-single . \
  -n fleet-default \
  --set cluster.name=dev-rke2-single \
  --set configMode=Simple \
  --set nodePoolTemplate=SinglePool \
  --set cluster.config.openstack.applicationCredentialSecretName=os-app-cred-<suffix>
```

## First Live Helm Test Result

- Context used: `virt-infra-dev-buc-hq`.
- Helm release `dev-rke2-single` was installed successfully into `fleet-default`.
- Helm release state after install: `deployed`, revision `1`.
- Created Rancher provisioning cluster:
  - `u-<suffix>/dev-rke2-single`
  - version `v1.30.4+rke2r1`
  - `READY` was still empty immediately after install, so provisioning was still in progress.
- Created OpenStack machine configs:
  - `u-e3r4hflh6x/dev-rke2-single-master`
  - `u-e3r4hflh6x/dev-rke2-single-worker`
- Created/generated user-namespace secrets included:
  - `dev-rke2-single-cloud-config-108ee65f`
  - `dev-rke2-single-master-cg2sf-nhcs8-machine-bootstrap`
  - `dev-rke2-single-master-cg2sf-nhcs8-machine-bootstrap-token4jcj8`
  - `dev-rke2-single-master-cg2sf-nhcs8-machine-plan`
  - `dev-rke2-single-rke-state`
- Observation: even with `nodePoolTemplate=SinglePool`, the chart still rendered both master and worker `OpenstackConfig` objects, while the Rancher `Cluster` used the single master pool.
- Follow-up fix applied on `dev`: `templates/nodeconfig-openstack.yaml` now matches the `cluster.yaml` `SinglePool` / `MultiPool` gate so `SinglePool` renders only the first `OpenstackConfig`.
- Render validation after the fix:
  - `SinglePool`: 1 `OpenstackConfig`
  - `MultiPool`: 2 `OpenstackConfig`
- Runtime investigation after the cluster briefly became `Active` and then returned to `Updating`:
  - Rancher shows `Provisioned=True` but `Connected=False` and `Ready=False` with `Cluster agent is not connected`.
  - Management-plane logs report inability to connect to the workload cluster Kubernetes API and repeated probe waits.
  - The backing OpenStack VM is `ACTIVE`, `cloud-init` completed, and `rancher-system-agent` started successfully.
  - The instance only has the project `default` security group attached.
  - SSH to the floating IP from this workstation timed out.
  - Current working hypothesis: security-group reachability to the bootstrap/control-plane node is insufficient for stable workload API and agent connectivity.
  - Important limitation: node-level `rke2-server` logs could not yet be inspected because SSH access to the VM is currently blocked.
- Validated chart prerequisite from the first Dev runtime test:
  - a dedicated OpenStack security group should be treated as a chart/environment prerequisite
  - recommended name: `k8s-rke2`
  - the chart can attach this group through `cluster.config.openstack.secGroups`, but it cannot create the OpenStack SG or its rules
- Dev follow-up applied after documenting the prerequisite:
  - created OpenStack SG `k8s-rke2` in the Dev project
  - added a simplified baseline SG model for the single-node bootstrap path: all ingress from `k8s-rke2`, plus permissive Dev/debug access on `22` and `6443`
  - uninstalled and recreated `dev-rke2-single` with `cluster.config.openstack.secGroups=k8s-rke2`
  - initial post-recreate state was early provisioning with `waiting for viable init node`
  - follow-up verification reached a healthy state: `Provisioned=True`, `Connected=True`, `Ready=True`
  - the recreated node is attached to SG `k8s-rke2`
  - SSH reachability improved to the authentication stage, confirming the security-group change fixed basic network reachability
  - remaining SSH issue is key/auth related (`Permission denied (publickey)`), not floating-IP reachability
  - corrected scope after review: the successful single-node test did not depend on Octavia because bootstrap used a direct floating IP on the node
  - the later ingress / `Service type=LoadBalancer` path is where OpenStack CCM and Octavia-specific NodePort/backend reachability becomes relevant
- Chart default alignment applied after the first Dev validation:
  - changed `values.yaml` default `cluster.config.openstack.secGroups` from `default` to `k8s-rke2`
  - changed `questions.yaml` default for `cluster.config.openstack.secGroups` from `default` to `k8s-rke2`
  - updated `README.md` to describe `cluster.config.openstack.secGroups=k8s-rke2` as the default chart value
- Multi-pool Dev validation started with a temporary override file instead of `--set nodepools[0].quantity=...`:
  - Helm CLI list-index overrides collapse the `nodepools[]` entries in this chart and drop required sibling fields such as `openstackconfig`
  - current test target is `3` control-plane/etcd nodes plus `1` worker node
  - installed release `dev-rke2-multipool` in `fleet-default`
  - Rancher created `2` machine deployments and `4` machine objects in namespace `u-e3r4hflh6x`
  - generated `OpenstackConfig` resources inherit `secGroups: k8s-rke2`
  - generated `OpenstackConfig` resources currently have `floatingipPool: ""` for both pools
  - initial provisioning state was `configuring bootstrap node(s) ... waiting for probes: calico, kube-apiserver, kube-controller-manager, kube-scheduler`
  - follow-up state advanced to `waiting for cluster agent to connect`
  - final Rancher state reached `Provisioned=True`, `Connected=True`, `Ready=True`
  - final live MachineDeployment state is `master 3/3 ready`, `worker 1/1 ready`
  - final live Machine state is `4` machines `Running`
  - the generated kubeconfig secret exists, but from this workstation it targets a Rancher-proxied endpoint that is not directly reachable here (`https://10.152.183.154/k8s/clusters/c-m-697wbhf6`)
- Multi-pool chart cleanup after the first successful HA test:
  - added scalar Helm-friendly overrides `nodePoolCounts.master` and `nodePoolCounts.worker`
  - chart templates now prefer `nodePoolCounts.*` for rendered quantities and fall back to `nodepools[].quantity`
  - Rancher questions now use `nodePoolCounts.master` and `nodePoolCounts.worker` for node counts instead of direct list-index quantity edits
  - corrected the `MultiPool` question text to remove the stale `Not yet supported` wording
  - corrected worker OpenStack advanced subquestion gating so those fields are available in `MultiPool`
- Kubernetes version default alignment after Rancher inspection:
  - Rancher currently advertises `rke2-default-version=1.33.12+rke2r2`
  - chart default `cluster.config.kubernetesVersion` is now `v1.35.6+rke2r1`
  - Rancher questions default is now `v1.35.6+rke2r1`
  - old `v1.26` through `v1.30` options were removed from the Rancher UI version list
- Multi-version RKE2/OpenStack CCM compatibility matrix after user decision:
  - the chart supports exactly three tested RKE2 releases: `v1.33.12+rke2r2`, `v1.34.6+rke2r1`, and `v1.35.6+rke2r1` (default)
  - RKE2 `1.31` and `1.32` are no longer offered
  - the OpenStack CCM image is derived automatically from the selected version (`v1.33.0`, `v1.34.0`, `v1.35.0` respectively) via a helper and is not user configurable
  - `values.schema.json` restricts `cluster.config.kubernetesVersion` to exactly the matrix; changing the matrix requires a chart release and validation
- Topology-aware floating-IP and ingress handling (replaces the interim all-FIP removal):
  - the original live Dev failure happened because Rancher attempted to allocate a bootstrap floating IP from the `ext_net_gts` pool for a multi-master (HA) cluster
  - effective master count is resolved by a new `rancher-cluster-templates.masterCount` helper: `nodePoolCounts.master` when non-empty/non-zero, else the `master` nodepool `quantity`; a count of exactly `2` fails rendering with a clear message, and any count other than `1` or `>= 3` is rejected
  - single master (count `1`): the master `OpenstackConfig` renders `floatingipPool` (default `ext_net_gts`) so the node gets a direct floating IP; the packaged `rke2-ingress-nginx` controller Service is forced to `enabled: false`, while the controller is selected onto the control-plane master, tolerates `node-role.kubernetes.io/control-plane:NoSchedule` and `node-role.kubernetes.io/etcd:NoExecute`, and serves host ports `80` and `443` via the node floating IP
  - HA (count `>= 3`): no node floating IPs; the packaged `rke2-ingress-nginx` controller Service is forced to `enabled: true` with `type: LoadBalancer` and has no single-master host-port, selector, or toleration override; external addresses are allocated by OpenStack CCM/Octavia from `os-ccm-net-config` (`floatingNetworkId`)
   - workers never render `floatingipPool`; they stay on the private tenant network (`local-net`)
   - `cluster.config.openstack.floatingipPool` (default `ext_net_gts`) and its Rancher question are restored as the single-master node floating-IP network
    - baseline `cluster.config.openstack.secGroups` remains attached to all node pools; `cluster.config.openstack.publicIngressSecGroups` (default `k8s-rke2-public-ingress`) is appended only to a single master and permits only TCP `80` and `443` publicly
    - CCM `floatingNetworkId` and `cloud.conf` were unchanged by the topology work; `manage-security-groups` was later set to `false` under the 2026-08-17 HA security-group contract
   - Dev 3-master/1-worker revalidation with `manage-security-groups=false` succeeded: all nodes used only the baseline group, the worker alone was an ONLINE Octavia backend, public HTTP/HTTPS returned ingress `404`, and no tenant `lb-sg-*` group was created. Helm cluster deletion still left the Octavia LB and FIP after CCM exited, so test cleanup explicitly removed their monitors, members, LB, and FIP.
- OpenStack config-drive validation after direct third-master investigation:
  - a stuck third master in the HA test fell back to `DatasourceNone`, did not inject the `ubuntu` authorized key, and never reached `rancher-system-agent` startup
  - a ready master from the same cluster used `DatasourceOpenStackLocal [net,ver=2]`, injected the authorized key, and completed bootstrap normally
  - Dev revalidation with `nodepools[0].openstackconfig.configDrive=true` and `nodepools[1].openstackconfig.configDrive=true` eliminated the original third-master bootstrap failure
  - the failure mode changed from a cloud-init/bootstrap miss on the third master to a later separate issue: `waiting for cluster agent to connect`
  - based on that validation, `configDrive` should be promoted to the chart default for OpenStack node configs
- Fresh clean redeploy outcome after full cleanup of the previous failed cluster:
  - the previous failed cluster was cleaned up cleanly
  - a stale Helm release secret had to be removed before the reinstall could succeed
  - fresh `dev-rke2-multipool` redeploy from improved chart defaults succeeded
  - generated `OpenstackConfig` resources had `secGroups: k8s-rke2` and `configDrive: true`
  - final Rancher cluster state reached `Connected=True`, `Provisioned=True`, `Ready=True`, `Updated=True`
  - all 4 Machines were `Running` with nodeRefs
  - no temporary floating IP was needed on the final successful run
  - this strongly validates promoting `configDrive` to the chart default for OpenStack node configs

## Draft Validation Procedure

### Static Chart Checks

- Run `helm lint`.
- Run the offline Cinder CSI contract test: `python3 tests/validate-cinder-csi.py` (requires `helm` and Python 3 with PyYAML). It renders the real chart from a temporary copy with synthetic `lookup` fixtures only; production templates stay fail-closed.
- Run the offline Gateway contract test: `python3 tests/validate-gateway.py --require-packaged-charts` (requires `helm` and Python 3 with PyYAML). Set `RKE2_TRAEFIK_CHART_DIR` to the optional offline package cache; the packages are not vendored and the test does not download them.
- Render with default values.
- Render with `nodePoolTemplate=SinglePool`.
- Render with `nodePoolTemplate=MultiPool`.
- Inspect rendered `Cluster`, `OpenstackConfig`, cloud config Secret, ManagedCharts, and ClusterRoleTemplateBinding resources.

### Rancher UI Checks

- Verify `questions.yaml` writes values to paths consumed by templates.
- Verify addon values land under `addons.*`.
- Verify hidden and advanced fields are only present where they make sense.
- Verify defaults match `values.yaml`.

### Live Read-Only Rancher Checks

- Confirm current context before any inspection.
- For Dev, expected context is `virt-infra-dev-buc-hq`.
- For Prod, expected context is `virt-infra-prod-buc-hq`.
- List namespaces matching `cattle-*`, `fleet-*`, and `u-*`.
- Inspect existence of expected namespaces such as `fleet-default`, `cattle-global-data`, and known `u-*` user namespaces.
- Inspect Secret names and key names only, not secret values.
- Compare actual secret naming with chart helper logic.

## Environment Validation Order

1. Static chart validation from the repo.
2. Read-only Rancher namespace and secret-shape inspection in Dev using `virt-infra-dev-buc-hq`.
3. Dev install or upgrade validation.
4. Merge cleaned shared baseline toward `main`.
5. Read-only Rancher namespace and secret-shape inspection in Prod using `virt-infra-prod-buc-hq`.
6. Prod-specific patch series on `main`.

## Cinder CSI Bootstrap Add-On (New Clusters)

- Accepted scope: new clusters bootstrapped from the template install the OpenStack Cinder CSI driver through `additionalManifest` after the CCM manifest. The chart cannot distinguish a new install from an existing release, so this add-on is not validated by upgrading an existing release; existing clusters are not deployed or upgraded by this task.
- Images: driver and sidecars are pinned by the existing three-version RKE2 matrix, with no user image input.
- Storage: exactly `cinder-delete` (`Delete`, sole default) and `cinder-retain` (`Retain`, non-default). Both use `WaitForFirstConsumer`, enable expansion, default to ext4 through the provisioner, use the Cinder environment default volume type, and select the availability zone through CSI topology instead of a hardcoded AZ.
- Credentials: the existing per-user application credential is reused through the node `/etc/rancher/rke2/cloud.conf`, mounted read-only as a single file. No new credential inputs, Secrets, or embedded auth are added.
- Limits: plain filesystem RWO only; no snapshot support and no shared RWX.
- Topology: the shared `cloud.conf` `ignore-volume-az = true` does not by itself reconcile Nova/Cinder availability zones. Upstream defaults request the node topology AZ, so validate AZ compatibility before acceptance and design separate availability configuration for mismatched zones rather than disabling the check blindly.
- Status: offline contract verification passed (3 RKE2 versions x 1/3 masters plus unsupported-version negatives). Live acceptance was also run on 2026-11-06 in Dev on a newly provisioned default `v1.35.6+rke2r1` cluster with one control-plane and two workers; storage-class admission defaulting, WaitForFirstConsumer binding, data integrity, cross-worker detach/reattach, online expansion, `Delete`, and `Retain` all behaved as specified (details in the 2026-11-06 change-log entry). The cluster and retained volume were left for inspection after the run and were then cleaned up under separate explicit authorization on 2026-11-06 (see the change-log entry). HA and the `v1.33`/`v1.34` rows remain offline-render-only, so this is not a full production-ready claim.

## Gateway API Ingress Baseline (Chart 1.1.0, New Clusters)

- Scope: new clusters only. Do not upgrade or migrate an existing NGINX or other ingress path to this baseline as part of this work.
- Controller: the chart forces `ingress-controller: [traefik]`; RKE2 auto-disables the unselected packaged NGINX controller. The packaged `rke2-traefik` chart owns GatewayClass `traefik`, Gateway `kube-system/shared-gateway`, the Traefik workload, and its Service. No Gateway or GatewayClass is embedded in `additionalManifest`.
- Default listener: `web` HTTP on packaged port `8000`, published externally as `80`, with namespace opt-in selector `gateway-access: public`. External `443` and the `websecure` entrypoint are published/allocated, but no HTTPS listener, Certificate, Secret, issuer, or `certificateRefs` is configured by default. Global websecure TLS is disabled; TLS is per listener.
- Topology: single master pins the Traefik DaemonSet to Linux control-plane nodes with control-plane/etcd tolerations, host ports `80`/`443`, and a `ClusterIP` Service reached through the master floating IP. HA keeps one DaemonSet, clears host ports, and uses one `LoadBalancer` Service served by CCM/Octavia. Gateway status is empty in host-port mode and HA copies the LoadBalancer status; DNS against the master floating IP stays manual, with no custom discovery or ExternalDNS controller.
- Security contract: unchanged. The HA `manage-security-groups = false` contract, onboarding-managed `k8s-rke2` NodePort rule, `lb-sg-*` prohibition, never attached in HA public ingress group, and no public `6443` rules remain authoritative.
- TLS onboarding: documented in `docs/gateway-api.md` with non-secret examples in `examples/gateway/`. The application owns `HTTPRoute`, per-domain `Certificate`, cert-manager TLS Secret, and narrow `ReferenceGrant`; the administrator owns Gateway listeners, namespace opt-in, cert-manager installation/configuration, and issuers.
- cert-manager: not installed by the template. A compatible pinned cert-manager is an integration prerequisite. For new installs, use a verified patch from the current 1.21 line (1.21 supports Kubernetes 1.33-1.36; 1.20 supports 1.32-1.35). The exact patch pin is an administrator choice and is not invented here.
- Gateway CRDs: must exist before cert-manager starts. The packaged Traefik CRD bundle supplies them for new clusters. RKE2 installs the packaged Traefik main and CRD HelmCharts asynchronously with no explicit dependency; the initial Traefik Helm job may retry until the Gateway API CRDs are established. Persistent failure requires HelmChart/job/event inspection, not automatic deletes/restarts/uninstalls/custom repair or a cert-manager restart.
- Verification: independent offline verification completed on 2026-11-06 (Gateway 399 checks, CSI 1379 checks, static shell PASS). These are local render/static results only; live routing, HTTPS/ACME issuance, fresh-bootstrap CRD convergence, and new-patch CSI acceptance remain live gates. Existing Cinder live acceptance remains historical and used `v1.35.6+rke2r1`.

## Planned Phases

1. Documentation baseline
2. `values.yaml`, `questions.yaml`, and `templates/` consistency fixes
3. Generic template cleanup
4. Dev validation
5. Merge shared cleanup baseline into `main`
6. Prod-specific patch series on `main`

## Change Log For This Effort

### 2026-06-29

- Captured the initial shared cleanup and adaptation plan.
- Added this file as the long-running roadmap and progress tracker.
- Added a top-level README note pointing maintainers to the files that will be kept in sync during this work.
- Bootstrapped `dev` from `main` and restored the in-progress documentation changes onto `dev`.
- Tightened the README provider, secret, install, and reference sections to better match current chart behavior.

### 2026-06-30

- Expanded the cleanup analysis snapshot and backlog so the work can be restarted in a later session.
- Captured Dev and Prod Rancher management contexts for future read-only namespace and secret-shape validation.
- Documented the Dev inspection results and the initial live Helm test command for a single-node RKE2 install.
- Documented the chart's technical flow, input secrets, and generated outputs in the README.
- Completed the first live Dev Helm install for `dev-rke2-single` and recorded the immediate Rancher resources created by the chart.
- Applied the first template cleanup fix: `SinglePool` no longer renders an unused worker `OpenstackConfig`, while `MultiPool` still renders both pools.
- Investigated the first runtime regression after `Active -> Updating`; current evidence points to bootstrap/control-plane reachability problems, likely related to the attached OpenStack security group.
- Documented the dedicated `k8s-rke2` security group as a validated prerequisite and clarified that default-SG changes are Dev/debug-only workarounds.
- Created the dedicated Dev security group `k8s-rke2`, recreated the first test cluster against it, and captured the second test starting state.
- Verified that recreating the test cluster with SG `k8s-rke2` resolved the earlier connectivity problem and produced a healthy Rancher cluster in Dev.
- Aligned flavor defaults across `values.yaml` and `questions.yaml`:
  - control-plane (master) default: `c1.medium`
  - worker default: `s1.medium`
  - `questions.yaml` options are `c1.small`, `c1.medium`, `c1.large` for master and `s1.small`, `s1.medium`, `s1.large` for worker
  - the public Dev workload flavor catalog now matches Prod for these selections
- Hardened OpenStack credential validation so missing `applicationCredentialSecretName` now fails with an explicit Helm error instead of a nil/lookup template crash during Rancher UI submission.

### 2026-08-16

- Migrated the `rke2-openstack-environment` chart lookup to the derived user
  namespace: the chart now consumes only `u-<suffix>/rke2-openstack-environment`
  (projected by onboarding from the canonical `fleet-default` source) and no
  longer looks up `fleet-default`. All normal user Helm lookups are local; no
  user `fleet-default` read access is required.
- Fresh-user test condition: user `u-dnaaco4azl` can read local `u-dnaaco4azl`
  objects (Secrets and `rke2-openstack-environment`) but cannot read the
  `fleet-default` ConfigMap; a server-backed render as that user must succeed
  using only the local ConfigMap.

### 2026-08-17

- HA security-group contract with onboarding-managed static rules (user decision
  `manage-security-groups=false`):
  - the generated `cloud.conf` now sets `manage-security-groups = false`; the CCM must not
    create per-LB `lb-sg-*` security groups.
  - HA relies on the onboarding-managed static `k8s-rke2` NodePort rule (`30000-32767`) from
    the tenant subnet for Octavia amphora-to-member reachability.
  - the public ingress group (`k8s-rke2-public-ingress`) is never attached in HA; it remains
    single-master only.
  - public `80`/`443` traffic reaches the Octavia floating IP first, then the node NodePorts.
  - do not add public `6443` and do not alter the baseline or ingress topology behavior.

### 2026-11-06

- Added the OpenStack Cinder CSI bootstrap for new clusters: version-derived image bundle, CSIDriver, controller Deployment, node DaemonSet, prefixed RBAC, and `cinder-delete`/`cinder-retain` StorageClasses appended to `additionalManifest` after the CCM manifest.
- Reused the existing per-user application credential through a read-only `/etc/rancher/rke2/cloud.conf` file mount; no new credential inputs or embedded Secrets.
- Recorded the scope boundary: new clusters only, and existing releases must not be upgraded to validate this add-on.
- Recorded the topology caveat: `ignore-volume-az=true` does not resolve Nova/Cinder availability-zone mismatches; validate AZ compatibility before acceptance.
- Offline verification: an independent verifier authored `tests/validate-cinder-csi.py`; `python3 tests/validate-cinder-csi.py` passed (6 renders across 3 RKE2 versions x 1/3 masters, plus unsupported-version schema/helper negatives), and `bash tests/validate-openstack-environment.sh` passed. No real cluster or Helm management-cluster lookup was used. Tool versions observed during verification: Helm 4.3.1, Python 3.10.12, PyYAML 6.0.1.
- Live acceptance ran on 2026-11-06 in Dev from local chart HEAD `f6a28ad` plus the uncommitted CSI work (chart `1.0.5`, Helm revision `1`, installed 16:37Z, cluster ready 17:01Z, test stages 17:08-17:22Z). The new cluster used default RKE2 `v1.35.6+rke2r1` with CSI `v1.35.0` and pinned sidecars, one control-plane node and two workers.
- Observed results: both StorageClasses correct; a claim omitting `storageClassName` was defaulted to `cinder-delete` at admission, stayed `Pending` under WaitForFirstConsumer until a consumer was scheduled, then bound; consistent PV/PVC/Cinder identity, capacity, type, AZ, and attachment; marker plus 1 MiB write/re-read with matching SHA-256 on both 1 GiB claims (`rbd1`, `nova`, ext4, RWO); graceful worker A -> worker B move with detach/reattach of the same volumes and intact hashes; online 1Gi -> 2Gi expansion in about 11.8s with the same Pod UID, zero restarts, 2 GiB claim/PV/volume, and filesystem growth from 996780 to 2028392 KiB (a 1.2 GiB write also passed, temp file removed); `Delete` removed PVC, PV, and Cinder volume (404 verified twice) in about 5s; `Retain` left the PVC gone, the PV `Released`, and a 1 GiB Cinder volume `available` with no attachments, observed twice over more than 30s.
- Final independent GET-only verification: 3 Ready nodes, CSI controller `1/1`, node DaemonSet `3/3`, 3 `CSINode` objects, 3 Nova servers `ACTIVE` with three 40 GiB boot volumes plus the retained 1 GiB volume (4 volumes, 121 GiB total), and no leftover test Pods, PVCs, or VolumeAttachments.
- Scope limits: no live HA and no `v1.33`/`v1.34` runs, so those remain offline-render-only. The run used operator Helm management access but the tenant application credential for provisioning, CSI, and OpenStack cross-checks, and did not test Rancher UI RBAC or password login.
- The cluster and retained PV/volume were intentionally left for inspection at that point; no cleanup was performed during acceptance and PV finalizers were not mutated. Cleanup followed separately the same day.
- Cleanup completed on 2026-11-06 under separate explicit authorization: the `Retain` PV was deleted normally (404 at 17:41:24; controllers cleared finalizers with no override), the retained Cinder volume was deleted by exact ID (404 at 17:41:42), and the test namespace was gone at 17:42:01; one `helm uninstall` of the test release in `fleet-default` (with `--wait --timeout 20m`) exited `0` at 17:45:30 and the Rancher CAPI cascade finished at 17:46:21; all three Nova servers, boot volumes, floating IP, VM ports, and test-owned management CAPI/Fleet/cloud-config/kubeconfig objects were removed automatically, with no manual cluster-orphan fallback and no PV finalizer stripping.
- Independent GET-only cleanup verification passed: Helm release and provisioning/management clusters absent; all five Cinder volume IDs, three Nova servers, floating IP, and VM ports 404; tenant has 0 servers, 0 volumes, and 0 floating IPs; shared user namespace, onboarding Secrets, environment ConfigMap, bootstrap keypair, and tenant/external networks, subnet, and security groups were preserved.

#### Gateway API Baseline And 1.1.0 Documentation (2026-11-06)

- Advanced the supported RKE2 matrix to `v1.33.13+rke2r2`, `v1.34.12+rke2r1`, and `v1.35.9+rke2r1` (default). The latest live Rancher observed for this workspace is 2.14.3, whose official support matrix covers Kubernetes 1.33-1.35 only; no 1.36/1.37 offer or upgrade was added.
- Replaced the legacy ingress contract with the packaged `rke2-traefik` Gateway baseline: forced `ingress-controller: [traefik]`, disabled legacy Ingress/NGINX compatibility/native Traefik CRD providers and the unused IngressClass, and kept one GatewayClass `traefik` plus Gateway `kube-system/shared-gateway` owned by the packaged chart rather than `additionalManifest`.
- Default `web` listener is HTTP on packaged port `8000`, published externally as `80`, with namespace opt-in `gateway-access: public`. External `443`/`websecure` remain published/allocated, but no HTTPS listener, Certificate, Secret, issuer, or `certificateRefs` is installed by default; global websecure TLS is disabled and TLS is per listener.
- Single master keeps the Traefik DaemonSet on Linux control-plane nodes with host ports `80`/`443`, a `ClusterIP` Service reached through the master floating IP, and the existing public ingress group. HA clears host ports and uses one `LoadBalancer` Service served by CCM/Octavia. Gateway status stays empty in host-port mode and HA copies the LoadBalancer status; DNS remains manual with no custom discovery or ExternalDNS controller.
- Security contract unchanged: `manage-security-groups = false`, onboarding-managed static `k8s-rke2` NodePort rule, no per-LB `lb-sg-*`, public ingress group never attached in HA, and no public `6443`.
- Added `docs/gateway-api.md` and non-secret `examples/gateway/` covering administrator/application ownership, per-domain cert-manager Certificates, staging-first issuance, narrow cross-namespace ReferenceGrant (`v1beta1` because the packaged Gateway API bundles serve both v1 and v1beta1), HTTP-01 via the shared `web` listener, and listener merge into Rancher `Cluster` chartValues. The template does not install cert-manager, issuers, domains, emails, or DNS credentials.
- cert-manager integration is documented as an administrator prerequisite. The verified current 1.21 chart enables Gateway API with `config.gatewayAPI.enabled: true` and CRDs with `crds.enabled: true` (not the earlier `config.enableGatewayAPI` claim). New installs should use a verified pinned 1.21 patch; Gateway CRDs must exist before cert-manager starts, with no restart workaround.
- Bumped source `Chart.yaml` from `1.0.5` to `1.1.0`; README, checklist, and update plan now carry `1.1.0` and the three new pins. This is an unreleased source baseline with no tag, CI, or publication implied.
- Independent offline verification completed on 2026-11-06: `python3 tests/validate-gateway.py --require-packaged-charts` passed 399 checks, `python3 tests/validate-cinder-csi.py` passed 1379 checks, and `bash tests/validate-openstack-environment.sh` passed. The Gateway run used the optional `RKE2_TRAEFIK_CHART_DIR` offline cache; official packaged chart sources are `https://github.com/rancher/rke2-charts/raw/main/assets/rke2-traefik/rke2-traefik-40.1.009.tgz` and `https://github.com/rancher/rke2-charts/raw/main/assets/rke2-traefik-1.34-1.36/rke2-traefik-40.1.013.tgz`; packages are not vendored and no unverified SHA is hardcoded.
- Remaining live gates: actual routing, HTTPS/ACME issuance, the packaged Traefik main/CRD HelmChart startup-retry path, fresh-bootstrap CRD convergence, and new-patch CSI acceptance. No existing cluster was upgraded or migrated. The 2026-11-06 `v1.35.6+rke2r1` Cinder live acceptance remains historical.

### 2026-11-07

#### Gateway API And TLS Live Acceptance (Run 2026-11-06 UTC)

- Ran from the unreleased, uncommitted `1.1.0` Dev worktree at `0721620` (`values.yaml` SHA-256 `b093deae...`, source `templates/cluster.yaml` SHA-256 `193d6656...`). No commit, push, tag, or artifact release was made, and no template source changed during the run.
- Provisioned a fresh single node (`SinglePool`) and a fresh 3CP+2W HA cluster (`MultiPool`) on default RKE2 `v1.35.9+rke2r1`; `v1.33.13+rke2r2` and `v1.34.12+rke2r1` remain offline-render-only, so the patch matrix is not fully live-accepted. Provisioning was CLI/Helm based; Rancher UI RBAC and password login were not tested.
- Bootstrap converged normally on both. The packaged `rke2-traefik` Helm job retried twice until the Gateway API CRDs were established; no manual repair was needed.
- Single node published Traefik on the node floating IP with host ports `80`/`443`, a `ClusterIP` Service, and no Gateway status address. HA kept nodes private and used one Octavia amphora `LoadBalancer` with NodePorts `80:31234` and `443:31506`; the Gateway address was the load-balancer floating IP. One reachable external IPv4 required running the stages sequentially.
- Public HTTP returned `200` on both. An unlabeled namespace route was rejected with `NotAllowedByListeners` (not asserted as `404`, because an allowed fallback route can serve the path). Per-domain cert-manager `1.21.3` HTTPS passed with normal trust, exact SNI/SAN, a named-Secret `ReferenceGrant`, and one certificate/listener reused by a second namespace. Listeners were added only through the owning Rancher provisioning `Cluster` chartValues.
- Staging issuance, exactly one controlled staging renewal per cluster with `cmctl 2.6.2` (revision 1 -> 2, new serial/fingerprint served without restart), and production issuance on a fresh issuer (revision 3) prove controlled reissuance and hot reload. They do not exercise the natural 90-day scheduler or production rotation. HA recorded valid Order/`DomainVerified`/Ready CertificateRequest but missed the direct public HTTP-01 `200`/key-auth probe; the single-node stage captured that probe once.
- HA availability was qualified, not zero-downtime: one application Pod delete gave HTTP 149/149 and HTTPS 148/149 (one transient `502`), and one Traefik Pod delete gave HTTP 160/160 and HTTPS 160/160. No whole-node, control-plane, network, or amphora failure was tested; the amphora was `STANDALONE`.
- CCM/CSI were healthy on both (`CSINode` 1 and 5, both StorageClasses present). No new PVC I/O, expansion, reattach, or reclaim test was run; the earlier `v1.35.6+rke2r1` CSI acceptance remains historical.
- Both clusters and their DNS records were cleaned up and independently verified: tenant servers/volumes/floating IPs/load balancers are zero, baseline ports and the three security groups/13 rules are unchanged, onboarding resources and the existing `test` cluster are preserved, and both test names return `NXDOMAIN`. HA teardown disabled `rke2-traefik.service.enabled` in the owning test `Cluster` chartValues and removed only the test HTTPS listener so packaged Helm deleted the Service, CCM requested load-balancer deletion, and Octavia removed the load balancer, VIP, service compute, and amphora as part of that LB cleanup; CCM removed the floating IP. Rancher CAPI then removed the Kubernetes nodes, boot volumes, and ports, and does not own the amphora or VIP.
- Details and limits: [`docs/gateway-live-acceptance.md`](docs/gateway-live-acceptance.md).
