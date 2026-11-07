#!/usr/bin/env python3
"""Offline semantic contract test for the OpenStack Cinder CSI bootstrap.

Renders the real chart from a temporary copy, replacing only the four `lookup`
call sites with synthetic fixtures and asserting those call sites verbatim. The
nested additionalManifest is parsed as YAML and checked for images, CCM/CSI
linkage, StorageClasses, sockets/mounts, effective RBAC via actual bindings,
probe ownership, credential absence, CCM/NGINX preservation, and fail-closed
versions. Runtime Cinder behavior is out of scope.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

CHART = Path(__file__).resolve().parents[1]
TMP_ROOT = Path("/tmp/opencode")
NAMESPACE = "u-verifier"
CLUSTER_NAME = "csi-verifier-cluster"
SENTINEL = "VERIFIER-SYNTHETIC-CREDENTIAL-SENTINEL-4f7c"

def bundle(driver, attacher, provisioner, resizer, liveness, registrar):
    return {
        "driver": f"registry.k8s.io/provider-os/cinder-csi-plugin:{driver}",
        "ccm": f"registry.k8s.io/provider-os/openstack-cloud-controller-manager:{driver}",
        "attacher": f"registry.k8s.io/sig-storage/csi-attacher:{attacher}",
        "provisioner": f"registry.k8s.io/sig-storage/csi-provisioner:{provisioner}",
        "resizer": f"registry.k8s.io/sig-storage/csi-resizer:{resizer}",
        "liveness": f"registry.k8s.io/sig-storage/livenessprobe:{liveness}",
        "registrar": f"registry.k8s.io/sig-storage/csi-node-driver-registrar:{registrar}",
    }
BUNDLES = {
    "v1.33.13+rke2r2": bundle("v1.33.0", "v4.7.0", "v5.1.0", "v1.12.0", "v2.14.0", "v2.12.0"),
    "v1.34.12+rke2r1": bundle("v1.34.0", "v4.10.0", "v5.3.0", "v1.14.0", "v2.17.0", "v2.15.0"),
    "v1.35.9+rke2r1": bundle("v1.35.0", "v4.10.0", "v5.3.0", "v1.14.0", "v2.17.0", "v2.15.0"),
}
CONTROLLER_PERMISSIONS = {
    ("", "persistentvolumes"): {"get", "list", "watch", "create", "delete", "patch"},
    ("", "persistentvolumeclaims"): {"get", "list", "watch", "update"},
    ("", "persistentvolumeclaims/status"): {"patch"},
    ("", "nodes"): {"get", "list", "watch"},
    ("", "events"): {"list", "watch", "create", "update", "patch"},
    ("", "pods"): {"get", "list", "watch"},
    ("storage.k8s.io", "csinodes"): {"get", "list", "watch"},
    ("storage.k8s.io", "volumeattachments"): {"get", "list", "watch", "patch"},
    ("storage.k8s.io", "volumeattachments/status"): {"patch"},
    ("storage.k8s.io", "storageclasses"): {"get", "list", "watch"},
    ("coordination.k8s.io", "leases"): {"get", "list", "watch", "create", "update", "delete"},
}
NODE_PERMISSIONS = {("", "events"): {"get", "list", "watch", "create", "update", "patch"}}

class Report:
    def __init__(self):
        self.checks = 0
        self.failures = []
        self.scope = ""
    def check(self, condition, message):
        self.checks += 1
        if not condition:
            self.failures.append(f"{self.scope}: {message}" if self.scope else message)
    def eq(self, actual, expected, message):
        self.check(actual == expected, f"{message}: expected {expected!r}, got {actual!r}")
def b64(value):
    return base64.b64encode(value.encode()).decode()
def named(items, name):
    return next((item for item in items or [] if item.get("name") == name), {})
def find(docs, kind, name):
    return next((d for d in docs if d.get("kind") == kind
                 and (d.get("metadata") or {}).get("name") == name), None)
def expect(report, docs, kind, name):
    document = find(docs, kind, name)
    report.check(document is not None, f"{kind}/{name} missing")
    return document or {}
def pod(workload):
    return (((workload.get("spec") or {}).get("template") or {}).get("spec") or {})
def ctr(workload, name):
    return named(pod(workload).get("containers"), name)
def mount(container, name):
    return named(container.get("volumeMounts"), name)
def env(container, name):
    return named(container.get("env"), name).get("value")
def fields(report, label, values):
    for actual, expected, field in values:
        report.eq(actual, expected, f"{label} {field}")
def tolerates(spec, key, effect):
    return any(t.get("key") == key and t.get("operator") == "Exists"
               and t.get("effect") == effect for t in spec.get("tolerations") or [])
def has_arg(container, flag):
    return flag in (container.get("args") or [])
def csi_address(container):
    for argument in container.get("args") or []:
        if argument.startswith("--csi-address="):
            value = argument.split("=", 1)[1]
            return env(container, "ADDRESS") if value == "$(ADDRESS)" else value
    return None
def socket_mount(container):
    return mount(container, "socket-dir").get("mountPath")
def check_cloud_config(report, workload, label):
    spec = pod(workload)
    host_path = named(spec.get("volumes"), "cloud-config").get("hostPath") or {}
    report.eq(host_path.get("path"), "/etc/rancher/rke2/cloud.conf", f"{label} cloud.conf path")
    report.eq(host_path.get("type"), "File", f"{label} cloud.conf hostPath type")
    for container in spec.get("containers") or []:
        mounted = mount(container, "cloud-config")
        if container.get("name") == "cinder-csi-plugin":
            report.eq(mounted.get("mountPath"), "/etc/config/cloud.conf", f"{label} mount path")
            report.check(mounted.get("readOnly") is True, f"{label} must be read-only")
        else:
            report.check(not mounted, f"{label} {container.get('name')} must not mount cloud.conf")
def check_probe(report, driver, sidecar, label):
    http_get = (driver.get("livenessProbe") or {}).get("httpGet") or {}
    report.check(bool(driver.get("livenessProbe")), f"{label} probe must be on driver")
    report.eq(http_get.get("path"), "/healthz", f"{label} probe path")
    report.eq(http_get.get("port"), "healthz", f"{label} probe port")
    report.check(not sidecar.get("livenessProbe") and not sidecar.get("readinessProbe"),
                 f"{label} sidecar must not own probes")
    report.check(has_arg(sidecar, "--health-port=9808"), f"{label} sidecar health port")
    ports = {p.get("name"): p.get("containerPort") for p in driver.get("ports") or []}
    report.eq(ports.get("healthz"), 9808, f"{label} driver healthz port")
    report.eq(csi_address(sidecar), f"{socket_mount(driver)}/csi.sock",
              f"{label} sidecar CSI socket")
def check_controller_sockets(report, workload):
    driver_socket = socket_mount(ctr(workload, "cinder-csi-plugin"))
    report.eq(driver_socket, "/csi", "controller driver socket mount")
    for name in ("csi-attacher", "csi-provisioner", "csi-resizer"):
        sidecar = ctr(workload, name)
        report.eq(socket_mount(sidecar), "/var/lib/csi/sockets/pluginproxy",
                  f"{name} socket mount")
        report.eq(csi_address(sidecar), f"{socket_mount(sidecar)}/csi.sock",
                  f"{name} CSI socket")
    liveness = ctr(workload, "liveness-probe")
    report.eq(socket_mount(liveness), driver_socket, "liveness socket mount")
    report.eq(csi_address(liveness), f"{driver_socket}/csi.sock", "liveness CSI socket")
def check_storage(report, docs):
    driver = expect(report, docs, "CSIDriver", "cinder.csi.openstack.org")
    spec = driver.get("spec") or {}
    fields(report, "CSIDriver", [
        (spec.get("attachRequired"), True, "attachRequired"),
        (spec.get("volumeLifecycleModes"), ["Persistent"], "modes"),
    ])
    classes = [d for d in docs if d.get("kind") == "StorageClass"]
    report.eq(sorted((d.get("metadata") or {}).get("name") for d in classes),
              ["cinder-delete", "cinder-retain"], "StorageClass set")
    defaults = 0
    for name, reclaim, marker in (
        ("cinder-delete", "Delete", "true"),
        ("cinder-retain", "Retain", "false"),
    ):
        sc = expect(report, docs, "StorageClass", name)
        fields(report, name, [
            (sc.get("provisioner"), "cinder.csi.openstack.org", "provisioner"),
            (sc.get("reclaimPolicy"), reclaim, "reclaimPolicy"),
            (sc.get("volumeBindingMode"), "WaitForFirstConsumer", "binding mode"),
            (sc.get("allowVolumeExpansion"), True, "expansion"),
            (((sc.get("metadata") or {}).get("annotations") or {}).get(
                "storageclass.kubernetes.io/is-default-class"), marker, "default"),
        ])
        defaults += marker == "true"
        report.check(not (sc.get("parameters") or {}), f"{name} type/AZ parameters")
        report.check("allowedTopologies" not in sc, f"{name} allowedTopologies")
    report.eq(defaults, 1, "exactly one default StorageClass")
def check_controller(report, docs, images):
    workload = expect(report, docs, "Deployment", "cinder-csi-controller")
    spec = pod(workload)
    fields(report, "controller", [
        ((workload.get("spec") or {}).get("replicas"), 1, "replicas"),
        (spec.get("serviceAccountName"), "csi-cinder-controller-sa", "serviceAccount"),
    ])
    for key, effect in (("node-role.kubernetes.io/control-plane", "NoSchedule"),
                        ("node-role.kubernetes.io/etcd", "NoExecute")):
        report.check(tolerates(spec, key, effect), f"controller toleration {key}")
    driver = ctr(workload, "cinder-csi-plugin")
    fields(report, "controller driver", [
        (driver.get("image"), images["driver"], "image"),
        (env(driver, "CLUSTER_NAME"), CLUSTER_NAME, "cluster name"),
    ])
    report.check(has_arg(driver, "--provide-node-service=false"), "controller node service flag")
    report.check(not has_arg(driver, "--provide-controller-service=false"),
                 "controller must provide controller service")
    for name, key in (("csi-attacher", "attacher"), ("csi-provisioner", "provisioner"),
                      ("csi-resizer", "resizer"), ("liveness-probe", "liveness")):
        sidecar = ctr(workload, name)
        report.check(bool(sidecar), f"controller {name} missing")
        report.eq(sidecar.get("image"), images[key], f"controller {name} image")
    report.check(has_arg(ctr(workload, "csi-provisioner"), "--default-fstype=ext4"),
                 "provisioner ext4 default")
    check_controller_sockets(report, workload)
    check_probe(report, driver, ctr(workload, "liveness-probe"), "controller")
    check_cloud_config(report, workload, "controller")
def check_node(report, docs, images):
    workload = expect(report, docs, "DaemonSet", "cinder-csi-node")
    spec = pod(workload)
    fields(report, "node", [
        (spec.get("serviceAccountName"), "csi-cinder-node-sa", "serviceAccount"),
        ((spec.get("nodeSelector") or {}).get("kubernetes.io/os"), "linux", "OS selector"),
        (spec.get("hostNetwork"), True, "hostNetwork"),
        (spec.get("dnsPolicy"), "ClusterFirstWithHostNet", "dnsPolicy"),
    ])
    report.check("node.kubernetes.io/control-plane" not in (spec.get("nodeSelector") or {}),
                 "node plugin must also run on masters")
    report.check(any(t.get("operator") == "Exists" and not t.get("key")
                     for t in spec.get("tolerations") or []), "node tolerates all taints")
    driver = ctr(workload, "cinder-csi-plugin")
    fields(report, "node driver", [
        (driver.get("image"), images["driver"], "image"),
        ((driver.get("securityContext") or {}).get("privileged"), True, "privileged"),
        (mount(driver, "kubelet-dir").get("mountPath"), "/var/lib/kubelet", "kubelet mount"),
        (mount(driver, "kubelet-dir").get("mountPropagation"), "Bidirectional", "kubelet propagation"),
        (mount(driver, "dev").get("mountPath"), "/dev", "dev mount"),
        (mount(driver, "dev").get("mountPropagation"), "HostToContainer", "dev propagation"),
    ])
    report.check(has_arg(driver, "--provide-controller-service=false"),
                 "node controller service flag")
    report.check(not has_arg(driver, "--provide-node-service=false"),
                 "node must provide node service")
    for name, path in (
        ("socket-dir", "/var/lib/kubelet/plugins/cinder.csi.openstack.org"),
        ("registration-dir", "/var/lib/kubelet/plugins_registry"),
    ):
        host_path = named(spec.get("volumes"), name).get("hostPath") or {}
        report.eq(host_path.get("path"), path, f"node {name} hostPath")
    registrar = ctr(workload, "node-driver-registrar")
    report.eq(registrar.get("image"), images["registrar"], "registrar image")
    report.eq(mount(registrar, "registration-dir").get("mountPath"), "/registration",
              "registrar registration mount")
    socket_host = (named(spec.get("volumes"), "socket-dir").get("hostPath") or {}).get("path")
    report.eq(env(registrar, "DRIVER_REG_SOCK_PATH"), f"{socket_host}/csi.sock",
              "registrar host registration path")
    report.eq(csi_address(registrar), f"{socket_mount(driver)}/csi.sock", "registrar CSI socket")
    liveness = ctr(workload, "liveness-probe")
    report.eq(liveness.get("image"), images["liveness"], "node liveness image")
    report.eq(socket_mount(liveness), socket_mount(driver), "node liveness socket mount")
    report.eq(csi_address(liveness), f"{socket_mount(driver)}/csi.sock", "node liveness CSI socket")
    check_probe(report, driver, liveness, "node")
    check_cloud_config(report, workload, "node")
def effective_rbac(report, docs, service_account):
    accounts = {name for name in ((d.get("metadata") or {}).get("name")
                                  for d in docs if d.get("kind") == "ServiceAccount")}
    cluster_roles = {(d.get("metadata") or {}).get("name"): d
                     for d in docs if d.get("kind") == "ClusterRole"}
    roles = {(d.get("metadata") or {}).get("name"): d
             for d in docs if d.get("kind") == "Role"}
    granted, used_roles, bindings = {}, [], 0
    for binding in docs:
        if binding.get("kind") not in {"RoleBinding", "ClusterRoleBinding"}:
            continue
        subjects = binding.get("subjects") or []
        if not any(s.get("name") == service_account for s in subjects):
            continue
        bindings += 1
        binding_name = (binding.get("metadata") or {}).get("name")
        reference = binding.get("roleRef") or {}
        role = (cluster_roles.get(reference.get("name"))
                if reference.get("kind") == "ClusterRole"
                else roles.get(reference.get("name")) if reference.get("kind") == "Role" else None)
        report.check(role is not None, f"{service_account} binding {binding_name} unresolved")
        if role:
            used_roles.append(role)
            for rule in role.get("rules") or []:
                for group in rule.get("apiGroups") or []:
                    for resource in rule.get("resources") or []:
                        granted.setdefault((group, resource), set()).update(rule.get("verbs") or [])
        for subject in subjects:
            report.eq(subject.get("kind"), "ServiceAccount", f"{binding_name} subject kind")
            report.eq(subject.get("namespace"), "kube-system", f"{binding_name} subject namespace")
            report.check(subject.get("name") in accounts, f"{binding_name} unknown subject")
        if binding.get("kind") == "RoleBinding":
            report.eq((binding.get("metadata") or {}).get("namespace"), "kube-system",
                      f"{binding_name} namespace")
        else:
            report.eq(reference.get("kind"), "ClusterRole", f"{binding_name} roleRef kind")
    report.check(bindings > 0, f"{service_account} has no bindings")
    return granted, used_roles
def check_permissions(report, granted, required, label):
    for (group, resource), verbs in required.items():
        effective = granted.get((group, resource), set())
        if "*" in effective:
            effective = set(verbs)
        report.check(verbs <= effective, f"{label} missing {group}/{resource}")
    return granted
def check_rbac(report, docs):
    controller, controller_roles = effective_rbac(report, docs, "csi-cinder-controller-sa")
    node, node_roles = effective_rbac(report, docs, "csi-cinder-node-sa")
    check_permissions(report, controller, CONTROLLER_PERMISSIONS, "controller SA")
    check_permissions(report, node, NODE_PERMISSIONS, "node SA")
    report.check(("coordination.k8s.io", "leases") not in node, "node SA lease access")
    report.check(not (node.get(("", "persistentvolumes"), set()) & {"create", "delete"}),
                 "node SA PV write access")
    for role in controller_roles + node_roles:
        role_name = (role.get("metadata") or {}).get("name")
        for rule in role.get("rules") or []:
            resources = rule.get("resources") or []
            report.check("*" not in resources, f"{role_name} wildcard resource")
            report.check(not any("secret" in r for r in resources), f"{role_name} Secret access")
            report.check(not any("snapshot" in r for r in resources)
                         and not any("snapshot" in g for g in rule.get("apiGroups") or []),
                         f"{role_name} snapshot access")
def check_ccm_addons(report, docs, cluster, images, masters):
    ccm = expect(report, docs, "Deployment", "openstack-cloud-controller-manager")
    report.eq(ctr(ccm, "openstack-cloud-controller-manager").get("image"),
              images["ccm"], "CCM image")
    markers = [find(docs, "CSIDriver", "cinder.csi.openstack.org"),
               find(docs, "StorageClass", "cinder-delete"),
               find(docs, "Deployment", "cinder-csi-controller"),
               find(docs, "DaemonSet", "cinder-csi-node")]
    indices = [docs.index(m) for m in markers if m in docs]
    report.check(ccm in docs and indices and docs.index(ccm) < min(indices),
                 "Cinder CSI must follow the CCM manifest")
    rke_config = (cluster.get("spec") or {}).get("rkeConfig") or {}
    chart_values = rke_config.get("chartValues") or {}
    report.check("rke2-ingress-nginx" not in chart_values,
                 "legacy rke2-ingress-nginx chartValues must be absent")
    traefik = chart_values.get("rke2-traefik") or {}
    report.check(bool(traefik), "packaged rke2-traefik chartValues missing")
    report.eq(((traefik.get("providers") or {}).get("kubernetesGateway") or {}).get(
        "enabled"), True, "Traefik Gateway provider")
    report.eq((rke_config.get("machineGlobalConfig") or {}).get("ingress-controller"),
              ["traefik"], "RKE2 ingress-controller selection")
    report.check(not any(d.get("kind") in {"Gateway", "GatewayClass"} for d in docs),
                 "additionalManifest must not duplicate Gateway/GatewayClass objects")
def check_cluster(report, documents, version, masters):
    images = BUNDLES[version]
    clusters = [d for d in documents if d.get("kind") == "Cluster"]
    report.eq(len(clusters), 1, "Cluster count")
    if not clusters:
        return
    cluster = clusters[0]
    report.eq((cluster.get("metadata") or {}).get("name"), CLUSTER_NAME, "Cluster name")
    report.eq((cluster.get("spec") or {}).get("kubernetesVersion"), version, "Cluster version")
    master_pool = next((p for p in (cluster.get("spec") or {}).get("rkeConfig", {}).get(
        "machinePools") or [] if p.get("name") == "master"), {})
    report.eq(master_pool.get("quantity"), masters, "master count")
    manifest = (cluster.get("spec") or {}).get("rkeConfig", {}).get("additionalManifest")
    report.check(isinstance(manifest, str) and bool(manifest.strip()), "additionalManifest")
    if not isinstance(manifest, str):
        return
    report.check("{{" not in manifest, "manifest retains template directives")
    report.check(SENTINEL not in manifest and b64(SENTINEL) not in manifest,
                 "credential sentinel leaked into additionalManifest")
    embedded = [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]
    report.check(not any(d.get("kind") == "Secret" for d in embedded),
                 "additionalManifest contains a Secret")
    check_storage(report, embedded)
    check_controller(report, embedded, images)
    check_node(report, embedded, images)
    check_rbac(report, embedded)
    check_ccm_addons(report, embedded, cluster, images, masters)
LOOKUP_SUBSTITUTIONS = (
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $appCredSecretName }}',
     '{{- $secret := include "csi-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $appCredSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $ccmNetConfigSecretName }}',
     '{{- $secret := include "csi-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $ccmNetConfigSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $environment := lookup "v1" "ConfigMap" $namespace '
     '"rke2-openstack-environment" }}',
     '{{- $environment := include "csi-verifier.fixture" (dict "root" $ "key" '
     '(printf "ConfigMap/%s/rke2-openstack-environment" $namespace)) | fromYaml }}'),
    ("templates/nodeconfig-openstack.yaml",
     '{{- $pkSecret := lookup "v1" "Secret" $namespace $pkSecretName }}',
     '{{- $pkSecret := include "csi-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $pkSecretName)) | fromYaml }}'),
)

FIXTURE_TEMPLATE = """{{- define "csi-verifier.fixture" -}}
{{- $fixtures := .root.Values.__csiVerifierFixtures | default dict -}}
{{- if not (hasKey $fixtures .key) -}}{{- fail (printf "missing csi verifier fixture %s" .key) -}}{{- end -}}
{{- toYaml (index $fixtures .key) -}}
{{- end -}}
"""

def fixture_values():
    secret = f"Secret/{NAMESPACE}/"
    return {"__csiVerifierFixtures": {
        secret + "os-app-cred-verifier": {"data": {
            "applicationCredentialId": b64("fixture-id"),
            "applicationCredentialSecret": b64(SENTINEL)}},
        secret + "os-ccm-net-config": {"data": {
            "subnetId": b64("fixture-subnet"),
            "floatingNetworkId": b64("fixture-network")}},
        secret + "openstack-privatekey": {"data": {
            "privatekey": b64("fixture-private-key-not-real")}},
        f"ConfigMap/{NAMESPACE}/rke2-openstack-environment": {"data": {
            "authUrl": "https://identity.invalid/v3", "region": "fixture-region"}},
    }}
def build_harness(workdir):
    chart = workdir / "chart"
    shutil.copytree(CHART, chart, ignore=shutil.ignore_patterns(
        ".git", ".idea", "__pycache__", "*.tgz"))
    templates = [p for p in (chart / "templates").rglob("*") if p.is_file()]
    if sum(p.read_text().count("lookup ") for p in templates) != len(LOOKUP_SUBSTITUTIONS):
        raise RuntimeError("lookup call-site count drift")
    edited = {}
    for relative_path, original, replacement in LOOKUP_SUBSTITUTIONS:
        path = chart / relative_path
        text = edited.setdefault(path, path.read_text())
        if text.count(original) != 1:
            raise RuntimeError(f"lookup call-site drift in {relative_path}")
        edited[path] = text.replace(original, replacement)
    for path, text in edited.items():
        path.write_text(text)
    if any("lookup " in p.read_text() for p in templates):
        raise RuntimeError("lookup fixture replacement incomplete")
    (chart / "templates" / "zz-csi-verifier-fixtures.tpl").write_text(FIXTURE_TEMPLATE)
    values = workdir / "fixtures.yaml"
    values.write_text(yaml.safe_dump(fixture_values(), sort_keys=True))
    return chart, values
def run_helm(chart, values, version, masters):
    command = ["helm", "template", "csi-verifier", str(chart), "--namespace", NAMESPACE,
               "--values", str(values), "--set-string", f"cluster.name={CLUSTER_NAME}",
               "--set-string",
               "cluster.config.openstack.applicationCredentialSecretName=os-app-cred-verifier",
               "--set-string", f"cluster.config.kubernetesVersion={version}"]
    if masters != 1:
        command.extend(["--set", f"nodePoolCounts.master={masters}"])
    return subprocess.run(command, capture_output=True, text=True, timeout=120)
def render(report, chart, values, version, masters):
    completed = run_helm(chart, values, version, masters)
    if completed.returncode != 0:
        report.check(False, "helm template failed: " + (completed.stderr.strip() or "no stderr"))
        return
    try:
        documents = [d for d in yaml.safe_load_all(completed.stdout) if isinstance(d, dict)]
    except yaml.YAMLError as error:
        report.check(False, f"rendered chart YAML: {error}")
        return
    report.check(any(SENTINEL in yaml.safe_dump(d) for d in documents
                     if d.get("kind") == "Secret"),
                 "synthetic sentinel was not rendered")
    check_cluster(report, documents, version, masters)
def check_schema(report):
    try:
        schema = json.loads((CHART / "values.schema.json").read_text())
        versions = schema["properties"]["cluster"]["properties"]["config"]["properties"][
            "kubernetesVersion"]["enum"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        report.check(False, f"schema version contract: {error}")
        return
    report.eq(sorted(versions), sorted(BUNDLES), "schema supported versions")
def check_unsupported(report, chart, values):
    for version in ("v1.32.1+rke2r1", "v1.33.12+rke2r2", "v1.34.6+rke2r1",
                    "v1.35.6+rke2r1"):
        completed = run_helm(chart, values, version, 1)
        report.check(completed.returncode != 0,
                     f"unsupported version {version} must fail rendering")
        report.check(all(supported in completed.stderr for supported in BUNDLES),
                     f"unsupported-version error for {version} lists supported versions")
def check_helper(report, workdir):
    mini = workdir / "helper-chart"
    (mini / "templates").mkdir(parents=True)
    (mini / "Chart.yaml").write_text("apiVersion: v2\nname: csi-helper\nversion: 0.0.1\n")
    shutil.copy(CHART / "templates/_helpers.tpl", mini / "templates/_helpers.tpl")
    (mini / "templates/probe.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: csi-image-probe\n"
        "data:\n  bundle: |\n"
        '{{ include "rancher-cluster-templates.openstackCinderCsiImages" . | indent 4 }}\n')
    completed = subprocess.run(
        ["helm", "template", "helper-check", str(mini), "--set-string",
         "cluster.config.kubernetesVersion=v1.32.1+rke2r1"],
        capture_output=True, text=True, timeout=120)
    report.check(completed.returncode != 0, "CSI helper must fail closed")
    report.check("Unsupported RKE2 Kubernetes version" in completed.stderr
                 and "OpenStack Cinder CSI" in completed.stderr, "CSI helper error")
def main():
    if shutil.which("helm") is None:
        print("FAIL: helm is required but not found on PATH", file=sys.stderr)
        return 1
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    report = Report()
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
        workdir = Path(temporary)
        try:
            chart, values = build_harness(workdir)
        except RuntimeError as error:
            print(f"FAIL: offline render harness: {error}", file=sys.stderr)
            return 1
        report.scope = "schema"
        check_schema(report)
        for version in BUNDLES:
            for masters in (1, 3):
                report.scope = f"{version} masters={masters}"
                render(report, chart, values, version, masters)
        report.scope = "unsupported-version"
        check_unsupported(report, chart, values)
        report.scope = "helper-fail-closed"
        check_helper(report, workdir)
    for failure in report.failures:
        print(f"  - {failure}")
    renders = len(BUNDLES) * 2
    if report.failures:
        print(f"FAILED: {renders} renders, {report.checks} checks")
        return 1
    print(f"PASS: {renders} renders ({len(BUNDLES)} versions x 1/3 masters), "
          f"{report.checks} checks")
    return 0
if __name__ == "__main__":
    sys.exit(main())
