# Rancher RKE2 Cluster Template Helm Chart

|    Type     | Chart Version |
| :---------: | :-----------: |
| application |   `1.0.0`     |

This repository contains a Rancher cluster template Helm chart for provisioning RKE2 clusters on OpenStack.

After adding the repository to Rancher, the template will be visible in `Cluster Management -> Clusters -> Create`.

## Project Status

This chart is currently under an active cleanup and alignment effort.

- Shared chart cleanup and Dev validation are expected to happen first on `dev`.
- Prod-specific adjustments are expected to follow later on `main`.
- Long-running work tracking and progress notes are maintained in [`update-plan.md`](update-plan.md).

## Maintained Files

The main files to keep in sync during this work are:

- [`README.md`](README.md): operator-facing overview, prerequisites, and usage notes
- [`update-plan.md`](update-plan.md): shared roadmap, findings, and progress for both `dev` and `main`
- [`values.yaml`](values.yaml): chart defaults
- [`questions.yaml`](questions.yaml): Rancher UI questions and defaults
- [`templates/`](templates): rendered resources and chart logic
- [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md): environment-specific troubleshooting notes under review

## Supported Providers

### Currently Maintained
- OpenStack

`Custom` still appears in parts of the chart history, but the current templates, examples, and validation focus are centered on OpenStack.

## How This Chart Works

- The chart is installed into `fleet-default`, but it creates Rancher provisioning objects in a derived `u-<suffix>` namespace.
- The namespace suffix is derived from `cluster.config.openstack.applicationCredentialSecretName` using the `os-app-cred-<suffix>` naming convention.
- MultiPool CLI overrides can set `nodePoolCounts.master` and `nodePoolCounts.worker`; `nodepools[].quantity` remains a fallback for older UI paths.
- OpenStack node configs default `configDrive` to `true` so cloud-init can bootstrap reliably even when metadata-service discovery is inconsistent.
- The chart default Kubernetes version is `v1.33.12+rke2r2`.
- Expected input secrets in that user namespace:
  - application credential secret `os-app-cred-<suffix>` with `applicationCredentialId` and `applicationCredentialSecret`
  - SSH private key secret `openstack-privatekey` with `privatekey`
  - CCM network config secret `os-ccm-net-config` with `subnetId` and `floatingNetworkId`
- High-level generated resources:
  - `provisioning.cattle.io/v1` `Cluster`
  - `rke-machine-config.cattle.io/v1` `OpenstackConfig`
  - generated `<cluster-name>-cloud-config-<suffix>` Secret
  - OpenStack CCM manifest embedded in `additionalManifest`
- `os-ccm-net-config` is an input secret, while `<cluster-name>-cloud-config-*` is generated output.
- Current chart behavior is RKE2/OpenStack oriented, and the first validation path is a single-node RKE2 install in Dev.
- `helm lint` can fail unless required values are provided or the live lookup-backed secrets already exist.


## Prerequisites

### OpenStack

#### Dedicated Security Group

This chart expects a pre-created OpenStack security group for Kubernetes nodes.

- Recommended name: `k8s-rke2`
- Default chart value: `cluster.config.openstack.secGroups=k8s-rke2`
- Helm can attach named security groups to the node definition, but it does not create OpenStack security groups or rules.

For the current first-layer validation path, the important distinction is:

- single-node bootstrap/control-plane access uses the direct floating IP assigned to the bootstrap node
- later Kubernetes `Service` objects of type `LoadBalancer` may rely on OpenStack CCM and Octavia

Minimum baseline rule groups for the dedicated security group for the initial single-node bootstrap path are:

- all egress
- all ingress from the same security group
- Kubernetes API access on `6443` from the required management or admin source CIDRs

When using `all ingress from the same security group`, separate intra-cluster rules for `9345`, `2379-2380`, and `10250` are redundant because they are already covered by the self-referential rule.

For the current Dev environment, the observed tenant node subnet is:

- tenant node subnet: `10.0.22.0/24`

If you later validate the ingress/service `LoadBalancer` path, add NodePort access on `30000-32767` from the tenant subnet used by the Kubernetes nodes and the load balancer backend path.

