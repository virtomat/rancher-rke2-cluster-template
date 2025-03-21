# rke2 Cluster Templates Helm Chart

|    Type     | Chart Version |
| :---------: | :-----------: |
| application |   `v2.0.1`    |


This template is specifically tested within rancher.

After adding the repository to rancher, the template will be visible in Cluster Management -> Clusters -> Create.

## Supported Providers

### Currently Available
- OpenStack
- Custom


## Prerequisites

### OpenStack
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
To use `OpenStack` as `cloudprovider` you first have to create some secrets on your Rancher manager.
- For authentication via `Application Credentials` (values var: `secretApplicationCredentials`) (not required when using username/password authentication):  
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: openstack-application-credentials
    namespace: fleet-default
  data:
    applicationCredentialId: <base64-encoded-application-credential-id>
    applicationCredentialSecret: <base64-encoded-application-credential-secret>
  ```

- A `private SSH Key` for rancher to login into the VMs that will be created through the template (values var: `secretprivateKeyFile`):  
  ```yaml
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: openstack-privatekey
    namespace: fleet-default
  data:
    privateKeyFile: <base64-encoded-private-key-file>
  ```

- `Cloud Credentials` either empty (when using Application Credentials) or with the `password` rancher should use to authenticate ot the OpenStack API:  
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
  The ID of the created `Cloud Credentials` needs to be added in `Values.cluster.config.cloudCredentialSecretName` like `cc-openstack-api-password`.


### ETCD S3 backup
To enable backup the ETCD to an S3 it is required to create `Cloud Credentials` on the rancher cluster beforehand:
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
The ID of the created `Cloud Credentials` needs to be added in `Values.cluster.config.etcd.s3.cloudCredentialName` like `cattle-global-data:cc-etcd-s3-backup`.


## Installing the Chart

### Helm Install via Repository

```sh
# Install latest Version
helm repo update
helm upgrade -i <cluster-name> ict-platform/rke2-cluster-templates -n fleet-default -f values.yaml
```

```sh
# List available versions
helm search repo ict-platform --versions
# Install specific version
helm install <cluster-name> ict-platform/rke2-cluster-templates --version <x.x.x> -n fleet-default -f values.yaml

```

## Helm Chart Deployment Status

```sh
helm status <cluster-name> -n fleet-default
```

## Uninstalling the Chart

```sh
helm delete <cluster-name> -n fleet-default
```


## Known issues
### Certificate Validation error when creating downstream cluster via rancher
Downstream cluster is created via rancher doesn't leave the `Updating` state and `/var/log/cloud-init-output.log` on the nodes contains:  
`[FATAL]  Aborting system-agent installation due to requested strict CA verification with no CA checksum provided`

Reason for this issue is that rancher version 2.8.0 introduced the configuration option `agentTLSMode`.  
When starting on a rancher version 2.9+ the option is set to `strict` by default, potentially resulting in this issue.  
This should only happen when the configuration `ingress.tls.source` is set to `letsEncrypt` or `secret` instead of `rancher`(default).

Possible solutions:
1. Upload the CA Certificates to rancher: `kubectl -n cattle-system create secret generic tls-ca --from-file=cacerts.pem=./cacerts.pem`  
  This also requires the configuration option `privateCA=true` for rancher.  
  e.g.: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system --set hostname=rancher.my.org --set bootstrapPassword=admin --set ingress.tls.source=secret --set privateCA=true`

2. Set `agentTLSMode` to `system-store` in rancher, which can be done in two ways:
  - UI setting: Global Settings -> agent-tls-mode -> Edit Setting -> System Store
  - During Install: `helm install rancher rancher-<CHART_REPO>/rancher --namespace cattle-system ... --set agentTLSMode="system-store" ...`

Please check [Release v2.9.0 Changes](https://github.com/rancher/rancher/releases/tag/v2.9.0), [rancher helm-chart](https://github.com/rancher/rancher/blob/main/chart/values.yaml) or the documentation ([TLS Settings](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/installation-references/tls-settings.md), [Adding TLS Secrets](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/add-tls-secrets.md) and [Updating a Private CA Certificate](https://github.com/rancher/rancher-docs/blob/main/docs/getting-started/installation-and-upgrade/resources/update-rancher-certificate.md#2-createupdate-the-ca-certificate-secret-object)) for more information.

### Kube API Server Audit log path
When configuring `audit-log-path` in `cluster.config.machineGlobalConfig.kube_apiserver_arg`, the value must be a file path. If a directory is specified instead, the API server will fail to start. When a file path is provided, the base directory of the file will be automatically created and mounted into the kube-apiserver pod.

## References
- [Hardened Rancher Cluster Templates by Rancher Government Solutions](https://artifacthub.io/packages/helm/rancher-cluster-templates/rancher-cluster-templates)
- [rancher cluster-template-examples](https://github.com/rancher/cluster-template-examples/tree/main)
