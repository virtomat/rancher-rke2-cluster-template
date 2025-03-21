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
