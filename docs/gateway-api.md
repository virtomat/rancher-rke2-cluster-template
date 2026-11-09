# Gateway API Ingress And Per-Domain TLS Onboarding

This guide describes the chart `1.1.0` Gateway API baseline and the
administrator/application workflow for adding TLS to a tenant cluster. It is an
integration guide, not an add-on that the template installs for you.

## Scope And Status

- Applies to **new clusters** provisioned from chart `1.1.0`. Do not upgrade or
  migrate an existing NGINX or other ingress path to this baseline as part of
  this work.
- Independent offline verification completed on 2026-11-06: the Gateway
  contract test passed 399 checks, the Cinder CSI contract test passed 1379
  checks, and the static environment contract check passed. These are local
  render/static results only. Fresh live acceptance then completed on 2026-11-06
  (UTC) on the default `v1.35.9+rke2r1` for a single node and a
  3-control-plane/2-worker HA cluster: CRD bootstrap, HTTP, per-domain
  HTTPS/ACME, controlled reissuance, and cleanup. It did not cover the
  `v1.33`/`v1.34` pins, Rancher UI RBAC, the natural renewal scheduler, or
  whole-node failure. See
  [`gateway-live-acceptance.md`](gateway-live-acceptance.md). The examples here
  remain documentation artifacts, not a second acceptance run.
- Default-pin production acceptance then completed on Rancher `2.14.1` on
  2026-11-08/09 (UTC) for the same default `v1.35.9+rke2r1` single-node and
  3CP+2W HA paths. See
  [`production-live-acceptance.md`](production-live-acceptance.md). The
  `v1.33`/`v1.34` pins, Rancher UI RBAC, the natural renewal scheduler, and
  whole-node failure remain unverified.
- The template does **not** install cert-manager, an issuer, a Certificate, a
  TLS Secret, an email address, a DNS credential, or a DNS controller. Those
  are administrator/application responsibilities.
- The examples use placeholders such as `shop`, `shop.example.com`, and
  `admin@example.com`. Replace them deliberately; never commit real
  credentials or private keys.

## Current Ingress Baseline

The rendered `Cluster` forces `ingress-controller: [traefik]`. The packaged
`rke2-traefik` chart owns GatewayClass `traefik`, Gateway
`kube-system/shared-gateway`, the Traefik DaemonSet, and its Service. No Gateway
or GatewayClass is embedded in `additionalManifest`.

| Item | Baseline |
| :--- | :--- |
| GatewayClass | `traefik`, owned by the packaged chart |
| Gateway | `kube-system/shared-gateway`, owned by the packaged chart |
| Default listener | `web`: `HTTP`, packaged port `8000`, external `80` |
| Namespace opt-in for `web` | label selector `gateway-access: public` |
| External `443` | Published/allocated through `websecure` and the Service, but no HTTPS listener is configured by default |
| Default TLS | None. `ports.websecure.http.tls.enabled: false` prevents the global self-signed default |
| Single master | Traefik DaemonSet on Linux control-plane nodes with control-plane/etcd tolerations, host ports `80`/`443`, `ClusterIP` Service reached through the master floating IP |
| HA (3+ masters) | Same DaemonSet with host ports cleared, one `LoadBalancer` Service served by CCM/Octavia |

The packaged add-on versions in this matrix are:

| RKE2 | `rke2-traefik` chart | Traefik | Gateway API standard bundle |
| :--- | :--- | :--- | :--- |
| `v1.33.13+rke2r2` | `40.1.009` | `3.7.8` | `1.5.1` |
| `v1.34.12+rke2r1` / `v1.35.9+rke2r1` | `40.1.013` | `3.7.13` | `1.6.1` |

The Gateway listener port is the **internal packaged entrypoint port**
(`8000` for HTTP, `8443` for HTTPS). The Service or host-port mapping publishes
it as external `80`/`443`. Do not set a Gateway listener to `80` or `443`; the
packaged chart requires the listener port to match a declared `ports` entry.

