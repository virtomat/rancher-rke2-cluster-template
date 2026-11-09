# Cluster Naming (Unreleased)

Status: unreleased local `dev` worktree feature. `Chart.yaml` remains `1.1.0`;
published `main` catalog source `9fdcace` (2026-11-08) does **not** include it.
No commit, push, tag, CI artifact, or publication is implied, and the live
Rancher UI/published-catalog path remains pending verification.

## Contract

New clusters render their name as `<environment>-<userName>` from two chart
inputs. `cluster.name` is no longer a Rancher UI question; it remains only as a
legacy direct-Helm fallback.

| Input | Allowed values | Default | Notes |
| --- | --- | --- | --- |
| `cluster.userName` | Lower-case DNS label: `a-z`, `0-9`, `-` | UI `test`; `values.yaml` `""` (legacy fallback) | No dots, uppercase, whitespace, or leading/trailing `-`. Required when `cluster.name` is empty. |
| `cluster.environment` | `stg` or `prod` | `stg` | Naming prefix only. |

- Under the new UI flow, the default question values render `stg-test`, and
  `prod-test` when the environment is `prod`. A pure Helm install using the
  chart's `values.yaml` defaults keeps the legacy name `test` unchanged because
  `cluster.userName` is empty there.
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

Both questions are visible in Simple and Advanced mode (no `show_if`). Installed
Rancher `2.14.3` enum-map support is evidenced, but the full live form is
**not** tested: the Dev catalog (`fbeb861`) lacks the uncommitted feature and no
commit/push was authorized, so label, default, ordering, and the new-cluster UI
path remain pending.

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
`/tmp/opencode/cluster-category/`; no credentials were recorded.
