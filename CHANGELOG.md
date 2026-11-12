# 1.1.0 source update (2026-11-09)

## Changes:
- feat: Add environment-prefixed naming for new clusters. A non-empty `cluster.userName` renders as `<cluster.environment>-<cluster.userName>`, with `stg` (default) or `prod` as the naming-only prefix; the result must stay within 63 characters and is never stripped or truncated.
- feat: Replace the `cluster.name` Rancher UI question with `cluster.userName` (default `test`, required) immediately followed by `cluster.environment` (enum `stg`/`prod`, default `stg`, required), both visible in Simple and Advanced. All name-derived resources (Cluster, machine configs, cloud-config Secret, ManagedCharts, ClusterRoleTemplateBinding, and Cinder CSI `CLUSTER_NAME`) consume the same resolved name.
- feat: Preserve legacy direct-Helm compatibility. An empty `cluster.userName` returns `cluster.name` unchanged and ignores the environment prefix; no existing release is renamed or migrated.
- docs: Add `docs/cluster-naming.md` and refresh README, Rancher UI checklist, root internal guide, and update plan for the naming contract and its pending UI gate.
- test: Add `tests/validate-cluster-naming.py` (273 checks, 9 renders) and extend the static environment contract check.
- note: This is a source update published on `main` at `f242633` (2026-11-09) under chart `1.1.0`; it is not a new chart version, semantic-version tag, CI artifact, or Harbor/OCI release. A production CLI naming sanity pass completed on Rancher `2.14.1`; the live Rancher UI form and catalog-driven new-cluster UI path remain unverified. See [`docs/cluster-naming.md`](docs/cluster-naming.md#production-naming-sanity-2026-11-09).

# 1.1.0 (2026-11-08, published source baseline)

## Changes:
- feat: Advance the supported RKE2 matrix to `v1.33.13+rke2r2`, `v1.34.12+rke2r1`, and `v1.35.9+rke2r1` (default); Rancher 2.14.3 supports Kubernetes 1.33-1.35 only, so no 1.36/1.37 path is offered.
- feat: Replace the legacy NGINX ingress contract with the packaged `rke2-traefik` Gateway baseline: forced `ingress-controller: [traefik]`, GatewayClass `traefik`, Gateway `kube-system/shared-gateway`, default HTTP `web` listener on internal `8000`/external `80`, namespace opt-in `gateway-access: public`, and no default HTTPS/TLS material.
- feat: Keep single-master host ports and `ClusterIP` publication through the master floating IP; use one `LoadBalancer` Service with host ports cleared in HA. External `443`/`websecure` remain published and ready for administrator-added HTTPS listeners.
- docs: Add `docs/gateway-api.md` and non-secret `examples/gateway/` for per-domain cert-manager TLS, staging-first issuance, narrow cross-namespace `ReferenceGrant`, HTTP-01 through the shared `web` listener, and listener merge into Rancher `Cluster` chartValues. The template does not install cert-manager or bootstrap issuers, domains, emails, or DNS credentials.
- docs: Refresh README, Rancher UI checklist, update plan, root internal guide, and security-group tuning references for the Gateway baseline; preserve the historical `v1.35.6+rke2r1` Cinder live-acceptance record and cleanup confirmation.
- test: Document `python3 tests/validate-gateway.py --require-packaged-charts` with the optional offline `RKE2_TRAEFIK_CHART_DIR` package cache and official RKE2 Traefik chart source URLs; no packages or unverified SHAs are vendored.
- test: Production live acceptance on Rancher `2.14.1` completed for the default `v1.35.9+rke2r1` single-node and 3CP+2W HA paths, covering Gateway HTTP/TLS issuance and reload, qualified HA availability, Cinder CSI lifecycle, and cleanup; see [`docs/production-live-acceptance.md`](docs/production-live-acceptance.md).
- note: `1.1.0` is published as a git-backed Rancher catalog source baseline from `main`; this repository creates no CI artifact, semantic-version tag, or Harbor/OCI release. The new patch matrix, Gateway baseline, and TLS onboarding completed independent offline verification and default-pin production acceptance. The `v1.33.13+rke2r2` and `v1.34.12+rke2r1` pins remain offline-render-only, so the full patch matrix, Rancher UI RBAC, and whole-node failure paths remain open.

# v2.0.1

## Changes:
- feat: Raise k8s patch Version from v1.30.2 to v1.30.5 and added audit-policy-file to machineGlobalConfig [0cbb8da7](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/0cbb8da7dccfb472b6661400239e316946c429c0)


# v2.0.0

## Changes:
- feat: Restructure repository to contain multiple helm-charts [c87cb53f](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/c87cb53fdcfe0245ff91c28ab2fc73fbf64a2c4d)
- doc: Added link to helm-charts [53b5bb2e](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/53b5bb2ee468810aba4ffe13c6fd33fd27e31b94)
- fix: CI Fileserver URL [51042d78](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/51042d78ca8dfdb087f65b8b6f808b85db61e78b)
- fix: Readded CI run rule [5fdd1b88](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/5fdd1b8807996825b7d73a317a833bc1295909e5)
- doc: Fix Helm CHart download URL [b07f03d8](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/b07f03d81f68b69e2563275dfa20b3a74354fde7)
- doc: Formatting [a1f67c0e](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/a1f67c0e9dc9e35a3d0a4629e1ff71626707a482)
- feat: Added Artifact Hub repository ID [e06b0c21](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/e06b0c21635c630d16d403329f46637486742fe0)
- fix: Indexing of repository in helm index [b7c6a933](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/b7c6a933572c60153517783667f581f20a383d93)
- fix: force helm chart upload [363f7a83](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/363f7a83641edd1551832bf54538fa34a4ff1891)
- fix: Readded CI rule [08a76d63](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/08a76d63d587035b0cd97bbe1c1a609faa20c68d)
- doc: Added Repo URL [340fd61f](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/340fd61f314bfa38481d528b0d2149204ff52aaa)
- fix: Commented out section in CI [71713bab](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/71713babcb09dafb538f0b1cbf8eca2d09bfa8cb)
- doc: Remove unneded option [225943d1](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/225943d1d81f8b8420592f53db99767dddb905cf)
- doc: Added known issue when nodes of a downstream cluster stop during rke2/k3s setup [2ac3cd04](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/2ac3cd043f47a13aaba1e491bbbf4a3fee0988df)
- fix: Uncomment disable_cloud_controller (was unintentionally enabled) [9199e17b](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/9199e17b3f45f01396f87cc0f1a013d345d2aa66)


# v1.1.3

## Changes:
- fix: Yaml linting [1f67e80f](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/1f67e80f1c3fc273d52223ba64729e9586e44114)


# v1.1.2

- Changes for v1.1.2 got added to v1.1.1 by accident


# v1.1.1

## Changes:
- fix: Lowered min k8s Version to from 1.27 to 1.26 [93753fc3](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/93753fc3307385a07fc729911fbea3210123764d)
- doc: Added lowest supported k8s Version in requirements [7f9e1d75](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/7f9e1d7599a6d3f96f1d83d21d7f0defd800d57a)
- fix: some openstackconfig errors [0746f7a7] (https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/0746f7a7ed1a8dbce14dc74f9f308c37be534622)

# v1.1.0

## Changes:
- feat: Added option to set labels for Pools [f93138d9](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/f93138d9554f575914d1abd73ec7e552a2a6aa68)
- doc: Added description where to find the template within rancher [a3e43a68](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/a3e43a685f83b0a93d78d947e6abeff975c3d27a)
- fix: additionalManifests duplicate and added lables option to Nodepool [1179c0a3](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/1179c0a32af92eb082921af3e7f8732f5887d77b)
- feat: Added label option to nodepool [8d417180](https://jugit.fz-juelich.de/iek-10/public/ict-platform/deployment/kubernetes/helm-charts/-/commit/8d41718015f7317e33000009cd067674886b6971)


# v1.0.0

- Initial release
