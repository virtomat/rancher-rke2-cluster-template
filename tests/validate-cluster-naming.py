#!/usr/bin/env python3
"""Offline contract test for environment-prefixed cluster naming.

Verifies the Rancher UI questions, values/schema contract, and the
`rancher-cluster-templates.clusterName` helper (legacy fallback, stg/prod
prefixing, DNS-label validation, no stripping/truncation, and the 63-character
boundary). It then renders the real chart from a temporary copy with synthetic
lookup fixtures and checks every name consumer: Cluster metadata, machine pool
machineConfigRef, OpenstackConfig metadata, cloud-config Secret and
machineSelectorFiles, ManagedChart names/targets, the ClusterRoleTemplateBinding
hash/namespace, and Cinder CSI CLUSTER_NAME. It also fails on any remaining raw
`.Values.cluster.name` consumer in templates or files outside the helper.
Runtime provisioning is out of scope.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

CHART = Path(__file__).resolve().parents[1]
TMP_ROOT = Path("/tmp/opencode")
NAMESPACE = "u-verifier"
RELEASE = "naming-verifier"
PRINCIPAL = "user://naming-verifier"
SHORT_NAME = "category-test"
VERSION = "v1.35.9+rke2r1"


class Report:
    def __init__(self):
        self.checks = 0
        self.renders = 0
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


def get(value, *keys):
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and isinstance(key, int) and -len(value) <= key < len(value):
            value = value[key]
        else:
            return None
    return value


def find(docs, kind, name):
    return next((document for document in docs
                 if document.get("kind") == kind
                 and get(document, "metadata", "name") == name), None)


def named(items, name):
    return next((item for item in items or [] if item.get("name") == name), {})


def sha8(value):
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def chart_version():
    return get(yaml.safe_load((CHART / "Chart.yaml").read_text()), "version")


def check_questions(report):
    data = yaml.safe_load((CHART / "questions.yaml").read_text())
    questions = data.get("questions") or []
    variables = [question.get("variable") for question in questions]
    report.check("cluster.name" not in variables,
                 "legacy cluster.name must not be a visible UI question")
    report.check(variables.count("cluster.userName") == 1,
                 "cluster.userName question count")
    report.check(variables.count("cluster.environment") == 1,
                 "cluster.environment question count")
    if "cluster.userName" not in variables or "cluster.environment" not in variables:
        return
    user_index = variables.index("cluster.userName")
    report.eq(variables[user_index + 1], "cluster.environment",
              "environment question must immediately follow cluster.userName")
    user = questions[user_index]
    environment = questions[user_index + 1]
    report.eq(user.get("label"), "Cluster Name", "cluster.userName label")
    report.eq(user.get("default"), "test", "cluster.userName default")
    report.eq(user.get("required"), True, "cluster.userName required")
    report.eq(user.get("type"), "string", "cluster.userName type")
    report.eq(user.get("group"), "General", "cluster.userName group")
    report.check("show_if" not in user,
                 "cluster.userName must be visible in Simple and Advanced")
    report.eq(environment.get("label"), "Environment",
              "cluster.environment label")
    report.eq(environment.get("default"), "stg", "cluster.environment default")
    report.eq(environment.get("required"), True, "cluster.environment required")
    report.eq(environment.get("type"), "enum", "cluster.environment type")
    report.eq(environment.get("group"), "General", "cluster.environment group")
    report.check("show_if" not in environment,
                 "cluster.environment must be visible in Simple and Advanced")
    options = environment.get("options")
    report.check(isinstance(options, dict),
                 "cluster.environment options must be the Rancher enum map")
    if isinstance(options, dict):
        report.eq(list(options), ["stg", "prod"],
                  "cluster.environment option order/values")
        report.eq(options.get("stg"), "Staging", "stg option label")
        report.eq(options.get("prod"), "Production", "prod option label")


def check_values_and_schema(report):
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    report.eq(get(values, "cluster", "name"), "test", "legacy values cluster.name")
    report.eq(get(values, "cluster", "userName"), "", "values cluster.userName")
    report.eq(get(values, "cluster", "environment"), "stg",
              "values cluster.environment")
    try:
        schema = json.loads((CHART / "values.schema.json").read_text())
        cluster = schema["properties"]["cluster"]["properties"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        report.check(False, f"schema cluster contract: {error}")
        return
    report.eq(get(cluster, "name", "type"), "string", "schema cluster.name type")
    report.eq(get(cluster, "userName", "type"), "string",
              "schema cluster.userName type")
    report.eq(get(cluster, "environment", "type"), "string",
              "schema cluster.environment type")
    report.eq(get(cluster, "environment", "enum"), ["stg", "prod"],
              "schema cluster.environment enum")
    report.eq(get(cluster, "environment", "default"), "stg",
              "schema cluster.environment default")
    allowed = get(cluster, "userName", "pattern")
    report.check(isinstance(allowed, str), "schema cluster.userName pattern")
    if isinstance(allowed, str):
        for value in ("", "category-test", "a", "0", "a-b"):
            report.check(re.fullmatch(allowed, value) is not None,
                         f"schema userName pattern accepts {value!r}")
        for value in ("Bad", "bad.name", "bad name", "-bad", "bad-", "bad_name"):
            report.check(re.fullmatch(allowed, value) is None,
                         f"schema userName pattern rejects {value!r}")
    report.eq(len(get(cluster, "config", "properties", "kubernetesVersion",
                      "enum") or []), 3,
              "schema Kubernetes version enum preserved")


def raw_name_consumers():
    paths = [path for path in (CHART / "templates").rglob("*") if path.is_file()]
    paths.append(CHART / "files" / "openstack-cinder-csi-manifest.yaml")
    for path in paths:
        if path.name == "_helpers.tpl":
            continue
        if path.suffix not in {".yaml", ".tpl"}:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if ".Values.cluster.name" in line:
                yield path.relative_to(CHART), number, line.strip()


def check_static_helper_usage(report):
    helper = (CHART / "templates" / "_helpers.tpl").read_text()
    report.check('define "rancher-cluster-templates.clusterName"' in helper,
                 "clusterName helper definition missing")
    report.check(".Values.cluster.name" in helper,
                 "legacy cluster.name fallback missing from helper")
    for relative in (
        "templates/cluster.yaml",
        "templates/nodeconfig-openstack.yaml",
        "templates/openstack-cloud-config-secret.yaml",
        "templates/managedcharts.yaml",
        "templates/clusterroletemplatebinding.yaml",
        "files/openstack-cinder-csi-manifest.yaml",
    ):
        report.check(
            'include "rancher-cluster-templates.clusterName"' in
            (CHART / relative).read_text(),
            f"{relative} does not use the clusterName helper")
    consumers = list(raw_name_consumers())
    report.check(not consumers,
                 "raw .Values.cluster.name consumers outside helper: "
                 + ", ".join(f"{path}:{line}" for path, line, _ in consumers))


HELPER_PROBE = """apiVersion: v1
kind: ConfigMap
metadata:
  name: naming-probe