The current chart enables `rke2-ingress-nginx` as a `LoadBalancer` service, so Octavia may become relevant later for ingress validation. It was not required to make the initial single-node Rancher/RKE2 bootstrap succeed.

For temporary Dev debugging only, it can also be useful to allow:

- SSH on `22`
- direct API access on `6443`

Those temporary debug rules should be treated as Dev-only and tightened or removed later.

See [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md) for background and examples.

#### Node Driver
Enable the OpenStack node driver in the Rancher Manager UI:
- Cluster Management -> Drivers -> Node Drivers -> OpenStack -> Activate

or via API:
```yaml
---
# Enable OpenStack node driver
apiVersion: management.cattle.io/v3
kind: NodeDriver
metadata:
  annotations:
    io.cattle.nodedriver/ui-field-hints: >-
      {"cacert":{"type":"multiline"},"privateKeyFile":{"type":"multiline"},"userDataFile":{"type":"multiline"}}
    lifecycle.cattle.io/create.node-driver-controller: 'true'
    privateCredentialFields: password
  finalizers:
    - controller.cattle.io/node-driver-controller
  labels:
    cattle.io/creator: norman
  managedFields:
    - apiVersion: management.cattle.io/v3
      fieldsType: FieldsV1
      fieldsV1:
        f:metadata:
          f:annotations:
            .: {}
            f:io.cattle.nodedriver/ui-field-hints: {}
            f:lifecycle.cattle.io/create.node-driver-controller: {}
            f:privateCredentialFields: {}
          f:finalizers:
            .: {}
            v:"controller.cattle.io/node-driver-controller": {}
          f:labels:
            .: {}
            f:cattle.io/creator: {}
        f:spec:
          .: {}
          f:active: {}
          f:addCloudCredential: {}
          f:builtin: {}
          f:checksum: {}
          f:description: {}
          f:displayName: {}
          f:externalId: {}
          f:uiUrl: {}
          f:url: {}
        f:status:
          .: {}
          f:appliedChecksum: {}
          f:appliedDockerMachineVersion: {}
          f:appliedURL: {}
          f:conditions: {}
      manager: rancher
      operation: Update
  name: openstack
spec:
  active: true
  addCloudCredential: false
  builtin: true
  checksum: ''
  description: ''
  displayName: openstack
  externalId: ''
  uiUrl: ''
  url: local://
```


#### Secrets
To use `OpenStack` as the cloud provider, you first have to create some secrets on the Rancher management cluster.

The current chart logic looks up some OpenStack-related secrets from a derived namespace based on `cluster.config.openstack.applicationCredentialSecretName`. The current derivation logic expects a secret name with the prefix `os-app-cred-` and resolves the namespace as `u-<suffix>`.

- For authentication via application credentials (values var: `cluster.config.openstack.applicationCredentialSecretName`) (not required when using username/password authentication):
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: os-app-cred-<user-suffix>
    namespace: u-<user-suffix>
  data:
    applicationCredentialId: <base64-encoded-application-credential-id>
    applicationCredentialSecret: <base64-encoded-application-credential-secret>
  ```

- A private SSH key for Rancher to log in to the VMs that will be created through the template (values var: `cluster.config.openstack.defaultPrivateKeyFileSecretName`):
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: openstack-privatekey
    namespace: u-<user-suffix>
  data:
    privatekey: <base64-encoded-private-key-file>
  ```

- Cloud credentials either empty (when using application credentials) or with the `password` Rancher should use to authenticate to the OpenStack API:
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    annotations:
      provisioning.cattle.io/driver: openstack
    labels:
      cattle.io/creator: norman
    name: cc-openstack-api-password
    namespace: cattle-global-data
  data:
    openstackcredentialConfig-password: ''
    #openstackcredentialConfig-password: <base64-encoded-password>
  type: Opaque
  ```
  The ID of the created cloud credentials needs to be added in `cluster.config.cloudCredentialSecretName` like `cc-openstack-api-password`.


### ETCD S3 backup
To enable ETCD backup to S3, create cloud credentials on the Rancher management cluster beforehand:
```yaml
apiVersion: v1
kind: Secret
metadata:
  labels:
    cattle.io/creator: norman
  name: cc-etcd-s3-backup
  namespace: cattle-global-data
