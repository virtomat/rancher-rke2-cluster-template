# Production Live Acceptance (2026-11-08/09)

Production acceptance of chart `1.1.0` Gateway/Traefik, per-domain TLS, and Cinder
CSI on fresh production clusters, run 2026-11-08 through cleanup 2026-11-09 (UTC)
and recorded 2026-11-09. It closes the default-pin production gates without
creating a tag or artifact. The Dev records in
[`gateway-live-acceptance.md`](gateway-live-acceptance.md) remain separate history.

## Source And Publication

- Chart `1.1.0` source `9fdcace52fded6b87853c38c3c56f333793a8c1e`; `main` was
  fast-forwarded from `af5797e` on 2026-11-08T22:03:30Z and equals `dev`.
- The git-backed production Rancher `ClusterRepo` catalog auto-reindexed `1.1.0`
  from that `main` commit; its gate completed at 2026-11-08T22:10:01Z.
- No CI pipeline, semantic-version tag, or Harbor/OCI artifact release exists;
  "published" means the Git catalog source baseline, not a packaged artifact.
- Provisioning used CLI/Helm with chart `1.1.0`; the catalog commit matched the install tree.
  No Rancher-UI RBAC/password test and no tenant upgrade/migration; both clusters were fresh.

## Environment And Topology