data:
  clusterName: {{ include "rancher-cluster-templates.clusterName" . | quote }}
"""


def build_helper_chart(workdir):
    mini = workdir / "helper-chart"
    (mini / "templates").mkdir(parents=True)
    (mini / "Chart.yaml").write_text(
        "apiVersion: v2\nname: naming-helper\nversion: 0.0.1\n")
    shutil.copy(CHART / "templates" / "_helpers.tpl",
                mini / "templates" / "_helpers.tpl")
    (mini / "templates" / "probe.yaml").write_text(HELPER_PROBE)
    return mini


def run_helper(workdir, mini, cluster, label):
    values = workdir / f"helper-{label}.yaml"
    values.write_text(yaml.safe_dump({"cluster": cluster}, sort_keys=False))
    return subprocess.run(
        ["helm", "template", "naming-helper", str(mini),
         "--values", str(values)],
        capture_output=True, text=True, timeout=120)


def helper_name(report, workdir, mini, cluster, expected, label):
    completed = run_helper(workdir, mini, cluster, label)
    if completed.returncode != 0:
        report.check(False, f"{label} helper render failed: "
                     + (completed.stderr.strip() or "no stderr"))
        return
    documents = [document for document in
                 yaml.safe_load_all(completed.stdout)
                 if isinstance(document, dict)]
    probe = find(documents, "ConfigMap", "naming-probe")
    actual = get(probe or {}, "data", "clusterName")
    report.eq(actual, expected, f"{label} helper name")
    if isinstance(actual, str):
        report.check(len(actual) <= 63, f"{label} helper name length")


def helper_failure(report, workdir, mini, cluster, label, needle):
    completed = run_helper(workdir, mini, cluster, label)
    report.check(completed.returncode != 0,
                 f"{label} helper must fail rendering")
    report.check(needle in completed.stderr,
                 f"{label} helper error must mention {needle!r}")


def check_helper_contract(report, workdir):
    mini = build_helper_chart(workdir)
    helper_name(report, workdir, mini, {"name": "legacy-name"},
                "legacy-name", "legacy")
    helper_name(report, workdir, mini,
                {"name": "legacy-name", "userName": SHORT_NAME},
                f"stg-{SHORT_NAME}", "omitted-environment")
    helper_name(report, workdir, mini,
                {"name": "legacy-name", "userName": SHORT_NAME,
                 "environment": "prod"},
                f"prod-{SHORT_NAME}", "prod")
    helper_name(report, workdir, mini,
                {"name": "legacy-name", "userName": "stg-foo",
                 "environment": "stg"},
                "stg-stg-foo", "double-prefix")
    stg_boundary = "a" * 59
    prod_boundary = "a" * 58
    helper_name(report, workdir, mini,
                {"name": "legacy-name", "userName": stg_boundary},
                f"stg-{stg_boundary}", "stg-boundary-63")
    helper_name(report, workdir, mini,
                {"name": "legacy-name", "userName": prod_boundary,
                 "environment": "prod"},
                f"prod-{prod_boundary}", "prod-boundary-63")

    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": SHORT_NAME,
                    "environment": "qa"},
                   "invalid-environment", "Unsupported cluster.environment")
    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": SHORT_NAME,
                    "environment": ""},
                   "empty-environment", "cluster.environment must not be empty")
    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": SHORT_NAME,
                    "environment": 1},
                   "non-string-environment",
                   "cluster.environment must be a string")
    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": 1},
                   "non-string-user-name",
                   "cluster.userName must be a string")
    for label, user_name in (
        ("uppercase", "Bad"),
        ("dot", "bad.name"),
        ("whitespace", "bad name"),
        ("underscore", "bad_name"),
        ("leading-hyphen", "-bad"),
        ("trailing-hyphen", "bad-"),
    ):
        helper_failure(report, workdir, mini,
                       {"name": "legacy-name", "userName": user_name},
                       f"non-dns-{label}", "cluster.userName")
    helper_failure(report, workdir, mini, {"name": "", "userName": ""},
                   "empty-both",
                   "cluster.userName is required when cluster.name is empty")
    helper_failure(report, workdir, mini, {},
                   "no-name",
                   "cluster.userName is required when cluster.name is empty")
    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": "a" * 60},
                   "stg-over-63", "maximum is 63")
    helper_failure(report, workdir, mini,
                   {"name": "legacy-name", "userName": "a" * 59,
                    "environment": "prod"},
                   "prod-over-63", "maximum is 63")


LOOKUP_SUBSTITUTIONS = (
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $appCredSecretName }}',
     '{{- $secret := include "naming-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $appCredSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $secret := lookup "v1" "Secret" $namespace $ccmNetConfigSecretName }}',
     '{{- $secret := include "naming-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $ccmNetConfigSecretName)) | fromYaml }}'),
    ("templates/_helpers.tpl",
     '{{- $environment := lookup "v1" "ConfigMap" $namespace '
     '"rke2-openstack-environment" }}',
     '{{- $environment := include "naming-verifier.fixture" (dict "root" $ "key" '
     '(printf "ConfigMap/%s/rke2-openstack-environment" $namespace)) | fromYaml }}'),
    ("templates/nodeconfig-openstack.yaml",
     '{{- $pkSecret := lookup "v1" "Secret" $namespace $pkSecretName }}',
     '{{- $pkSecret := include "naming-verifier.fixture" (dict "root" $ "key" '
     '(printf "Secret/%s/%s" $namespace $pkSecretName)) | fromYaml }}'),
)

FIXTURE_TEMPLATE = """{{- define "naming-verifier.fixture" -}}
{{- $fixtures := .root.Values.__namingVerifierFixtures | default dict -}}
{{- if not (hasKey $fixtures .key) -}}{{- fail (printf "missing naming verifier fixture %s" .key) -}}{{- end -}}
{{- toYaml (index $fixtures .key) -}}
{{- end -}}
"""


def fixture_values():
    secret = f"Secret/{NAMESPACE}/"
    return {"__namingVerifierFixtures": {
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
    templates = [path for path in (chart / "templates").rglob("*")
                 if path.is_file()]
    if sum(path.read_text().count("lookup ") for path in templates) != len(
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
    if any("lookup " in path.read_text() for path in templates):
        raise RuntimeError("lookup fixture replacement incomplete")
    (chart / "templates" / "zz-naming-verifier-fixtures.tpl").write_text(
        FIXTURE_TEMPLATE)
    values = workdir / "fixtures.yaml"
    values.write_text(yaml.safe_dump(fixture_values(), sort_keys=True))
    return chart, values


def base_args():
    return [
        "--set-string",
        "cluster.config.openstack.applicationCredentialSecretName=os-app-cred-verifier",
        "--set-string", f"cluster.config.kubernetesVersion={VERSION}",
        "--set", "addons.monitoring.enabled=true",
        "--set-string", "addons.monitoring.version=1.0.0",
        "--set-json",
        'clusterMembers=[{"principalName":"user://naming-verifier",'
        '"roleTemplateName":"cluster-member"}]',
    ]


def run_helm(chart, values, extra):
    command = ["helm", "template", RELEASE, str(chart),
               "--namespace", NAMESPACE, "--values", str(values)]
    command.extend(base_args())
    command.extend(extra)
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


def render(report, chart, values, extra, scope):
    report.scope = scope
    completed = run_helm(chart, values, extra)
    if completed.returncode != 0:
        report.check(False, "helm template failed: "
                     + (completed.stderr.strip() or "no stderr"))
        return None
    try:
        documents = [document for document in
                     yaml.safe_load_all(completed.stdout)
                     if isinstance(document, dict)]
    except yaml.YAMLError as error:
        report.check(False, f"rendered chart YAML: {error}")
        return None
    report.renders += 1
    return documents


def check_references(report, docs, expected, pools, scope):
    report.scope = scope
    clusters = [document for document in docs
                if document.get("kind") == "Cluster"]
    report.eq(len(clusters), 1, "Cluster count")
    if not clusters:
        return
    cluster = clusters[0]
    report.eq(get(cluster, "metadata", "name"), expected, "Cluster name")
    rke = get(cluster, "spec", "rkeConfig") or {}
    machine_pools = rke.get("machinePools") or []
    report.eq([pool.get("name") for pool in machine_pools], pools,
              "machine pool set")
    for pool in machine_pools:
        report.eq(get(pool, "machineConfigRef", "name"),
                  f"{expected}-{pool.get('name')}",
                  f"{pool.get('name')} machineConfigRef")
    configs = [document for document in docs
               if document.get("kind") == "OpenstackConfig"]
    report.eq(sorted(get(config, "metadata", "name") for config in configs),
              sorted(f"{expected}-{pool}" for pool in pools),
              "OpenstackConfig names")
    suffix = sha8(f"{RELEASE}-{NAMESPACE}-{chart_version()}")
    secret_name = f"{expected}-cloud-config-{suffix}"
    secret = find(docs, "Secret", secret_name)
    report.check(secret is not None, f"Secret/{secret_name} missing")
    if secret:
        report.eq(get(secret, "metadata", "annotations",
                      "rke.cattle.io/object-authorized-for-clusters"),
                  expected, "cloud-config authorized-for-clusters")
    selector_secret = get(rke, "machineSelectorFiles", 0, "fileSources", 0,
                          "secret", "name")
    report.eq(selector_secret, secret_name,
              "machineSelectorFiles cloud-config Secret name")
    managed = [document for document in docs
               if document.get("kind") == "ManagedChart"]
    report.eq(sorted(get(chart, "metadata", "name") for chart in managed),
              sorted([f"monitoring-crd-{expected}",
                      f"monitoring-{expected}"]),
              "ManagedChart names")
    for chart in managed:
        report.eq(get(chart, "spec", "targets", 0, "clusterName"), expected,
                  f"{get(chart, 'metadata', 'name')} target clusterName")
    manifest = rke.get("additionalManifest")
    report.check(isinstance(manifest, str) and bool(manifest.strip()),
                 "additionalManifest")
    if isinstance(manifest, str):
        embedded = [document for document in yaml.safe_load_all(manifest)
                    if isinstance(document, dict)]
        deployment = find(embedded, "Deployment", "cinder-csi-controller")
        report.check(deployment is not None,
                     "Cinder CSI controller deployment missing")
        driver = named(get(deployment or {}, "spec", "template", "spec",
                           "containers"), "cinder-csi-plugin")
        report.eq(named(driver.get("env"), "CLUSTER_NAME").get("value"),
                  expected, "CSI CLUSTER_NAME")
        report.check("--cluster=$(CLUSTER_NAME)" in (driver.get("args") or []),
                     "CSI --cluster must use CLUSTER_NAME")
    management_id = "c-m-" + sha8(f"{NAMESPACE}/{expected}")
    crtb_name = "ctrb-" + sha8(f"{NAMESPACE}/{PRINCIPAL}")
    crtb = find(docs, "ClusterRoleTemplateBinding", crtb_name)
    report.check(crtb is not None, f"CRTB/{crtb_name} missing")
    if crtb:
        report.eq(crtb.get("clusterName"), management_id,
                  "CRTB clusterName hash")
        report.eq(get(crtb, "metadata", "namespace"), management_id,
                  "CRTB namespace hash")
        report.eq(crtb.get("userPrincipalName"), PRINCIPAL,
                  "CRTB representative principal")


def render_and_check(report, chart, values, extra, expected, pools, scope):
    docs = render(report, chart, values, extra, scope)
    if docs is not None:
        check_references(report, docs, expected, pools, scope)


def check_chart_failure(report, chart, values, extra, scope, needle):
    report.scope = scope
    completed = run_helm(chart, values, extra)
    report.check(completed.returncode != 0, f"{scope} must fail rendering")
    report.check(needle in completed.stderr,
                 f"{scope} error must mention {needle!r}")


def check_rendered_contract(report, workdir, chart, values):
    legacy_values = workdir / "legacy-values.yaml"
    legacy_values.write_text(yaml.safe_dump(
        {"cluster": {"name": "legacy-old-values"}}, sort_keys=False))
    render_and_check(
        report, chart, values,
        ["--values", str(legacy_values)],
        "legacy-old-values", ["master"], "legacy-old-values")
    render_and_check(report, chart, values, [], "test", ["master"],
                     "legacy-default")
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={SHORT_NAME}"],
        f"stg-{SHORT_NAME}", ["master"], "stg-category-simple")
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={SHORT_NAME}",
         "--set", "nodePoolTemplate=MultiPool",
         "--set", "nodePoolCounts.master=3",
         "--set", "nodePoolCounts.worker=1"],
        f"stg-{SHORT_NAME}", ["master", "worker"], "stg-category-multi")
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={SHORT_NAME}",
         "--set-string", "cluster.environment=prod"],
        f"prod-{SHORT_NAME}", ["master"], "prod-category-simple")
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={SHORT_NAME}",
         "--set-string", "cluster.environment=prod",
         "--set", "nodePoolTemplate=MultiPool",
         "--set", "nodePoolCounts.master=3",
         "--set", "nodePoolCounts.worker=1"],
        f"prod-{SHORT_NAME}", ["master", "worker"], "prod-category-multi")
    render_and_check(
        report, chart, values,
        ["--set-string", "cluster.userName=stg-foo",
         "--set-string", "cluster.environment=stg"],
        "stg-stg-foo", ["master"], "double-prefix")
    stg_boundary = "a" * 59
    prod_boundary = "a" * 58
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={stg_boundary}"],
        f"stg-{stg_boundary}", ["master"], "stg-boundary-63")
    render_and_check(
        report, chart, values,
        ["--set-string", f"cluster.userName={prod_boundary}",
         "--set-string", "cluster.environment=prod"],
        f"prod-{prod_boundary}", ["master"], "prod-boundary-63")
    check_chart_failure(
        report, chart, values,
        ["--set-string", f"cluster.userName={'a' * 60}"],
        "chart-stg-over-63", "maximum is 63")
    check_chart_failure(
        report, chart, values,
        ["--set-string", f"cluster.userName={'a' * 59}",
         "--set-string", "cluster.environment=prod"],
        "chart-prod-over-63", "maximum is 63")

    empty_values = workdir / "empty-name.yaml"
    empty_values.write_text(yaml.safe_dump(
        {"cluster": {"name": "", "userName": ""}}, sort_keys=False))
    check_chart_failure(
        report, chart, values, ["--values", str(empty_values)],
        "chart-empty-name",
        "cluster.userName is required when cluster.name is empty")
    check_chart_failure(
        report, chart, values,
        ["--set-string", f"cluster.userName={SHORT_NAME}",
         "--set-string", "cluster.environment=qa"],
        "chart-invalid-environment", "/cluster/environment")
    check_chart_failure(
        report, chart, values,
        ["--set-string", "cluster.userName=Bad"],
        "chart-invalid-user-name", "/cluster/userName")


def main():
    if shutil.which("helm") is None:
        print("FAIL: helm is required but not found on PATH", file=sys.stderr)
        return 1
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.scope = "questions"
    check_questions(report)
    report.scope = "values-schema"
    check_values_and_schema(report)
    report.scope = "static"
    check_static_helper_usage(report)
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
        workdir = Path(temporary)
        report.scope = "helper"
        check_helper_contract(report, workdir)
        try:
            chart, values = build_harness(workdir)
        except RuntimeError as error:
            print(f"FAIL: offline render harness: {error}", file=sys.stderr)
            return 1
        check_rendered_contract(report, workdir, chart, values)
    for failure in report.failures:
        print(f"  - {failure}")
    if report.failures:
        print(f"FAILED: {report.renders} chart renders, {report.checks} checks")
        return 1
    print(f"PASS: {report.renders} chart renders, {report.checks} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
