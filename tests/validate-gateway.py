#!/usr/bin/env python3
"""Offline semantic contract test for the packaged Traefik Gateway baseline.

Renders the real chart from a temporary copy, replacing only the four `lookup`
call sites with synthetic fixtures. It verifies the three-version RKE2 matrix,
`ingress-controller: [traefik]`, the absence of legacy NGINX chartValues, the
packaged rke2-traefik GatewayClass/Gateway/listener/provider contract, single
master vs HA publication topology, hostPort clearing, merge preservation of
administrator-added listeners, fail-closed old pins, and invalid topology.

When local copies of the packaged rke2-traefik chart are available in the
offline package cache (RKE2_TRAEFIK_CHART_DIR, default
/tmp/opencode/gateway-evaluation), the generated chartValues are also rendered
against the actual chart to prove that Gateway-only providers render, the
websecure entrypoint stays non-TLS until an HTTPS listener supplies
certificateRefs, `hostPort: null` clears the packaged 80/443 defaults in HA, and
the Service still publishes 80/443. Pass --require-packaged-charts to make a
missing package a hard failure instead of an explicit skip. No cluster,
credentials, CRDs, network access, or downloaded charts are required.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

CHART = Path(__file__).resolve().parents[1]
TMP_ROOT = Path("/tmp/opencode")
NAMESPACE = "u-verifier"
CLUSTER_NAME = "gateway-verifier-cluster"
PACKAGE_CACHE = Path(os.environ.get(
    "RKE2_TRAEFIK_CHART_DIR", "/tmp/opencode/gateway-evaluation"))
PACKAGED_CHARTS = {
    "v1.33.13+rke2r2": PACKAGE_CACHE / "rke2-traefik-40.1.009.tgz",
    "v1.34.12+rke2r1": PACKAGE_CACHE / "rke2-traefik-40.1.013.tgz",
    "v1.35.9+rke2r1": PACKAGE_CACHE / "rke2-traefik-40.1.013.tgz",
}
IMAGES = {
    "v1.33.13+rke2r2": ("v1.33.0", "v1.33.0"),
    "v1.34.12+rke2r1": ("v1.34.0", "v1.34.0"),
    "v1.35.9+rke2r1": ("v1.35.0", "v1.35.0"),
}
OLD_PINS = ("v1.32.1+rke2r1", "v1.33.12+rke2r2", "v1.34.6+rke2r1",
            "v1.35.6+rke2r1")
ADD_HTTPS_LISTENER = [
    "--set-json",
    'cluster.config.chartValues.rke2-traefik.gateway.listeners.websecure='
    '{"port":8443,"protocol":"HTTPS","certificateRefs":[{"name":'
    '"dummy-tls","namespace":"kube-system"}],"namespacePolicy":{"from":'
    '"Selector","selector":{"matchLabels":{"gateway-access":"public"}}}}',
]


class Report:
    def __init__(self):
        self.checks = 0
        self.failures = []
        self.scope = ""

    def check(self, condition, message):
        self.checks += 1
        if not condition:
            prefix = f"{self.scope}: " if self.scope else ""
            self.failures.append(prefix + message)

    def eq(self, actual, expected, message):
        self.check(actual == expected,
                   f"{message}: expected {expected!r}, got {actual!r}")
def b64(value):
    return base64.b64encode(value.encode()).decode()
def get(mapping, *keys):
    for key in keys:
        if isinstance(mapping, dict):
            mapping = mapping.get(key)
        elif isinstance(mapping, list) and isinstance(key, int) \
                and 0 <= key < len(mapping):
            mapping = mapping[key]
        else:
            return None
    return mapping
def find(docs, kind, name):
    return next((d for d in docs if d.get("kind") == kind
                 and get(d, "metadata", "name") == name), None)
def port_of(container, name):
    return next((p for p in container.get("ports") or []
                 if p.get("name") == name), {})


def check_cluster(report, cluster, version, masters):
    rke = get(cluster, "spec", "rkeConfig") or {}
    report.eq(get(rke, "machineGlobalConfig", "ingress-controller"),
              ["traefik"], "RKE2 ingress-controller selection")
    chart_values = rke.get("chartValues") or {}
    report.check("rke2-ingress-nginx" not in chart_values,
                 "legacy rke2-ingress-nginx chartValues must be absent")
    traefik = chart_values.get("rke2-traefik") or {}
    report.check(bool(traefik), "packaged rke2-traefik chartValues missing")
    if not traefik:
        return
    fields = [
        (get(traefik, "deployment", "kind"), "DaemonSet", "workload kind"),
        (traefik.get("hostNetwork"), False, "hostNetwork"),
        (get(traefik, "ingressClass", "enabled"), False,
         "unused IngressClass"),
        (get(traefik, "providers", "kubernetesCRD", "enabled"), False,
         "Traefik CRD provider"),
        (get(traefik, "providers", "kubernetesGateway", "enabled"), True,
         "Gateway provider"),
        (get(traefik, "providers", "kubernetesGateway", "experimentalChannel"),
         False, "Gateway experimental channel"),
        (get(traefik, "providers", "kubernetesIngress", "enabled"), False,
         "legacy Ingress provider"),
        (get(traefik, "providers", "kubernetesIngressNGINX", "enabled"), False,
         "NGINX compatibility provider"),
        (get(traefik, "gatewayClass", "enabled"), True, "GatewayClass enabled"),
        (get(traefik, "gatewayClass", "name"), "traefik", "GatewayClass name"),
        (get(traefik, "gateway", "enabled"), True, "Gateway enabled"),
        (get(traefik, "gateway", "name"), "shared-gateway", "Gateway name"),
        (get(traefik, "gateway", "namespace"), "kube-system",
         "Gateway namespace"),
        (get(traefik, "service", "enabled"), True, "Service enabled"),
        (get(traefik, "service", "single"), True, "single mixed-protocol Service"),
        (get(traefik, "ports", "web", "port"), 8000, "web entrypoint port"),
        (get(traefik, "ports", "websecure", "port"), 8443,
         "websecure entrypoint port"),
        (get(traefik, "ports", "websecure", "http", "tls", "enabled"), False,
         "websecure entrypoint global TLS"),
    ]
    for actual, expected, field in fields:
        report.eq(actual, expected, f"Traefik {field}")
    listeners = get(traefik, "gateway", "listeners") or {}
    report.eq(set(listeners), {"web"}, "default Gateway listener set")
    report.eq(get(listeners, "web", "port"), 8000, "web listener port")
    report.eq(get(listeners, "web", "protocol"), "HTTP", "web listener protocol")
    report.eq(get(listeners, "web", "namespacePolicy", "from"), "Selector",
              "web listener namespace policy")
    report.eq(get(listeners, "web", "namespacePolicy", "selector",
                  "matchLabels"), {"gateway-access": "public"},
              "web listener namespace label selector")
    report.check("tls" not in (listeners.get("web") or {}),
                 "default web listener must not configure TLS")
    report.check("addresses" not in (get(traefik, "gateway") or {}),
                 "Gateway must not fabricate spec addresses")
    report.check("status" not in (get(traefik, "gateway") or {}),
                 "Gateway status must remain runtime-owned")
    if masters == 1:
        report.eq(get(traefik, "service", "spec", "type"), "ClusterIP",
                  "single-master Service type")
        report.eq(get(traefik, "ports", "web", "hostPort"), 80,
                  "single-master web hostPort")
        report.eq(get(traefik, "ports", "websecure", "hostPort"), 443,
                  "single-master websecure hostPort")
        report.eq(get(traefik, "nodeSelector", "kubernetes.io/os"), "linux",
                  "single-master OS selector")
        report.eq(get(traefik, "nodeSelector",
                      "node.kubernetes.io/control-plane"), "true",
                  "single-master control-plane selector")
        tolerations = traefik.get("tolerations") or []
        report.check(any(t.get("key") == "node-role.kubernetes.io/control-plane"
                         and t.get("operator") == "Exists"
                         and t.get("effect") == "NoSchedule"
                         for t in tolerations), "control-plane toleration")
        report.check(any(t.get("key") == "node-role.kubernetes.io/etcd"
                         and t.get("operator") == "Exists"
                         and t.get("effect") == "NoExecute"
                         for t in tolerations), "etcd toleration")
    else:
        report.eq(get(traefik, "service", "spec", "type"), "LoadBalancer",
                  "HA Service type")
        report.check("hostPort" in (get(traefik, "ports", "web") or {})
                     and get(traefik, "ports", "web", "hostPort") is None,
                     "HA web hostPort must be explicitly cleared")
        report.check("hostPort" in (get(traefik, "ports", "websecure") or {})
                     and get(traefik, "ports", "websecure", "hostPort") is None,
                     "HA websecure hostPort must be explicitly cleared")
        report.check("nodeSelector" not in traefik,
                     "HA must not force a single-master nodeSelector")
        report.check("tolerations" not in traefik,
                     "HA must not force single-master tolerations")
    manifest = rke.get("additionalManifest")
    report.check(isinstance(manifest, str) and bool(manifest.strip()),
                 "additionalManifest")
    if not isinstance(manifest, str):
        return
    embedded = [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]
    report.check(not any(d.get("kind") in {"Gateway", "GatewayClass"}
                         for d in embedded),
                 "additionalManifest must not duplicate Gateway objects")
    report.check(not any(d.get("kind") == "Secret" for d in embedded),
                 "additionalManifest must not embed a Secret")
    ccm = find(embedded, "Deployment", "openstack-cloud-controller-manager")
    ccm_image = get(ccm, "spec", "template", "spec", "containers", 0,
                    "image")
    report.eq(ccm_image,
              "registry.k8s.io/provider-os/openstack-cloud-controller-manager:"
              + IMAGES[version][0], "CCM image bundle")
    csi = find(embedded, "DaemonSet", "cinder-csi-node")
    csi_image = get(csi, "spec", "template", "spec", "containers", 0, "image")
    report.eq(csi_image,
              "registry.k8s.io/provider-os/cinder-csi-plugin:"
              + IMAGES[version][1], "CSI driver image bundle")


LOOKUP_SUBSTITUTIONS = (
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $appCredSecretName }}',
     '{{- $secret := include "gateway-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $appCredSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $ccmNetConfigSecretName }}',
     '{{- $secret := include "gateway-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $ccmNetConfigSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $environment := lookup "v1" "ConfigMap" $namespace '
     '"rke2-openstack-environment" }}',
     '{{- $environment := include "gateway-verifier.fixture" (dict "root" $ '
     '"key" (printf "ConfigMap/%s/rke2-openstack-environment" $namespace)) '
     '| fromYaml }}'),
    ("templates/nodeconfig-openstack.yaml",
     '{{- $pkSecret := lookup "v1" "Secret" $namespace $pkSecretName }}',
     '{{- $pkSecret := include "gateway-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $pkSecretName)) | fromYaml }}'),
)

FIXTURE_TEMPLATE = """{{- define "gateway-verifier.fixture" -}}
{{- $fixtures := .root.Values.__gatewayVerifierFixtures | default dict -}}
{{- if not (hasKey $fixtures .key) -}}{{- fail (printf "missing gateway verifier fixture %s" .key) -}}{{- end -}}
{{- toYaml (index $fixtures .key) -}}
{{- end -}}
"""


def fixture_values():
    secret = f"Secret/{NAMESPACE}/"
    return {"__gatewayVerifierFixtures": {
        secret + "os-app-cred-verifier": {"data": {
            "applicationCredentialId": b64("fixture-id"),
            "applicationCredentialSecret": b64("fixture-secret")}},
        secret + "os-ccm-net-config": {"data": {
            "subnetId": b64("fixture-subnet"),
            "floatingNetworkId": b64("fixture-network")}},
        secret + "openstack-privatekey": {"data": {
            "privatekey": b64("fixture-private-key-not-real")}},
        f"ConfigMap/{NAMESPACE}/rke2-openstack-environment": {"data": {
            "authUrl": "https://identity.invalid/v3",
            "region": "fixture-region"}},
    }}


def build_harness(workdir):
    chart = workdir / "chart"
    shutil.copytree(CHART, chart, ignore=shutil.ignore_patterns(
        ".git", ".idea", "__pycache__", "*.tgz"))
    templates = [p for p in (chart / "templates").rglob("*") if p.is_file()]
    if sum(p.read_text().count("lookup ") for p in templates) != len(
            LOOKUP_SUBSTITUTIONS):
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
    (chart / "templates" / "zz-gateway-verifier-fixtures.tpl").write_text(
        FIXTURE_TEMPLATE)
    values = workdir / "fixtures.yaml"
    values.write_text(yaml.safe_dump(fixture_values(), sort_keys=True))
    return chart, values


def run_helm(chart, values, version, masters, extra=None):
    command = ["helm", "template", "gateway-verifier", str(chart),
               "--namespace", NAMESPACE, "--values", str(values),
               "--set-string", f"cluster.name={CLUSTER_NAME}",
               "--set-string",
               "cluster.config.openstack.applicationCredentialSecretName="
               "os-app-cred-verifier",
               "--set-string", f"cluster.config.kubernetesVersion={version}"]
    if masters != 1:
        command.extend(["--set", f"nodePoolCounts.master={masters}"])
    if extra:
        command.extend(extra)
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


def rendered_cluster(report, chart, values, version, masters, extra=None):
    completed = run_helm(chart, values, version, masters, extra)
    if completed.returncode != 0:
        report.check(False, "helm template failed: "
                     + (completed.stderr.strip() or "no stderr"))
        return None
    try:
        documents = [d for d in yaml.safe_load_all(completed.stdout)
                     if isinstance(d, dict)]
    except yaml.YAMLError as error:
        report.check(False, f"rendered chart YAML: {error}")
        return None
    clusters = [d for d in documents if d.get("kind") == "Cluster"]
    report.eq(len(clusters), 1, "Cluster count")
    return clusters[0] if clusters else None


def check_schema(report):
    try:
        schema = json.loads((CHART / "values.schema.json").read_text())
        versions = schema["properties"]["cluster"]["properties"]["config"][
            "properties"]["kubernetesVersion"]["enum"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        report.check(False, f"schema version contract: {error}")
        return
    report.eq(sorted(versions), sorted(IMAGES), "schema supported versions")


def check_merge_preservation(report, chart, values):
    extra = ADD_HTTPS_LISTENER + [
        "--set-json",
        'cluster.config.chartValues.rke2-traefik.gateway.listeners.web.'
        'namespacePolicy={"from":"Same"}',
        "--set-json",
        'cluster.config.chartValues.rke2-traefik.providers.kubernetesGateway.'
        'enabled=false',
        "--set-json",
        'cluster.config.chartValues.rke2-traefik.gateway.enabled=false',
        "--set-string",
        "cluster.config.chartValues.rke2-traefik.service.spec.type=NodePort",
    ]
    cluster = rendered_cluster(report, chart, values, "v1.35.9+rke2r1", 1,
                               extra)
    if cluster is None:
        return
    traefik = get(cluster, "spec", "rkeConfig", "chartValues",
                  "rke2-traefik") or {}
    listeners = get(traefik, "gateway", "listeners") or {}
    report.eq(set(listeners), {"web", "websecure"},
              "extra HTTPS listener must survive chartValues merge")
    report.eq(get(listeners, "websecure", "port"), 8443,
              "extra HTTPS listener port")
    report.eq(get(listeners, "websecure", "protocol"), "HTTPS",
              "extra HTTPS listener protocol")
    report.eq(get(listeners, "websecure", "certificateRefs"),
              [{"name": "dummy-tls", "namespace": "kube-system"}],
              "extra HTTPS certificateRefs")
    report.eq(get(traefik, "providers", "kubernetesGateway", "enabled"), True,
              "provider enablement stays forced")
    report.eq(get(traefik, "providers", "kubernetesCRD", "enabled"), False,
              "CRD provider stays disabled")
    report.eq(get(traefik, "ingressClass", "enabled"), False,
              "unused IngressClass stays disabled")
    report.eq(get(traefik, "ports", "websecure", "http", "tls", "enabled"),
              False, "global websecure TLS stays disabled")
    report.eq(get(traefik, "gateway", "enabled"), True,
              "Gateway enablement stays forced")
    report.eq(get(traefik, "service", "spec", "type"), "ClusterIP",
              "single-master publication stays forced")
    report.eq(get(listeners, "web", "namespacePolicy", "from"), "Selector",
              "baseline web namespace opt-in stays forced")
    report.eq(get(listeners, "web", "namespacePolicy", "selector",
                  "matchLabels"), {"gateway-access": "public"},
              "baseline web namespace selector stays forced")
    report.check("rke2-ingress-nginx" not in (
        get(cluster, "spec", "rkeConfig", "chartValues") or {}),
        "merge must not reintroduce NGINX chartValues")


def check_invalid_topology(report, chart, values):
    completed = run_helm(chart, values, "v1.35.9+rke2r1", 2)
    report.check(completed.returncode != 0,
                 "master count 2 must fail rendering")
    report.check("Master node count of 2 is not supported" in completed.stderr,
                 "invalid topology error message")


def check_old_pins(report, chart, values):
    for version in OLD_PINS:
        completed = run_helm(chart, values, version, 1)
        report.check(completed.returncode != 0,
                     f"old/unsupported pin {version} must fail rendering")
        report.check(all(supported in completed.stderr
                         for supported in IMAGES),
                     f"old-pin error for {version} lists supported versions")


def packaged_chart_values(report, chart, values, version, masters, extra=None):
    cluster = rendered_cluster(report, chart, values, version, masters, extra)
    if cluster is None:
        return None
    return get(cluster, "spec", "rkeConfig", "chartValues", "rke2-traefik")


def render_packaged_chart(report, workdir, package, traefik_values, tag):
    values_file = workdir / f"packaged-{tag}.yaml"
    values_file.write_text(yaml.safe_dump(traefik_values, sort_keys=True))
    completed = subprocess.run(
        ["helm", "template", "gateway-verifier", str(package),
         "--namespace", "kube-system", "--values", str(values_file)],
        capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        report.check(False, f"packaged chart render ({package.name}): "
                     + (completed.stderr.strip() or "no stderr"))
        return None
    return [d for d in yaml.safe_load_all(completed.stdout)
            if isinstance(d, dict)]


def check_gateway_only_providers(report, documents, container, label):
    args = container.get("args") or []
    report.check(not any(arg == "--providers.kubernetescrd"
                         or arg.startswith("--providers.kubernetescrd.")
                         for arg in args),
                 f"{label} must not enable the Traefik CRD provider")
    report.check(not any(arg == "--entryPoints.websecure.http.tls=true"
                         for arg in args),
                 f"{label} must not enable global websecure TLS")
    report.check(not any(d.get("kind") == "IngressClass" for d in documents),
                 f"{label} must not render an IngressClass")


def check_packaged_chart(report, workdir, chart, values, version, masters):
    package = PACKAGED_CHARTS[version]
    if not package.is_file():
        return False
    traefik_values = packaged_chart_values(report, chart, values, version,
                                           masters)
    if traefik_values is None:
        return False
    documents = render_packaged_chart(report, workdir, package, traefik_values,
                                      f"{version}-{masters}")
    if documents is None:
        return False
    gateway_class = find(documents, "GatewayClass", "traefik")
    report.check(gateway_class is not None,
                 f"packaged GatewayClass ({package.name})")
    report.eq(get(gateway_class, "spec", "controllerName"),
              "traefik.io/gateway-controller", "packaged GatewayClass controller")
    gateway = find(documents, "Gateway", "shared-gateway")
    report.check(gateway is not None, f"packaged Gateway ({package.name})")
    report.eq(get(gateway, "metadata", "namespace"), "kube-system",
              "packaged Gateway namespace")
    listeners = get(gateway, "spec", "listeners") or []
    report.eq([listener.get("name") for listener in listeners], ["web"],
              "packaged default listener set")
    report.eq(get(listeners[0] if listeners else {}, "port"), 8000,
              "packaged listener port")
    report.check("addresses" not in (get(gateway, "spec") or {}),
                 "packaged Gateway must not fabricate addresses")
    workloads = [d for d in documents if d.get("kind") == "DaemonSet"]
    report.eq(len(workloads), 1, "packaged DaemonSet count")
    if not workloads:
        return True
    pod = get(workloads[0], "spec", "template", "spec") or {}
    container = (pod.get("containers") or [{}])[0]
    check_gateway_only_providers(report, documents, container, "packaged baseline")
    web = port_of(container, "web")
    secure = port_of(container, "websecure")
    services = [d for d in documents if d.get("kind") == "Service"]
    report.eq(len(services), 1, "packaged Service count")
    report.eq({(p.get("name"), p.get("port")) for p in
               (get(services[0], "spec", "ports") if services else []) or []},
              {("web", 80), ("websecure", 443)},
              "packaged Service must still publish 80 and 443")
    service_type = get(services[0], "spec", "type") if services else None
    if masters == 1:
        report.eq(web.get("hostPort"), 80, "packaged single-master web hostPort")
        report.eq(secure.get("hostPort"), 443,
                  "packaged single-master websecure hostPort")
        report.eq(service_type, "ClusterIP", "packaged single-master Service type")
        report.eq(get(pod, "nodeSelector", "node.kubernetes.io/control-plane"),
                  "true", "packaged single-master control-plane selector")
    else:
        report.check("hostPort" not in web and "hostPort" not in secure,
                     "packaged HA hostPorts cleared")
        report.eq(service_type, "LoadBalancer", "packaged HA Service type")
        report.check(get(pod, "nodeSelector",
                         "node.kubernetes.io/control-plane") is None,
                     "packaged HA must not pin control-plane nodes")
    report.check(not any(p.get("protocol") == "UDP" for p in
                         get(container, "ports") or []),
                 "packaged baseline must not expose UDP/HTTP3")
    report.eq(secure.get("containerPort"), 8443,
              "packaged websecure entrypoint must remain allocated")
    return True


def check_packaged_https_listener(report, workdir, chart, values):
    version = "v1.35.9+rke2r1"
    package = PACKAGED_CHARTS[version]
    if not package.is_file():
        return False
    traefik_values = packaged_chart_values(report, chart, values, version, 1,
                                           ADD_HTTPS_LISTENER)
    if traefik_values is None:
        return False
    documents = render_packaged_chart(report, workdir, package, traefik_values,
                                      "https-listener")
    if documents is None:
        return False
    gateway = find(documents, "Gateway", "shared-gateway")
    listeners = get(gateway, "spec", "listeners") or []
    report.eq([listener.get("name") for listener in listeners],
              ["web", "websecure"],
              "packaged added HTTPS listener set")
    secure = next((listener for listener in listeners
                   if listener.get("name") == "websecure"), {})
    report.eq(secure.get("protocol"), "HTTPS",
              "packaged added HTTPS listener protocol")
    report.eq(secure.get("tls", {}).get("certificateRefs"),
              [{"name": "dummy-tls", "namespace": "kube-system"}],
              "packaged added HTTPS listener certificateRefs")
    report.eq(secure.get("allowedRoutes", {}).get("namespaces", {}).get(
        "from"), "Selector", "packaged added HTTPS listener namespace opt-in")
    workloads = [d for d in documents if d.get("kind") == "DaemonSet"]
    report.eq(len(workloads), 1, "packaged HTTPS DaemonSet count")
    if not workloads:
        return True
    pod = get(workloads[0], "spec", "template", "spec") or {}
    container = (pod.get("containers") or [{}])[0]
    check_gateway_only_providers(report, documents, container,
                                 "packaged HTTPS listener")
    report.eq(port_of(container, "websecure").get("containerPort"), 8443,
              "packaged HTTPS listener container port")
    report.eq(port_of(container, "websecure").get("hostPort"), 443,
              "packaged HTTPS listener hostPort")
    return True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline semantic contract test for the packaged Traefik "
                    "Gateway baseline.",
        epilog="Set RKE2_TRAEFIK_CHART_DIR to the directory containing "
               "rke2-traefik-40.1.009.tgz and rke2-traefik-40.1.013.tgz. "
               "Packaged chart renders are optional unless "
               "--require-packaged-charts is given; this test never downloads "
               "charts.")
    parser.add_argument(
        "--require-packaged-charts", action="store_true",
        help="fail when either packaged rke2-traefik chart is missing instead "
             "of reporting an explicit skip")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if shutil.which("helm") is None:
        print("FAIL: helm is required but not found on PATH", file=sys.stderr)
        return 1
    missing = sorted({package for package in PACKAGED_CHARTS.values()
                      if not package.is_file()}, key=lambda path: path.name)
    if args.require_packaged_charts and missing:
        print("FAIL: --require-packaged-charts: missing packaged "
              "rke2-traefik chart(s):", file=sys.stderr)
        for package in missing:
            print(f"  - {package}", file=sys.stderr)
        print(f"RKE2_TRAEFIK_CHART_DIR={PACKAGE_CACHE} (set it to the offline "
              "package cache directory); this test does not download charts.",
              file=sys.stderr)
        return 1
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    report = Report()
    packaged = 0
    skipped = [package.name for package in missing]
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
        workdir = Path(temporary)
        try:
            chart, values = build_harness(workdir)
        except RuntimeError as error:
            print(f"FAIL: offline render harness: {error}", file=sys.stderr)
            return 1
        report.scope = "schema"
        check_schema(report)
        for version in IMAGES:
            for masters in (1, 3):
                report.scope = f"{version} masters={masters}"
                cluster = rendered_cluster(report, chart, values, version,
                                           masters)
                if cluster is not None:
                    check_cluster(report, cluster, version, masters)
                if check_packaged_chart(report, workdir, chart, values,
                                        version, masters):
                    packaged += 1
        report.scope = "packaged-https-listener"
        if check_packaged_https_listener(report, workdir, chart, values):
            packaged += 1
        report.scope = "merge-preservation"
        check_merge_preservation(report, chart, values)
        report.scope = "invalid-topology"
        check_invalid_topology(report, chart, values)
        report.scope = "old-pins"
        check_old_pins(report, chart, values)
    for failure in report.failures:
        print(f"  - {failure}")
    renders = len(IMAGES) * 2
    if report.failures:
        print(f"FAILED: {renders} renders, {report.checks} checks")
        return 1
    note = ""
    if skipped:
        note = (" (packaged chart cache skipped: " + ", ".join(sorted(skipped))
                + ")")
    print(f"PASS: {renders} renders ({len(IMAGES)} versions x 1/3 masters), "
          f"{packaged} packaged chart renders, {report.checks} checks{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
