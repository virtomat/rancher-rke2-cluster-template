# Cluster Naming

Status: published in the `main`/production catalog source `f242633`
(2026-11-09) at chart `1.1.0`; this source refresh created no new chart version,
tag, or CI artifact. A production CLI naming sanity pass completed; the live
Rancher UI form and the catalog-driven new-cluster UI path remain unchecked.

## Contract

New clusters render their name as `<environment>-<userName>` from two chart
inputs. `cluster.name` is no longer a Rancher UI question; it remains only as a
legacy direct-Helm fallback.

| Input | Allowed values | Default | Notes |
| --- | --- | --- | --- |
| `cluster.userName` | Lower-case DNS label: `a-z`, `0-9`, `-` | UI `test`; `values.yaml` `""` (legacy fallback) | No dots, uppercase, whitespace, or leading/trailing `-`. Required when `cluster.name` is empty. |
| `cluster.environment` | `stg` or `prod` | `stg` | Naming prefix only. |

- The new UI question defaults are configured as `cluster.userName=test` and
  `cluster.environment=stg`, which would render `stg-test` (`prod-test` with
  `prod`); these are question defaults, not an observed UI submission. A pure
  Helm install using the chart's `values.yaml` defaults keeps the legacy name
  `test` unchanged because `cluster.userName` is empty there.
- Maximum length is 63 characters: at most 59 for `cluster.userName` under
  `stg` and 58 under `prod`. Nothing is stripped or truncated, and the prefix is
  never de-duplicated (`stg-foo` under `stg` renders `stg-stg-foo`).
- Rendering fails for an unsupported/empty environment, non-string input, a
  non-DNS-label `userName`, both names empty, or a derived name over 63.
- Every name-derived resource consumes the same resolved name: `Cluster`
  metadata, `machineConfigRef`, `OpenstackConfig`, the cloud-config `Secret`
  name/annotation/`machineSelectorFiles` reference, `ManagedChart`
  names/targets, the `ClusterRoleTemplateBinding` hash/namespace, and Cinder CSI
  `CLUSTER_NAME`. Physical names add their own random suffixes.

Legacy compatibility: when `cluster.userName` is empty, the chart returns
`cluster.name` unchanged and ignores `cluster.environment`, so direct-Helm
releases that set only `cluster.name` keep their names without a prefix.

## Rancher UI Questions

The intended default order and values are:

1. **Cluster Name** (`cluster.userName`): UI default `test` (`values.yaml`
   stays `""`), required, string.
2. **Environment** (`cluster.environment`): immediately below Cluster Name,
   enum with `stg` = Staging (default) and `prod` = Production, required.

Both questions are visible in Simple and Advanced mode (no `show_if`). The
published source `f242633` carries this question metadata, and the production
Rancher `2.14.1` catalog was read-only verified to serve it (enum-map question
type supported), but no authenticated browser form submission was exercised:
label application, default application, ordering, and the new-cluster UI path
remain unchecked.

## CLI

New-flow installs use `cluster.userName`. The Helm release name is independent
of the rendered name; `stg-test` below is only an operator convention:

```sh
helm upgrade -i stg-test . -n fleet-default \
  --kube-context <management-context> \
  --set-string cluster.config.openstack.applicationCredentialSecretName=os-app-cred-<suffix> \
  --set cluster.userName=test
# Production category: add --set cluster.environment=prod
```

Legacy direct-Helm installs that use `--set cluster.name=...` (or the `values.yaml`
legacy default) remain unchanged and are not automatically prefixed.

## Scope And Change Safety

- New clusters only. `userName` and `environment` are creation-time inputs; do
  not modify an existing release to relabel or rename a cluster. There is no
  migration or rename path, and existing `cluster.name` releases are preserved.
- The environment category is **naming only**. It does not select production
  infrastructure, credential, account, flavor, TLS, or policy. A `prod` category
  cluster provisioned in Dev is not a production test.

## Dev Verification (2026-11-09)

Independent offline verification passed: 273 naming checks across 9 chart
renders, plus the existing Cinder CSI (1379 checks), Gateway (399 checks), and
static environment checks.

Two fresh Dev `SinglePool` clusters (one node with all roles, default
`v1.35.9+rke2r1`) were tested sequentially with `cluster.userName=category-test`:
the omitted environment produced `stg-category-test`; the explicit `prod`
environment produced `prod-category-test`. All resource prefixes, the
cloud-config annotation/references, and CSI `CLUSTER_NAME` matched; CCM, CSI,
and the Traefik Gateway became ready, and public HTTP returned `404`. Bootstrap
reached Ready/controllers-ready in 658 s/818 s (stg) and 649 s/865 s (prod).
Asynchronous boot-time controller restarts self-recovered (maximum observed 5
stg and 7 prod) with no repair; this is not a zero-restart claim.

Independent verification passed 18 checks for stg, 23 for prod, and 17 for
final cleanup. The original baseline was restored: zero VMs, volumes, floating
IPs, and load balancers; the original 3 security groups and 13 rules, onboarding
3 Secrets, and 1 ConfigMap were preserved; the other user cluster and 16
historical releases were untouched. No test resources remain. All side effects
were Dev-only; no production catalog or `main` changed.

Limits: no DNS, issuer, or PVC lifecycle test was run (names and CSI identity
only), so this is not a rerun of full TLS/storage acceptance. The Rancher UI
form and published-catalog path remain unverified, so the checklist stays
unchecked. Non-secret transient evidence was kept under
`/tmp/opencode/cluster-category/`.

## Production Naming Sanity (2026-11-09)

One fresh `SinglePool` cluster (one node with all roles, default
`v1.35.9+rke2r1`) was created on production Rancher `2.14.1` from published
source `f242633` with `cluster.userName=category-sanity` and
`cluster.environment=prod`. It rendered `prod-category-sanity`; the
`OpenstackConfig` name, cloud-config Secret annotation/references, and Cinder
CSI `CLUSTER_NAME` all matched. Management readiness took 356 s.

CCM, CSI, and the Traefik Gateway became ready; the Traefik DaemonSet pods
published host ports `80`/`443` while the Service remained a `ClusterIP`, and
anonymous HTTP returned `404`. Both StorageClasses matched the contract
(`cinder-delete` default, `cinder-retain` non-default, WaitForFirstConsumer,
expansion enabled). No PVC, DNS record, issuer, or TLS material was created,
and no existing cluster was changed.

Limits: this is naming and baseline sanity, not a fresh Gateway, TLS, Cinder
lifecycle, HA, or UI acceptance run. One `helm uninstall` at 16:46:51Z and the
normal Rancher CAPI cascade (complete 16:47:36Z, 45 s total) removed all test
resources with no manual repair. The production baseline ports, security
groups/rules, network, subnet, keypair, onboarding Secrets, and environment
ConfigMap were preserved. Non-secret evidence is under
`/tmp/opencode/cluster-category-production/`.