- Production Rancher `2.14.1` supports Kubernetes 1.33-1.35
  ([support matrix](https://www.suse.com/suse-rancher/support-matrix/all-supported-versions/rancher-v2-14-1/));
  KDM lists all three pins ([data.json](https://releases.rancher.com/kontainer-driver-metadata/release-v2.14/data.json)),
  but only default `v1.35.9+rke2r1` was live-tested; `v1.33.13+rke2r2` and
  `v1.34.12+rke2r1` remain offline-render-only.
- `SinglePool` was one node carrying control-plane, etcd, and worker roles.
  `MultiPool` was 3 control-plane/etcd nodes plus 2 workers.
- Nodes used Ubuntu 24.04 images, 40 GiB boot Cinder volumes, availability zone
  `nova`, and the production default Cinder volume type `__DEFAULT__`. No custom
  volume type, AZ, or CSI configuration was introduced for the test.
- The tenant quota for this test was scoped to 20 vCPU, 51200 MiB, and 1 floating
  IP. HA used 20 vCPU and 49152 MiB. Stages ran sequentially and were cleaned
  between them; this is a scoped test-tenant observation, not a claim about global
  production capacity or scarcity.
- Single: node floating IP, Traefik `ClusterIP` with host ports `80`/`443`, no
  Gateway address. HA: private nodes, Traefik DaemonSet on the two workers with no
  host ports, one Octavia `LoadBalancer` publishing `80`/`443` through worker
  NodePorts, and the load-balancer floating IP as the Gateway address.
- Bootstrap reached Ready in about 419 s (single) and 802 s (HA) through normal
  packaged asynchronous Helm retries, with no manual repair or restart.
- No existing production Ingress, issuer, ExternalDNS, security-group, or quota changed.

## HTTP Routes And TLS

- Both topologies returned public HTTP `200`; an unknown host returned `404`.
- Namespace opt-in was enforced. Routes in an opted-in namespace were `Accepted`;
  a route in an unlabelled namespace was rejected with `NotAllowedByListeners`.
  That negative case is route acceptance, not a required `404`, because an allowed
  fallback route may still serve the path with `200`.
- Per domain: one application-owned `Certificate` and cert-manager TLS Secret in
  the application namespace with a narrow named-Secret `ReferenceGrant`. The HTTPS
  listener was merged through the owning Rancher provisioning `Cluster`
  chartValues, not patched directly onto the Helm-owned Gateway. A second
  namespace served its own backend route through the same certificate/listener.
- cert-manager `1.21.3` was installed manually on each new downstream cluster
  only, after the Gateway API CRDs, with Gateway API support enabled.
- Fresh staging and production ACME accounts were created per cluster. Public
  HTTP-01 probes returned `200` with matching key authorization on single and HA,
  for both staging and production issuance.
- One controlled staging renewal per cluster (revision 1 -> 2) served a new serial
  and fingerprint without an application or Traefik restart. Production issuance
  followed as revision 3 with normal system trust, exact SAN, and served leaf
  matching the public `tls.crt`.
- This is not evidence for natural renewal scheduling, a production renewal, or a
  soak test; no default DNS or TLS installation is implied.

## Storage

- Both topologies created two 1 GiB PVCs that stayed `Pending` under
  WaitForFirstConsumer. A claim omitting `storageClassName` defaulted to
  `cinder-delete`; the explicit claim used `cinder-retain`.
- Synthetic markers and 1 MiB files were written and re-read with matching SHA-256
  hashes; no production user data was used. Single-node pod replacement preserved
  both hashes. HA worker A -> B movement took 76.2 s total (49.9 s detach, 25.6 s
  attach) and preserved the hashes.
- Online expansion from 1 GiB to 2 GiB completed in 16.1 s (single) and 16.2 s
  (HA); the filesystem grew from 996780 to 2028392 KiB, with the same Pod UID and
  zero restarts.
- A 1.2 GiB proof file (1288699904 bytes) was written and removed, verifying
  usable capacity through exact size and `df` usage. Its SHA-256 was not captured
  because the exec websocket timed out; the 1 MiB hashes were fully verified.
- `cinder-delete` removed PVC, PV, and Cinder volume (all `404`). `cinder-retain`
  left the PV `Released` and the volume unattached, observed twice over 35 s,
  followed by manual exact-owned PV and volume cleanup. Automatic rebinding is not
  claimed. No snapshot, RWX, backend, custom volume type, AZ, or CSI change is in
  scope.
- Qualification: the first single-node probe pod used `spec.nodeName`, bypassing
  scheduler-driven WaitForFirstConsumer binding. It was corrected to a hostname
  node selector before any data or Cinder volume existed. That was a test-harness
  correction, not a change to the template.

## HA Availability Qualification

- Each replacement was a separate bounded pod replacement with its own 30 s
  baseline and 30 s stable post-delete window: application Pod first, then Traefik
  Pod, at 2 requests/second per protocol with a 3 s timeout and no retry; deletes
  were UID-guarded.
- Independent recomputation of the raw requests: application HTTP 143/143 and
  HTTPS 143/143; Traefik HTTP 133/133 and HTTPS 133/133; combined 552/552 with
  zero failures.
- The application Pod and both ready endpoints recovered 10.59 s after the DELETE
  response. Traefik Pod, DaemonSet, and endpoint readiness recovered in 4.87 s;
  full load-balancer health was confirmed 6.8 s after the response (6.88 s after
  the request). The 4.87 s figure is readiness only, not full recovery.
- This is qualified Kubernetes-level pod-replacement behavior, not a zero-downtime
  guarantee. No whole-node, control-plane, network, or Octavia amphora failure was
  tested.
- Amphora topology is unknown: production tenant enumeration returned `403`; the
  Dev `STANDALONE` observation is not carried over. The extra single-replica
  application is not an HA claim.

## Independent Verification

- Independent re-verification passed the current single-node state (40 checks),
  corrected HA state (133 checks), and final cleanup (35 checks); an independent
  re-parse of the availability request logs matched the reported totals and zero
  failures. Counts support the functional results rather than replacing them.
- Live checks confirm `cinder-delete` is the sole default StorageClass and
  `cinder-retain` is non-default; no template change was needed.
- The management ConfigMap remained present and preserved throughout; no
  configuration was removed.

## Cleanup

- All 6 test VMs, 6 boot volumes, 4 CSI test volumes, 2 floating IPs, and 1 load
  balancer were removed from the target host project. Both test DNS names now
  return `NXDOMAIN`.
- HA teardown set `rke2-traefik.service.enabled: false` in the owning test
  Cluster chartValues and removed only the test HTTPS listener. The packaged Helm
  release then deleted the Service, CCM requested load-balancer and floating-IP
  deletion while CCM was still live, and Rancher CAPI removed the Kubernetes nodes
  and boot volumes. No forced fallback was needed.
- Preserved: 2 pre-existing ports, 3 security groups with their 13 exact rule IDs,
  the onboarding 3 Secrets and 1 ConfigMap, network, subnet, keypair, and
  management health.
- Octavia load-balancer, floating-IP, and VIP absence was verified through the
  tenant API; provider-internal amphora state was not admin-audited, so no global
  service-project or amphora absence is claimed. Foreign ports returned `404` only
  within authorized tenant visibility, with no ownership asserted.

## Not Covered

- No live run on `v1.33.13+rke2r2` or `v1.34.12+rke2r1`; both remain
  offline-render-only. No Rancher UI RBAC/password, existing-cluster
  upgrade/migration, natural or production renewal, or soak test.
- No snapshot/RWX, custom volume type, AZ variation, whole-node, control-plane,
  network, amphora-failure, or zero-downtime test.
- No secret, credential, production data, or private key was persisted; scratch
  evidence is non-secret and retains historical names/IDs not reproduced here.