In single-master host-port mode the Gateway status has no addresses.
Administrators continue to use the master floating IP for DNS, as before. HA
copies the LoadBalancer status. There is no custom discovery or ExternalDNS
controller. One Traefik controller and one Service serve all Gateways;
additional Gateways or controllers are manual administrator work and are out of
scope.

## Ownership

| Resource or decision | Owner |
| :--- | :--- |
| Chart version, new-cluster provisioning, Gateway baseline | Administrator/platform |
| Gateway `kube-system/shared-gateway` and its listeners | Administrator/platform |
| Namespace opt-in labels and per-listener namespace policy | Administrator/platform |
| cert-manager installation and Gateway API configuration | Administrator/platform |
| `ClusterIssuer` / `Issuer` definitions and ACME account | Administrator/platform |
| DNS A/AAAA records and floating-IP/DNS association | Administrator/platform |
| Application `Service` and `HTTPRoute` | Application team |
| Per-domain `Certificate` and cert-manager TLS Secret | Application team |
| `ReferenceGrant` for its named TLS Secret | Application team |
| Per-domain HTTPS listener addition | Administrator on application request |

An application may span several namespaces. Keep one per-domain `Certificate`
and TLS Secret in a designated application namespace. Its HTTPS listener remains
on the shared Gateway in `kube-system`. Other namespaces can own `HTTPRoute`s
that attach to that listener only when its `allowedRoutes` namespace selector
includes them. The HTTPS example selects only
`kubernetes.io/metadata.name: shop`, so an administrator must broaden that
selector intentionally for another namespace. The shared `web` HTTP-01 opt-in
label is needed in the Certificate/solver namespace. A route in another
namespace that references a backend `Service` in `shop` needs a
`ReferenceGrant` in the backend Service's destination namespace, or it should
use a local route/backend. This is consistent with the per-domain guidance
below.

## Prerequisites

### New Cluster And Gateway CRDs

1. The cluster must be a new `1.1.0` cluster, not an upgraded legacy cluster.
2. Gateway API CRDs must exist before cert-manager starts. The packaged Traefik
   CRD bundle supplies them for new clusters. Verify on the target cluster:

   ```sh
   kubectl --context "$TENANT_CONTEXT" get crd \
     gateways.gateway.networking.k8s.io \
     httproutes.gateway.networking.k8s.io \
     referencegrants.gateway.networking.k8s.io
   ```

3. RKE2 installs the packaged Traefik main and CRD HelmCharts asynchronously and
   declares no explicit dependency between them. The initial Traefik Helm job
   may retry until the Gateway API CRDs are established; allow bounded normal
   initial convergence. If the CRDs remain missing or the job stays failed after
   that, inspect the `HelmChart`, jobs, and events and report it. Do not delete,
   restart, or uninstall resources or apply a custom repair automatically, and
   do not compensate with a cert-manager restart.

### cert-manager

Use a compatible, verified, pinned cert-manager patch. At the time of writing,
the official release information is at
<https://cert-manager.io/docs/releases/>: cert-manager `1.21` supports Kubernetes
`1.33`-`1.36`, and `1.20` supports `1.32`-`1.35`. For a new install, prefer the
latest verified patch in the `1.21` line. This repository deliberately does not
invent or hardcode an exact patch pin; choose the patch your organization has
verified and pin it through your normal OCI/Helm process.

For the verified current chart, the required values are:

```yaml
crds:
  enabled: true
config:
  gatewayAPI:
    enabled: true
```

These are installation configuration, not a managed chart add-on. See
[`../examples/gateway/certmanager-values.yaml`](../examples/gateway/certmanager-values.yaml).
The Gateway API setting is `config.gatewayAPI.enabled`, matching the current
1.21 chart's `ControllerConfiguration`. Do not use the older
`config.enableGatewayAPI` spelling; inspect the exact pinned chart's values and
schema if you are not on 1.21.

Verify that the cert-manager controller sees Gateway API support before
continuing. Install cert-manager only after the Gateway API CRDs exist and
before creating any `ClusterIssuer` or `Certificate`.