data:
  s3credentialConfig-accessKey: <base64-encoded-s3-accessKey>
  s3credentialConfig-secretKey: <base64-encoded-s3-secretKey>
  # Optional
  # s3credentialConfig-defaultBucket: <base64-encoded-s3-defaultBucket>
  # s3credentialConfig-defaultEndpoint: <base64-encoded-s3-defaultEndpoint>
  # s3credentialConfig-defaultFolder: <base64-encoded-s3-defaultFolder>
  # s3credentialConfig-defaultRegion: <base64-encoded-s3-defaultRegion>
  # s3credentialConfig-defaultSkipSSLVerify: <base64-encoded-s3-defaultSkipSSLVerify>
type: Opaque
```
The ID of the created cloud credentials needs to be added in `cluster.config.etcd.s3.cloudCredentialName` like `cattle-global-data:cc-etcd-s3-backup`.


## Installing the Chart

### Helm Install From A Local Checkout

```sh
helm upgrade -i <cluster-name> . -n fleet-default -f values.yaml
```

### Helm Install From A Published Repository

```sh
# Replace <repo-alias> with the Helm repository alias configured in your environment.
helm repo update
helm search repo <repo-alias> --versions
helm install <cluster-name> <repo-alias>/rke2-cluster-templates --version <x.x.x> -n fleet-default -f values.yaml
```

## Helm Chart Deployment Status

```sh
helm status <cluster-name> -n fleet-default
```

## Uninstalling the Chart

```sh
helm delete <cluster-name> -n fleet-default
```


## Known Issues

### Certificate Validation Error When Creating A Downstream Cluster Via Rancher

If a downstream cluster remains in the `Updating` state and `/var/log/cloud-init-output.log` on the nodes contains:

`[FATAL]  Aborting system-agent installation due to requested strict CA verification with no CA checksum provided`

the issue is usually related to the Rancher `agentTLSMode` setting introduced in Rancher 2.8.0. Starting with Rancher 2.9+, the option defaults to `strict`, which can trigger this behavior when `ingress.tls.source` is set to `letsEncrypt` or `secret` instead of `rancher`.

Possible solutions:
1. Upload the CA Certificates to rancher: `kubectl -n cattle-system create secret generic tls-ca --from-file=cacerts.pem=./cacerts.pem`  
  This also requires the configuration option `privateCA=true` for rancher.  
  e.g.: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system --set hostname=rancher.my.org --set bootstrapPassword=admin --set ingress.tls.source=secret --set privateCA=true`

2. Set `agentTLSMode` to `system-store` in Rancher, which can be done in two ways:
   - UI setting: Global Settings -> agent-tls-mode -> Edit Setting -> System Store
   - During Install: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system ... --set agentTLSMode="system-store" ...`

Please check [Release v2.9.0 Changes](https://github.com/rancher/rancher/releases/tag/v2.9.0), [rancher helm-chart](https://github.com/rancher/rancher/blob/main/chart/values.yaml) or the documentation ([TLS Settings](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/installation-references/tls-settings.md), [Adding TLS Secrets](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/add-tls-secrets.md) and [Updating a Private CA Certificate](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/update-rancher-certificate.md#2-createupdate-the-ca-certificate-secret-object)) for more information.

### Kube API Server Audit Log Path

When configuring `audit-log-path` in `cluster.config.machineGlobalConfig.kube_apiserver_arg`, the value must be a file path. If a directory is specified instead, the API server will fail to start. When a file path is provided, the base directory of the file will be automatically created and mounted into the kube-apiserver pod.

## References
- [`rancher-ui-test-checklist.md`](rancher-ui-test-checklist.md): operator checklist for creating the validated HA cluster from the Rancher UI
- [`update-plan.md`](update-plan.md)
- [`troubleshooting/security-group-tuning.md`](troubleshooting/security-group-tuning.md)
- [Hardened Rancher Cluster Templates by Rancher Government Solutions](https://artifacthub.io/packages/helm/rancher-cluster-templates/rancher-cluster-templates)
- [rancher cluster-template-examples](https://github.com/rancher/cluster-template-examples/tree/main)
