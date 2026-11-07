# Gateway API Live Acceptance (2026-11-06)

Live acceptance of the chart `1.1.0` Gateway API/Traefik baseline and per-domain
TLS onboarding. The run took place in Dev on 2026-11-06 (UTC) and is recorded
here on 2026-11-07. It closes the default-pin Gateway/TLS live gates left by
the independent offline verification; it does not release or publish the
chart. The onboarding workflow itself is in [`gateway-api.md`](gateway-api.md).

## Source Tested

- Chart `1.1.0`, still unreleased and uncommitted: Dev worktree at `0721620`
  (`values.yaml` SHA-256 `b093deae...`, source `templates/cluster.yaml`
  SHA-256 `193d6656...`) with the Gateway work still dirty.
- No chart commit, push, tag, or artifact release was made. These results
  describe that exact worktree, not a published artifact.
- No template source changed during the run. Template-owned configuration was
  extended only by the declared test `Cluster` HTTPS listener and
  service-cleanup overrides; the application and cert-manager objects are
  described below.

## What Was Tested

- A fresh single node (`SinglePool`: one node with control-plane, etcd, and
  worker roles) and a fresh HA cluster (`MultiPool`: 3 control-plane/etcd plus
  2 workers, default flavors).
- Both used the default RKE2 `v1.35.9+rke2r1`. That is the only live-tested
  pin: `v1.33.13+rke2r2` and `v1.34.12+rke2r1` remain offline-render-only. Do
  not treat the patch matrix as fully accepted.
- Provisioning was CLI/Helm based. Rancher UI RBAC and password login were not
  tested.
- The earlier `v1.35.6+rke2r1` Cinder CSI live acceptance remains historical
  and is unchanged by this run.

## Bootstrap And Topology

- Both clusters reached `Ready` and registered all expected nodes through
  normal bootstrap convergence, with no manual repair, restart, or workaround.
  The packaged `rke2-traefik` Helm job was observed to retry twice on each
  cluster. On the single cluster the CRD ordering was observed separately: the
  job retried until the Gateway API CRDs were established, while the CRD job
  completed first try. The HA retries also included initial unschedulability
  before workers joined and converged normally; a single proven root cause for
  every HA retry was not established.
- Single node: the node received a floating IP; Traefik used host ports `80`
  and `443` with a `ClusterIP` Service, and the Gateway had no status address.
  Public reachability used the node floating IP.
- HA: nodes stayed private; Traefik ran on the two workers (no host ports) with
  one `LoadBalancer` Service. CCM created one Octavia amphora load balancer
  with NodePorts `80:31234` and `443:31506`; the Gateway status address was the
  load-balancer floating IP.
- Both clusters served the shared Gateway with exactly the `web` HTTP listener
  on internal `8000` and, after the TLS step, one `test-https` HTTPS listener
  on internal `8443`.
- Preserving one reachable external IPv4 address required running the single
  and HA stages sequentially, not concurrently. HA capacity was 20 vCPU and
  49152 MiB against a test-tenant quota of 20 vCPU and 51200 MiB; that headroom
  belongs to this test tenant and is not a universal chart requirement.

## HTTP And TLS

- Both topologies passed public HTTP: a fresh DNS A record (manual Cloudflare,
  DNS-only, not ExternalDNS) resolved to the published address and returned
  the test application's `200`.
- A namespace without the `gateway-access: public` opt-in had its HTTPRoute
  rejected with `NotAllowedByListeners`. This is asserted as route acceptance,
  not as a required `404`, because an allowed fallback route can still serve
  the path.
- Per domain: the application-owned `Certificate` and cert-manager TLS Secret
  lived in the application namespace, with a narrow named-Secret
  `ReferenceGrant`. The administrator added the HTTPS listener by merging the
  owning Rancher provisioning `Cluster`
  `spec.rkeConfig.chartValues.rke2-traefik`; the Helm-owned Gateway was not
  patched directly and the cluster-template Helm release was not upgraded.
- A second namespace reused the same domain certificate and listener through
  its own local `HTTPRoute`/`Service`; one certificate, one Secret, and one
  HTTPS listener served both namespaces.
- Production HTTPS verified with normal system trust (no `-k`): exact SNI and
  SAN, a valid production chain, and the served leaf matching the public
  certificate in the TLS Secret.
- cert-manager `1.21.3` was installed explicitly on each new test cluster only,
  after the Gateway API CRDs, with `config.gatewayAPI.enabled: true` and
  `crds.enabled: true`, reusing the existing administrator identity and fresh
  per-cluster staging/production ACME accounts. The chart still does not
  install cert-manager, issuers, or DNS credentials; the existing Dev `1.20.2`
  Cloudflare DNS-01 issuer was left unchanged.