### Public Reachability And DNS

- Let's Encrypt HTTP-01 validates the domain over **public port 80**. The
  cluster must have a public address for the selected Gateway listener:
  the master floating IP in single-master mode, or the LoadBalancer floating IP
  in HA.
- Create a DNS `A` and/or `AAAA` record for each domain. Every published address
  must be valid and reach the Gateway. A partial record set can fail validation.
- Do not use wildcard certificates with HTTP-01. Wildcards require DNS-01 and
  are outside this workflow.
- The shared HTTP `web` listener must remain reachable for initial issuance and
  renewal. Do not add a global HTTP-to-HTTPS redirect that blocks
  `/.well-known/acme-challenge/`.

## Contexts And Names

All downstream-cluster commands use an explicit tenant context. Management
edits use a clearly different management context, the derived user namespace,
and the actual Rancher cluster name. Do not assume guessed names.

```sh
# Management cluster where Rancher and the Helm release live.
export MGMT_CONTEXT='<explicit-management-kubectl-context>'
export ROOT_NAMESPACE='fleet-default'          # Helm release namespace
export DERIVED_NAMESPACE='u-<suffix>'          # derived from os-app-cred-<suffix>
export CLUSTER='<actual-provisioning-cluster-name>'

# Target/downstream cluster where Gateways and application resources live.
export TENANT_CONTEXT='<explicit-tenant-kubectl-context>'
export TENANT_NAMESPACE='shop'
export DOMAIN='shop.example.com'
```

Use `--context "$TENANT_CONTEXT"` for `Certificate`, `HTTPRoute`,
`ReferenceGrant`, `Gateway`, `Service`, and app checks. Use
`--context "$MGMT_CONTEXT"` only for the Rancher provisioning object or the
cluster-template Helm release. Never apply a downstream resource with the
management context by accident.

## Onboarding Order

Use this order for each domain. The order keeps the HTTP challenge path
available while the HTTPS listener and its Secret are introduced.

1. Establish/verify Gateway API CRDs, then install/verify cert-manager
   (administrator).
2. Create the staging `ClusterIssuer` (administrator).
3. Label the application namespace for the shared HTTP listener
   (administrator-controlled opt-in).
4. Create the per-domain `Certificate` with the staging issuer and wait for
   `Ready=True` (application).
5. Create the `ReferenceGrant` for the named TLS Secret (application).
6. Add the per-domain HTTPS listener through Rancher `Cluster` chartValues
   (administrator).
7. Create the `HTTPRoute` bound to that listener (application).
8. After DNS and TLS verification, create the production issuer, replace the
   Certificate's issuer reference, and wait for a new `Ready=True` (application
   and administrator review).

### 1. Staging Issuer

Apply the staging issuer (`letsencrypt-staging`) to the target cluster. Use the
example with a real administrator email:

```sh
kubectl --context "$TENANT_CONTEXT" apply \
  -f examples/gateway/cluster-issuer-staging.yaml
```

The HTTP-01 solver attaches a temporary HTTPRoute to the shared `web` listener:

```yaml
solvers:
  - http01:
      gatewayHTTPRoute:
        parentRefs:
          - name: shared-gateway
            namespace: kube-system
            kind: Gateway
            sectionName: web
```

Do not set `port` on the parent reference. The listener's real internal port is
`8000`; external `80` is only the Service/host-port mapping. cert-manager
creates its temporary challenge HTTPRoute in the Certificate's namespace, so
that namespace must be allowed by the listener's namespace policy. The example
namespace label `gateway-access: public` satisfies the default `web` selector.
No `ReferenceGrant` is required for route attachment.

### 2. Namespace Opt-In

The namespace label is an administrator-controlled namespace opt-in, not
hostname authorization. Apply it before creating the Certificate and keep it
present for renewals:

```sh
kubectl --context "$TENANT_CONTEXT" apply -f examples/gateway/namespace.yaml
```

