# Rancher RKE2 Cluster Template Update Plan

Goal: improve chart consistency, maintainability, and documentation while preserving Dev deployability first; later prepare and track Prod-specific adaptation.

## Working Model

- `dev`: shared cleanup and Dev-validated improvements
- `main`: shared baseline first, Prod-specific patches later
- This file is intended to be kept on both branches and to track work affecting both environments.
- Shared generic fixes should remain small and cherry-pickable between branches.

## Current Status

- Phase: planning and initial documentation cleanup
- Current baseline: imported chart under review
- Current validation target: Dev environment
- Branch split status: `dev` branch created from `main`; shared cleanup now continues on `dev`

## Progress

- [x] Create `dev` branch from current `main`
- [x] Add a shared `update-plan.md` tracker for both branches
- [x] Add a README status note and maintained-files index
- [ ] Align top-level documentation with actual chart behavior
- [ ] Fix `values.yaml`, `questions.yaml`, and `templates/` mismatches
- [ ] Validate generic cleanup in Dev
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
  - Appears unrelated to this Helm chart.
  - No chart references found.
  - Candidate for removal from this repo.
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
- [ ] Remove `systemprompt.md` if confirmed unrelated.
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
