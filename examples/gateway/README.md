# Gateway API Example Bundle

Non-secret examples for the chart `1.1.0` Gateway baseline. They are starting
points, not a one-command deployment. Replace `shop`, `shop.example.com`, and
`admin@example.com` with approved values, and use explicit management and tenant
kubectl contexts as described in [`../../docs/gateway-api.md`](../../docs/gateway-api.md).

## Prerequisite And Apply/Merge Order

1. `certmanager-values.yaml` - optional values for installing or configuring
   cert-manager; if cert-manager already exists, use it as the configuration
   reference and ensure Gateway support is enabled. cert-manager is not
   installed or managed by this chart. Install or configure it after the Gateway
   API CRDs are established and before any `ClusterIssuer`/`Certificate`.
   Gateway support (`config.gatewayAPI.enabled: true`) is required for the
   HTTP-01 workflow.
2. `cluster-issuer-staging.yaml` - staging `ClusterIssuer`; replace the email.
3. `namespace.yaml` - administrator-controlled namespace opt-in for the shared
   HTTP `web` listener.
4. `certificate.yaml` - application per-domain `Certificate`; wait for
   `Ready=True` before continuing.
5. `referencegrant.yaml` - narrow cross-namespace grant for the named TLS
   Secret. The example uses `gateway.networking.k8s.io/v1beta1`; verify the
   served CRD versions on the target cluster.
6. `gateway-listener-values.yaml` - packaged Traefik values **fragment**.
   Merge it under the existing `rke2-traefik` chart values; do not apply it as a
   Kubernetes object and do not replace the existing `web` listener.
7. `httproute.yaml` - application `HTTPRoute` bound to `shop-https`. The
   application `Service` named `shop` on port `80` is presumed to exist.
8. `cluster-issuer-production.yaml` - optional, after DNS verification. Create
   the distinct production issuer, update the Certificate's issuer reference,
   and wait for `Ready=True`. Do not delete the TLS Secret/private key.

## Constraints

- The template does not install cert-manager, issuers, domains, emails, DNS
  credentials, or ExternalDNS.
- The listener fragment is not a standalone Gateway replacement.
- For an existing `1.1.0` cluster, merge the listener through Rancher
  `provisioning.cattle.io/v1` `Cluster.spec.rkeConfig.chartValues.rke2-traefik`
  on the management cluster. Do not use `helm upgrade` of the cluster-template
  release to add a listener, and do not patch the Helm-owned Gateway directly.
- Keep the shared HTTP listener reachable for ACME renewals.
- Do not use wildcard HTTP-01. Each domain gets its own Certificate, TLS Secret,
  and listener.
- One listener can serve routes from more than one namespace only when its
  `allowedRoutes` selector includes them; the example selects only `shop`.
  Cross-namespace backend `Service` references need a `ReferenceGrant` in the
  backend Service's namespace.
- These examples contain no plaintext Secret credentials or private keys.