The default `web` listener uses `gateway-access: public`. The HTTPS example
listener uses a separate per-listener selector, `kubernetes.io/metadata.name:
shop`, to limit route attachment to the intended namespace. Kubernetes
maintains `kubernetes.io/metadata.name` automatically; do not try to remove it.

### 3. Per-Domain Certificate

The application owns one Certificate and one TLS Secret per domain. Start with
the staging issuer so rate limits and trust mistakes do not affect production:

```sh
kubectl --context "$TENANT_CONTEXT" apply -f examples/gateway/certificate.yaml
kubectl --context "$TENANT_CONTEXT" -n "$TENANT_NAMESPACE" \
  wait --for=condition=Ready certificate/shop-example-com --timeout=10m
```

If the challenge stalls, inspect `Certificate`, `Order`, `Challenge`, and the
temporary `cm-acme-http-solver-*` HTTPRoute/Service in the application
namespace. Re-check that public port `80` reaches the `web` listener and that
the namespace label is present.

### 4. Narrow ReferenceGrant

The Gateway is in `kube-system`; the Certificate Secret is in the application
namespace. Gateway API requires a `ReferenceGrant` in the Secret's namespace
for that cross-namespace `certificateRefs` reference. The grant can name the
Secret but cannot name the source Gateway object; it grants Gateways in the
specified source namespace. Narrow it to the single named Secret:

```sh
kubectl --context "$TENANT_CONTEXT" apply -f examples/gateway/referencegrant.yaml
```

The example uses `gateway.networking.k8s.io/v1beta1`. Both packaged Gateway API
bundles in the supported matrix serve `v1` and `v1beta1`; `v1beta1` is valid for
both and is the storage version in the inspected CRDs. Verify the served
versions on the actual cluster before changing the API version:

```sh
kubectl --context "$TENANT_CONTEXT" get crd \
  referencegrants.gateway.networking.k8s.io \
  -o jsonpath='{range .spec.versions[*]}{.name}{" served="}{.served}{"\n"}{end}'
```

If a target serves only `v1`, use `gateway.networking.k8s.io/v1` with the same
`spec`. Do not assume the version without inspecting the CRD.

### 5. Add The HTTPS Listener

The listener is **not** a standalone Gateway replacement and must not be
`kubectl apply`-ed as a Kubernetes object. It is a packaged Traefik values
fragment that is merged under `rke2-traefik` while preserving the chart's
existing `web` listener, providers, ports, Service, and topology invariants.

Default workflow: add the listener after the per-domain Certificate is
`Ready=True` and the ReferenceGrant is applied. New-cluster-only provisioning
does not forbid later administrator configuration of a newly created `1.1.0`
baseline cluster; it forbids upgrading or retrofitting a legacy cluster
template.

Merge this fragment into the existing `rke2-traefik` chart values:

```yaml
gateway:
  listeners:
    shop-https:
      port: 8443
      protocol: HTTPS
      hostname: shop.example.com
      mode: Terminate
      certificateRefs:
        - name: shop-example-com-tls
          namespace: shop
      namespacePolicy:
        from: Selector
        selector:
          matchLabels:
            kubernetes.io/metadata.name: shop
```

For a **1.1.0 tenant cluster** after provisioning (the default workflow), the
administrator edits the Rancher `provisioning.cattle.io/v1` `Cluster` in
`$DERIVED_NAMESPACE` on the **management** cluster. The durable path is:

```text
spec.rkeConfig.chartValues.rke2-traefik
```

Inspect the current management object before editing; this is a read-only check
with the management context, not the tenant context:

```sh
kubectl --context "$MGMT_CONTEXT" -n "$DERIVED_NAMESPACE" \
  get clusters.provisioning.cattle.io "$CLUSTER" \
  -o jsonpath='{.spec.rkeConfig.chartValues.rke2-traefik.gateway.listeners}'
```

Use the normal Rancher cluster-edit or approved GitOps flow to merge the
listener. Do not replace the whole
`rke2-traefik` value, do not remove the existing `web` listener, and do not
patch the Helm-owned Gateway in the downstream cluster directly; the packaged
chart reconciles it. Do not use `helm upgrade` of the cluster-template release
to add a listener to an existing cluster.