- Certificate lifecycle: staging issuance, then exactly one controlled
  staging renewal per cluster with `cmctl 2.6.2` (Certificate revision 1 -> 2,
  new serial and fingerprint served without a workload restart), then
  production issuance on a fresh production issuer (revision 3). This proves
  controlled reissuance and certificate hot reload. It does not exercise
  automatic renewal scheduling over the certificate lifetime or a soak test,
  or a production renewal, so do not claim durable production rotation.
- The single-node stage captured one live public HTTP-01 challenge response
  (`200`, body equal to the key authorization) through the solver HTTPRoute.
  In HA, a valid production Order with `DomainVerified` and a Ready
  CertificateRequest proves ACME validation, but the direct public
  `200`/key-auth probe was not captured for either the staging or production
  challenge. That is a recording gap, not a failed validation; no extra
  issuance was attempted.
- All test DNS records are deleted. Domains, addresses, and resource IDs in
  this run are historical and are not current service URLs.

## HA Availability Qualification

Two bounded single-pod replacements were measured on the HA cluster with
continuous public HTTP and HTTPS clients at 2 requests/second per protocol:
30 s baseline, then a normal (no-force, UID-guarded) delete, then a stable
follow-up window.

- Application Pod delete: HTTP 149/149, HTTPS 148/149. One HTTPS request
  returned `502` about 0.4 s after the delete; the next HTTPS request succeeded
  1 s later, and a new application Pod was Ready in 8.62 s.
- Traefik Pod delete: HTTP 160/160 and HTTPS 160/160 with zero errors; a new
  DaemonSet Pod was Ready in 15.54 s.
- This is qualified request-level evidence, not a zero-downtime certification.
  There is no confirmed root cause for the single `502`; it was not
  investigated further and no fix was applied.
- No whole-node, control-plane, network, or Octavia amphora failure was tested.
  Octavia used a `STANDALONE` amphora, so this validates Kubernetes-level HA,
  not HA of the load-balancer appliance. The extra single-replica application
  is not an HA claim.

## CCM, CSI, And Storage

CCM and CSI were healthy on both clusters: CCM ready, CSI controller and node
plugin ready, `CSINode` objects present (`1` on single, `5` on HA), and both
StorageClasses configured as expected. No new PVC I/O, expansion, reattach, or
reclaim test was run in this acceptance; the earlier `v1.35.6+rke2r1` Cinder
CSI live acceptance remains the historical storage evidence.

## Independent Verification And Cleanup

Independent read-only reprobes passed for the current state: 46 checks on the
single cluster, 60 current checks on HA (plus cleanup-readiness checks), and 18
final cleanup checks. The important functional results are the evidence above,
not the counts.

Cleanup of both clusters completed and was independently verified:

- Tenant project: 0 servers, 0 volumes, 0 floating IPs, 0 load balancers; the
  three baseline ports are unchanged; the three security groups and their 13
  rules are unchanged.
- The onboarding namespace and Secrets, network and subnet, bootstrap keypair,
  the existing `test` cluster, and the Dev management Ingress, cert-manager,
  and issuers were preserved.
- Both test DNS names (single and HA) now return `NXDOMAIN`.
- HA teardown removed the test load balancer safely while CCM was still live:
  merge the owning test `Cluster` chartValues
  `rke2-traefik.service.enabled: false` and remove only the test HTTPS listener
  (keeping `web` and all other keys), then let the packaged Helm release delete
  the Service and let CCM request load-balancer deletion. Octavia removed the
  load balancer, VIP, service compute, and amphora as part of that LB cleanup,
  and CCM removed the floating IP, all before the template release was
  uninstalled. The test application namespaces and issuers were deleted before
  that uninstall; Rancher CAPI then removed the Kubernetes nodes, boot
  volumes, and ports. Rancher CAPI does not own the amphora or VIP. No direct
  Service delete or Octavia fallback was needed.
- This service-before-cluster teardown is for test cleanup only. It is not a
  normal operating baseline, and directly deleting the Service alone is not a
  safe substitute because Helm can recreate it.

## Not Covered

- No RKE2 version upgrade, migration, or existing-cluster configuration change.
- No RKE2 `v1.33`/`v1.34` live run; those pins remain offline-only.
- No Rancher UI RBAC or password-login test.
- No public `6443`, SSH, security-group, or quota change.
- No new PVC I/O, expansion, reattach, or reclaim test.
- No production promotion, artifact publication, or Git commit/push.