Advanced/optional initial provisioning: if you must predeclare the listener in
the initial Helm values wrapper `cluster.config.chartValues.rke2-traefik`, that
is not the default workflow. The listener remains unresolved/not Ready until the
Certificate Secret and ReferenceGrant exist, and the initial HTTP `web` path
must remain functional. Apply the same merge and non-overwrite rules.

The listener port `8443` matches the baseline declared `websecure` entrypoint,
so the external `443` mapping is already allocated. The Secret name and
namespace must match the Certificate and ReferenceGrant. After the merge, check
that the Gateway accepted and programmed the listener:

```sh
kubectl --context "$TENANT_CONTEXT" -n kube-system get gateway shared-gateway \
  -o jsonpath='{range .status.listeners[*]}{.name}{" accepted="}{.conditions[?(@.type=="Accepted")].status}{" programmed="}{.conditions[?(@.type=="Programmed")].status}{"\n"}{end}'
```

### 6. Application HTTPRoute

The application owns the `HTTPRoute` and binds it to the administrator's HTTPS
listener with `sectionName`. The hostname must match the listener and the
Certificate:

```sh
kubectl --context "$TENANT_CONTEXT" apply -f examples/gateway/httproute.yaml
kubectl --context "$TENANT_CONTEXT" -n "$TENANT_NAMESPACE" \
  get httproute shop -o yaml
```

The example expects an existing `Service` named `shop` on port `80`; it does not
deploy a demo application or image. The route's `parentRefs` uses
`shared-gateway` in `kube-system`, `sectionName: shop-https`, and no `port`.
The listener's namespace policy allows the `shop` namespace; the route does not
need a ReferenceGrant for route attachment.

### 7. Staging To Production

Do not treat a staging certificate as production. Once public DNS resolves to
all published addresses and the staging certificate is `Ready=True`:

1. Create a distinct production issuer, for example
   `letsencrypt-production`, using the production ACME directory. See
   [`../examples/gateway/cluster-issuer-production.yaml`](../examples/gateway/cluster-issuer-production.yaml).
2. Update the existing Certificate's `spec.issuerRef.name` to the production
   issuer. Keep the same per-domain Certificate/Secret pair unless your process
   explicitly requires separate names.
3. Do not delete the TLS Secret or private key to force reissuance. Let
   cert-manager issue the replacement and wait for `Ready=True`.
4. Verify the served certificate is from a valid production issuer, not a
   staging/untrusted issuer, and that the HTTPS listener and route still work.

For multiple domains, repeat the Certificate/ReferenceGrant/listener/HTTPRoute
steps per domain. Each domain gets its own Certificate, TLS Secret, and
listener; one listener can serve routes from multiple namespaces only when its
`allowedRoutes` selector intentionally includes them. Do not reuse one wildcard
HTTP-01 certificate as a shortcut.

## Verification Commands

Run downstream checks with the explicit tenant context:

```sh
kubectl --context "$TENANT_CONTEXT" get gatewayclass traefik
kubectl --context "$TENANT_CONTEXT" -n kube-system get gateway shared-gateway -o yaml
kubectl --context "$TENANT_CONTEXT" -n "$TENANT_NAMESPACE" get certificate,order,challenge
kubectl --context "$TENANT_CONTEXT" -n "$TENANT_NAMESPACE" get httproute shop -o yaml
```

Check the public HTTP challenge path and the HTTPS endpoint:

```sh
curl -v "http://${DOMAIN}/.well-known/acme-challenge/<token>"
curl -vk --resolve "${DOMAIN}:443:<published-address>" "https://${DOMAIN}/"
```

Inspect the issuer of the served certificate without printing private key
material:

```sh
openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
```

For the offline chart contract, see the README's
[`Offline Contract Checks`](../README.md#offline-contract-checks) section.
Independent verification on 2026-11-06 passed 399 Gateway checks, 1379 CSI
checks, and the static shell check. Those are local render/static results only.
Fresh live acceptance on the same date covered the default `v1.35.9+rke2r1`
single-node and HA paths; see
[`gateway-live-acceptance.md`](gateway-live-acceptance.md).

## Operational Limits

- **No cert-manager add-on:** the template does not manage cert-manager,
  issuers, ACME accounts, DNS credentials, or ExternalDNS.
- **No wildcard HTTP-01:** use per-domain certificates; wildcard issuance needs
  a separately designed DNS-01 flow.
- **No global redirect by default:** keep the shared HTTP listener reachable
  for ACME. If a redirect is later required, scope it so challenge paths remain
  reachable and review it separately.
- **Certificate Secret cross-namespace:** a listener `certificateRefs` entry
  pointing outside the Gateway namespace requires a ReferenceGrant in the
  Secret's namespace. The grant cannot name the source Gateway object.
- **Namespace opt-in is not hostname authorization:** the listener selector and
  route hostname rules must both be correct.
- **One Service per controller, not per Gateway:** multiple Gateways or
  controllers are manual administrator work outside this baseline.
- **No existing-cluster upgrade/migration:** do not retrofit this guide onto an
  existing NGINX cluster as part of `1.1.0`.
- **Live acceptance scope:** live acceptance covers the Gateway baseline and
  per-domain TLS on the default `v1.35.9+rke2r1` only, in Dev (2026-11-06) and
  production Rancher `2.14.1` (2026-11-08/09); the `v1.33`/`v1.34` pins,
  Rancher UI RBAC, the natural renewal scheduler, and whole-node/load-balancer
  failure remain unverified. See
  [`gateway-live-acceptance.md`](gateway-live-acceptance.md) and
  [`production-live-acceptance.md`](production-live-acceptance.md).

## Example Bundle

Files and their roles. Follow the numbered onboarding order above; the
cert-manager values file is installation-time configuration, not a last step.

| File | Purpose |
| :--- | :--- |
| [`../examples/gateway/certmanager-values.yaml`](../examples/gateway/certmanager-values.yaml) | Optional cert-manager installation/config values; use after Gateway API CRDs and before issuers/Certificates; not a managed add-on |
| [`../examples/gateway/cluster-issuer-staging.yaml`](../examples/gateway/cluster-issuer-staging.yaml) | Staging ACME `ClusterIssuer` with the Gateway HTTP-01 solver |
| [`../examples/gateway/namespace.yaml`](../examples/gateway/namespace.yaml) | Application namespace with the shared `web` listener opt-in label |
| [`../examples/gateway/certificate.yaml`](../examples/gateway/certificate.yaml) | Per-domain Certificate using the staging issuer |
| [`../examples/gateway/referencegrant.yaml`](../examples/gateway/referencegrant.yaml) | Narrow grant for the named TLS Secret |
| [`../examples/gateway/gateway-listener-values.yaml`](../examples/gateway/gateway-listener-values.yaml) | Packaged Traefik values fragment for the HTTPS listener; merge, do not apply |
| [`../examples/gateway/httproute.yaml`](../examples/gateway/httproute.yaml) | HTTPS HTTPRoute bound to `sectionName: shop-https` |
| [`../examples/gateway/cluster-issuer-production.yaml`](../examples/gateway/cluster-issuer-production.yaml) | Optional production issuer with a distinct name |

## References

- [cert-manager releases and Kubernetes support](https://cert-manager.io/docs/releases/)
- [cert-manager Helm installation](https://cert-manager.io/docs/installation/helm/)
- [cert-manager Gateway usage](https://cert-manager.io/docs/usage/gateway/)
- [cert-manager HTTP-01 Gateway API solver](https://cert-manager.io/docs/configuration/acme/http01/)
- [Gateway API documentation](https://gateway-api.sigs.k8s.io/)
- [RKE2 Traefik chart sources](https://github.com/rancher/rke2-charts/tree/main/assets)
