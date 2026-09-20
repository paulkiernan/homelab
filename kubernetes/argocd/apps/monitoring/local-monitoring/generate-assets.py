#!/usr/bin/env python3
"""Render this app's Grafana provisioning assets from their canonical sources.

The market measurement definitions stay owned by paulkiernan/diff-logic-cells:

  deploy/grafana/dashboards/*.json        every market dashboard, no exceptions
  deploy/grafana/alerts/*.json.tmpl       every market rule-group template

This script only adapts them to the local Grafana (which provisions from files
instead of the Grafana Cloud HTTP API), so nothing here may invent rules or
panels:

  dashboards  ${DS_PROMETHEUS} -> the local datasource UID market-prometheus,
              and the export-only __inputs/__requires blocks are dropped (file
              provisioning has no import dialog to answer them).
  alerts      __DATASOURCE_UID__ -> market-prometheus, the group's folderUid is
              replaced by the local folder title (file provisioning takes a
              folder title and creates it), and the per-site absence rule is
              expanded once per expected site, exactly like
              deploy/grafana/apply-market-recorder-alerts.py does for Grafana
              Cloud. Every template becomes one rule group; group names and rule
              uids must stay unique across templates (Grafana keys groups by
              folder+name and rules by uid, so a collision would silently
              overwrite rules), and the generator refuses to emit a file that
              would collide.

The Kubernetes assets come from vendored upstream files under upstream/.
fetch-upstream.py owns those files: it downloads each pinned URL, verifies the
sha256, and writes upstream/SOURCES.json, so this script never reaches the
network. Which of them are provisioned is decided here, not there:

  dashboards  the 16 kube-prometheus dashboards, plus the OpenCost overview and
              the Kepler exporter dashboard matching the deployed exporter.
  rules       the record and alert rules of the selected upstream groups, split
              by destination: Prometheus evaluates the recording rules (it has
              no Alertmanager and no alerting rules of its own — cluster
              alerting is Grafana-managed), Grafana provisions the alerting
              rules.

Selector rewrite: kube-prometheus targets a Prometheus that scrapes the
cluster itself, so its dashboards and rules select `job="kubelet"`,
`job="kube-state-metrics"` and `job="node-exporter"`, using `metrics_path` to
tell the two kubelet endpoints apart. This cluster instead receives Alloy's
remote-write, where those scrapes are separate jobs
(`integrations/kubernetes/cadvisor`, `integrations/kubernetes/kubelet`,
`integrations/kubernetes/kube-state-metrics`, `integrations/node_exporter`) and
`metrics_path` is not a label at all. Every selector string is therefore
rewritten with substitute()'s exact literals (not regexes) before emission, and
assert_selectors_rewritten() refuses to emit a document that still filters on
`metrics_path=` or on a job value this cluster does not produce — such panels
and rules would silently match nothing. The OpenCost and Kepler dashboards
select their own exporters' labels and are not rewritten.

Alert conversion: one upstream Prometheus alerting rule becomes one Grafana
provisioning rule whose condition is a math expression (`is_number($A)`) over
the upstream expression evaluated as an instant query. Upstream expressions
already embed their thresholds and return only the offending series — some of
them legitimately return the value 0 (rules ending `== 0`) — so "a numeric
result exists" is the correct firing condition where `$A > 0` would never fire
for those rules. Annotation templates are rewritten `$value` ->
`$values.A.Value` because Grafana's own `$value` is a formatted string while
the template functions (humanize, humanizePercentage, humanizeDuration) want
the float.

Expected sites come from the measurement ConfigMap in this repository
(kubernetes/argocd/apps/workloads/market-measurement/manifests/configmap.yaml,
key `sites`), so the two backends can never disagree about which capture hosts
must be reporting.

Outputs (all generated, all committed; run with --check to detect drift):

  manifests/assets/dashboards/<name>.json   import-ready dashboard JSON
  manifests/grafana-dashboards-configmap.yaml
  manifests/grafana-alerting-configmap.yaml
  manifests/grafana-dashboards-kubernetes-configmap.yaml
  manifests/grafana-alerting-kubernetes-configmap.yaml
  manifests/prometheus-rules-configmap.yaml

The ConfigMaps are the kustomize inputs referenced by manifests/kustomization.yaml
and by the Grafana helm values in application.yaml. No other generator and no
task in .taskfiles/ owns these files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MANIFESTS = HERE / "manifests"
ASSET_DASHBOARDS = MANIFESTS / "assets" / "dashboards"
MEASUREMENT_CONFIGMAP = (
    HERE.parents[1] / "workloads" / "market-measurement" / "manifests" / "configmap.yaml"
)

DEFAULT_SOURCE = Path(
    os.environ.get("MSR_SOURCE_DIR", Path.home() / "workspace/github.com/paulkiernan/diff-logic-cells")
)

# The Grafana datasource that points at the in-cluster Prometheus. Same UID in
# the datasource provisioning values (application.yaml) and in the alert rules;
# dashboards reach it through the ${DS_PROMETHEUS} substitution below.
DATASOURCE_UID = "market-prometheus"

# Grafana's hard limit on alert rule UIDs (pkg/services/ngalert validation).
GRAFANA_UID_MAX = 40

# Folder title for dashboards and alert rules. File provisioning creates it.
FOLDER_TITLE = "Market measurement"

# ConfigMap names referenced by the Grafana helm values. The alert ConfigMap
# must carry the chart's alerts-sidecar label so Grafana reloads rules without
# a pod restart.
DASHBOARDS_CONFIGMAP = "local-monitoring-grafana-dashboards"
ALERTING_CONFIGMAP = "local-monitoring-grafana-alerting"
ALERTS_SIDECAR_LABEL = "grafana_alert"

UNRESOLVED = re.compile(r"__[A-Z_]+__")
DS_TOKEN = re.compile(r"\$\{DS_[A-Za-z0-9_]+\}")
GENERATED_HEADER = (
    "# Generated by generate-assets.py from deploy/grafana in "
    "paulkiernan/diff-logic-cells — do not edit by hand.\n"
)
KUBE_GENERATED_HEADER = (
    "# Generated by generate-assets.py from the vendored upstream files in "
    "upstream/ — do not edit by hand.\n"
)

# Vendored upstream inputs. fetch-upstream.py writes them and upstream/SOURCES.json
# pins each one's sha256; this script only reads them.
UPSTREAM = HERE / "upstream"
KUBE_PROMETHEUS = UPSTREAM / "kube-prometheus"
UPSTREAM_DASHBOARDS = KUBE_PROMETHEUS / "dashboards"

# Folder for the cluster-wide dashboards and rules, next to the market folder.
KUBE_FOLDER_TITLE = "Kubernetes"

KUBE_DASHBOARDS_CONFIGMAP = "local-monitoring-grafana-dashboards-kubernetes"
KUBE_ALERTING_CONFIGMAP = "local-monitoring-grafana-alerting-kubernetes"
PROM_RULES_CONFIGMAP = "local-monitoring-prometheus-rules"

# The API server rejects a ConfigMap whose serialized object exceeds 1 MiB, and
# a rejected object fails the whole ArgoCD sync, so keep real headroom and fail
# at generation time instead of at apply time.
CONFIGMAP_BUDGET = 900_000

# The upstream selection is fixed here (not by whatever happens to be vendored),
# so a pin bump in fetch-upstream.py has to come with a deliberate change here.
UPSTREAM_RULE_FILES = (
    "kubernetesControlPlane-prometheusRule.yaml",
    "nodeExporter-prometheusRule.yaml",
    "kubeStateMetrics-prometheusRule.yaml",
    "kubePrometheus-prometheusRule.yaml",
)
UPSTREAM_KUBE_DASHBOARDS = (
    "cluster-total.json",
    "k8s-resources-cluster.json",
    "k8s-resources-namespace.json",
    "k8s-resources-node.json",
    "k8s-resources-pod.json",
    "k8s-resources-workload.json",
    "k8s-resources-workloads-namespace.json",
    "kubelet.json",
    "namespace-by-pod.json",
    "namespace-by-workload.json",
    "node-cluster-rsrc-use.json",
    "node-rsrc-use.json",
    "nodes.json",
    "persistentvolumesusage.json",
    "pod-total.json",
    "workload-total.json",
)
UPSTREAM_OTHER_DASHBOARDS = (
    UPSTREAM / "opencost" / "overview.json",
    UPSTREAM / "kepler" / "kepler-exporter.json",
)

# kube-prometheus group names whose record rules Prometheus evaluates locally.
# The apiserver/scheduler/controller-manager groups are omitted: this cluster
# runs a managed control plane and those targets are not scraped.
RECORDING_GROUPS = (
    "k8s.rules.container_cpu_usage_seconds_total",
    "k8s.rules.container_memory_working_set_bytes",
    "k8s.rules.container_memory_rss",
    "k8s.rules.container_memory_cache",
    "k8s.rules.container_memory_swap",
    "k8s.rules.container_memory_requests",
    "k8s.rules.container_cpu_requests",
    "k8s.rules.container_memory_limits",
    "k8s.rules.container_cpu_limits",
    "k8s.rules.pod_owner",
    "node.rules",
    "kubelet.rules",
    "node-exporter.rules",
    "kube-prometheus-node-recording.rules",
    "kube-prometheus-general.rules",
)
# The pinned upstream revision ships exactly this many of each; a mismatch means
# a pin bump or a selection mistake. Split the selection or bump the number
# deliberately — never widen a rewrite or drop a group to make it fit.
EXPECTED_RECORD_RULES = 53

# kube-prometheus group names whose alert rules become Grafana-managed rules.
ALERT_GROUPS = (
    "kubernetes-apps",
    "kubernetes-resources",
    "kubernetes-storage",
    "kubernetes-system",
    "kubernetes-system-kubelet",
    "node-exporter",
    "kube-state-metrics",
    "general.rules",
    "node-network",
)
EXPECTED_ALERT_RULES = 79
# Watchdog and InfoInhibitor are Alertmanager-only conventions (a dead-man and
# an inhibition marker) with no equivalent in Grafana unified alerting.
# KubeClientErrors selects job="apiserver", which this cluster does not receive.
EXCLUDED_ALERTS = frozenset({"Watchdog", "InfoInhibitor", "KubeClientErrors"})

# Exact-literal selector rewrite, applied to every string of the kube-prometheus
# dashboards and rules. The two qualified kubelet selectors are distinct
# literals, so substitute() can apply them in this order without overlap.
SELECTOR_REWRITE = {
    'job="kubelet", metrics_path="/metrics/cadvisor"': 'job="integrations/kubernetes/cadvisor"',
    'job="kubelet", metrics_path="/metrics"': 'job="integrations/kubernetes/kubelet"',
    'job="kube-state-metrics"': 'job="integrations/kubernetes/kube-state-metrics"',
    'job="node-exporter"': 'job="integrations/node_exporter"',
}
JOB_SELECTOR = re.compile(r'job=~?"([^"]*)"')
INTEGRATION_JOB_PREFIX = "integrations/"
# Grafana's `$value` is a formatted string; the template functions that consume
# it (humanize, humanizePercentage, humanizeDuration) want the float from
# `$values.<refId>.Value`. The lookahead keeps an existing `$values…` intact.
VALUE_TEMPLATE = re.compile(r"\$value(?![A-Za-z0-9_])")


def die(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def expected_sites(path: Path) -> list[str]:
    configmap = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw = (configmap.get("data") or {}).get("sites", "")
    sites = raw.split()
    if not sites:
        die(f"{path} has no `sites` entry in data")
    return sites


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def yaml_block(obj: object) -> str:
    """Deterministic YAML for embedding as a ConfigMap block scalar."""
    return yaml.safe_dump(obj, sort_keys=False, default_flow_style=False, width=4096, allow_unicode=True)


def substitute(value: object, mapping: dict[str, str]) -> object:
    if isinstance(value, str):
        for token, replacement in mapping.items():
            value = value.replace(token, replacement)
        return value
    if isinstance(value, list):
        return [substitute(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, mapping) for key, item in value.items()}
    return value


def strings(value: object) -> Iterator[str]:
    """Every string of a parsed JSON/YAML document, in document order.

    Selector validation has to look at the parsed values, not at the serialized
    file: json.dumps escapes the inner quotes of an expression, so a literal
    like job="kubelet" never appears verbatim in the emitted text.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def assert_selectors_rewritten(origin: str, document: object) -> None:
    """Die if a document still selects scrape targets this cluster does not have.

    Every job selector must name an Alloy remote-write job (integrations/...) or
    a dashboard template variable ($ksm_job, ...; a bare regex wildcard carries
    no literal target either). `metrics_path` is not a label on remote-written
    series at all, so any occurrence is residue of the kube-prometheus scrape
    config. Emitting one of those would provision panels and rules that match
    nothing while looking healthy.
    """
    for text in strings(document):
        if "metrics_path=" in text:
            die(f"{origin}: selector still filters on metrics_path after the rewrite: {text[:160]!r}")
        for value in JOB_SELECTOR.findall(text):
            if value.startswith((INTEGRATION_JOB_PREFIX, "$")) or not re.search(r"[A-Za-z0-9_/]", value):
                continue
            die(f"{origin}: unknown job selector job=\"{value}\" after the rewrite: {text[:160]!r}")


def assert_configmap_budget(configmap: dict) -> None:
    """Die if one ConfigMap's data would exceed CONFIGMAP_BUDGET bytes."""
    data = configmap.get("data") or {}
    size = sum(len(value.encode("utf-8")) for value in data.values())
    if size > CONFIGMAP_BUDGET:
        die(
            f"ConfigMap {configmap['metadata']['name']} carries {size} bytes of data, "
            f"over the {CONFIGMAP_BUDGET}-byte budget (the API server limit is 1 MiB and an "
            f"oversized ConfigMap would fail the sync)"
        )


def render_dashboard(name: str, raw: str, rewrite: dict[str, str] | None = None) -> str:
    """Adapt one dashboard to the local Grafana.

    `rewrite` is an extra exact-literal substitution applied to every string
    after the datasource placeholders; the kube-prometheus dashboards use it to
    move their selectors onto Alloy's job labels.
    """
    dashboard = json.loads(raw)
    if not isinstance(dashboard, dict) or not dashboard.get("uid") or not dashboard.get("title"):
        die(f"dashboard {name} must be a JSON object with uid and title")

    inputs = dashboard.pop("__inputs", [])
    dashboard.pop("__requires", None)
    placeholders: dict[str, str] = {}
    for entry in inputs:
        if not isinstance(entry, dict) or not entry.get("name"):
            die(f"dashboard {name} has a malformed __inputs entry")
        if entry.get("type") != "datasource" or entry.get("pluginId") != "prometheus":
            die(
                f"dashboard {name} needs datasource input {entry['name']!r} of type "
                f"{entry.get('pluginId')!r}; this Grafana only provisions the Prometheus "
                f"datasource {DATASOURCE_UID!r}"
            )
        placeholders[f"${{{entry['name']}}}"] = DATASOURCE_UID
    rendered = substitute(dashboard, placeholders)
    if rewrite:
        rendered = substitute(rendered, rewrite)
    text = json.dumps(rendered, indent=2, ensure_ascii=False) + "\n"

    tokens = sorted(set(DS_TOKEN.findall(text)))
    if tokens:
        die(f"dashboard {name} still references {', '.join(tokens)} after substitution")
    leftovers = sorted(set(UNRESOLVED.findall(text)))
    if leftovers:
        die(f"dashboard {name} still contains {', '.join(leftovers)}")
    return text


def validate_rule(context: str, rule: dict) -> None:
    """Shared checks for one Grafana provisioning rule, market or Kubernetes.

    Grafana loads every provisioning file at startup and a rule it rejects is
    fatal for the whole process (observed 2026-09-19: CrashLoopBackOff), so the
    generator refuses to emit anything Grafana would refuse to load.
    """
    if not rule.get("condition"):
        die(f"{context}: rule {rule.get('title')!r} has no condition refId")
    ref_ids = {node["refId"] for node in rule["data"]}
    if rule["condition"] not in ref_ids:
        die(f"{context}: rule {rule.get('title')!r} condition {rule['condition']!r} is not in data")
    for node in rule["data"]:
        if node["datasourceUid"] not in ("__expr__", DATASOURCE_UID):
            die(
                f"{context}: rule {rule.get('title')!r} uses unexpected "
                f"datasourceUid {node['datasourceUid']!r}"
            )
    if len(rule["uid"]) > GRAFANA_UID_MAX:
        die(
            f"{context}: rule uid {rule['uid']!r} is longer than {GRAFANA_UID_MAX} characters "
            "(Grafana rejects a longer uid and then refuses to start)"
        )


def render_alerts(template: Path, sites: list[str]) -> dict:
    text = template.read_text(encoding="utf-8")
    text = text.replace("__DATASOURCE_UID__", DATASOURCE_UID)
    group = json.loads(text)
    group["title"] = group.get("title") or template.name
    group.pop("folderUid", None)
    rules = group.get("rules")
    if not rules:
        die(f"{template} contains no rules")

    # One absence rule per expected site. The template ships one rule carrying
    # __EXPECTED_SITE__; losing it would silently drop the coverage that catches
    # a capture host which never reported at all, so fail loudly instead.
    if not any("__EXPECTED_SITE__" in json.dumps(rule) for rule in rules):
        die(f"{template} is missing the expected-site absence rule (__EXPECTED_SITE__)")

    expanded: list[dict] = []
    for rule in rules:
        if "__EXPECTED_SITE__" not in json.dumps(rule):
            expanded.append(rule)
            continue
        for site in sites:
            clone = json.loads(json.dumps(rule).replace("__EXPECTED_SITE__", site))
            clone["uid"] = f"{rule['uid']}-{slug(site)}"
            expanded.append(clone)

    interval = group.get("interval", 60)
    rendered = {
        "orgId": 1,
        "name": group["title"],
        "folder": FOLDER_TITLE,
        "interval": f"{int(interval)}s" if isinstance(interval, int) else str(interval),
        "rules": expanded,
    }

    unresolved = sorted(set(UNRESOLVED.findall(json.dumps(rendered))))
    if unresolved:
        die(f"{template} still contains unresolved tokens: {', '.join(unresolved)}")
    uids = [rule["uid"] for rule in expanded]
    if len(set(uids)) != len(uids):
        die(f"{template} produced duplicate rule uids: {sorted(uids)}")
    # Grafana rejects rule UIDs longer than 40 characters, and a rejected
    # provisioning file is fatal for the whole Grafana process at startup
    # (observed 2026-09-19: CrashLoopBackOff on a 44-character per-site uid).
    # Fail here, where the author can shorten the template uid, not there.
    too_long = [uid for uid in uids if len(uid) > GRAFANA_UID_MAX]
    if too_long:
        die(f"{template} produced rule uids longer than {GRAFANA_UID_MAX} characters "
            f"(shorten the template uid; site suffixes are appended): {too_long}")
    for rule in expanded:
        validate_rule(str(template), rule)
    return rendered


def register_dashboard(
    rendered: str,
    path: Path,
    target: dict[str, str],
    files: dict[Path, str],
    seen_uids: dict[str, str],
    seen_assets: dict[str, str],
) -> None:
    """File one rendered dashboard, refusing uid or file-name collisions.

    Grafana files dashboards by uid and the import-ready copies all land in one
    directory, so a collision between the market and Kubernetes sets would
    silently replace one dashboard with the other.
    """
    uid = json.loads(rendered)["uid"]
    if uid in seen_uids:
        die(f"dashboard uid {uid!r} is used by both {seen_uids[uid]} and {path}")
    if path.name in seen_assets:
        die(f"dashboard file {path.name!r} is generated from both {seen_assets[path.name]} and {path}")
    seen_uids[uid] = str(path)
    seen_assets[path.name] = str(path)
    target[path.name] = rendered
    files[ASSET_DASHBOARDS / path.name] = rendered


def load_upstream_groups() -> dict[str, dict]:
    """Every vendored upstream PrometheusRule group, keyed by group name.

    The files come from fetch-upstream.py, which verifies each sha256 against
    upstream/SOURCES.json, so this reads exactly the pinned upstream revision.
    """
    vendored = sorted(path.name for path in KUBE_PROMETHEUS.glob("*-prometheusRule.yaml"))
    if vendored != sorted(UPSTREAM_RULE_FILES):
        die(
            f"{KUBE_PROMETHEUS} holds {vendored}; expected {sorted(UPSTREAM_RULE_FILES)} "
            "(the selection is fixed by fetch-upstream.py's PINS)"
        )
    groups: dict[str, dict] = {}
    for name in UPSTREAM_RULE_FILES:
        path = KUBE_PROMETHEUS / name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if document.get("kind") != "PrometheusRule":
            die(f"{path} is a {document.get('kind')!r}, expected a PrometheusRule")
        for group in document["spec"]["groups"]:
            if group["name"] in groups:
                die(f"upstream group {group['name']!r} appears in more than one vendored file")
            groups[group["name"]] = group
    return groups


def upstream_dashboards() -> list[tuple[Path, dict[str, str] | None]]:
    """Upstream dashboards to provision, with the rewrite where one applies.

    The kube-prometheus dashboards select the jobs its own Prometheus scrapes
    and are rewritten. The OpenCost and Kepler dashboards select their own
    exporters' labels (and template variables such as $ksm_job) and are
    provisioned verbatim.
    """
    vendored = sorted(path.name for path in UPSTREAM_DASHBOARDS.glob("*.json"))
    if vendored != sorted(UPSTREAM_KUBE_DASHBOARDS):
        die(
            f"{UPSTREAM_DASHBOARDS} holds {vendored}; expected {sorted(UPSTREAM_KUBE_DASHBOARDS)} "
            "(the selection is fixed by fetch-upstream.py's PINS)"
        )
    sources: list[tuple[Path, dict[str, str] | None]] = [
        (UPSTREAM_DASHBOARDS / name, SELECTOR_REWRITE) for name in sorted(UPSTREAM_KUBE_DASHBOARDS)
    ]
    sources.extend((path, None) for path in UPSTREAM_OTHER_DASHBOARDS)
    return sources


def build_recording_rules(groups: dict[str, dict]) -> dict:
    """The `record:` rules of the selected upstream groups, selectors rewritten.

    Prometheus loads this as a rule file. Alert rules stay in Grafana, so a
    group that suddenly carries one (a pin bump) has to be dealt with
    explicitly: the rule count below only covers record rules and would not
    notice a dropped alert.
    """
    selected: list[dict] = []
    for name in RECORDING_GROUPS:
        group = groups.get(name)
        if group is None:
            die(f"upstream has no group {name!r}; the vendored revision changed")
        if any("alert" in rule for rule in group["rules"]):
            die(f"upstream group {name!r} now carries alert rules; split the selection explicitly")
        rules = [substitute(rule, SELECTOR_REWRITE) for rule in group["rules"]]
        if not rules:
            die(f"upstream group {name!r} contains no rules")
        assert_selectors_rewritten(f"upstream group {name!r}", rules)
        for rule in rules:
            if not rule.get("record") or not rule.get("expr"):
                die(f"upstream group {name!r}: rule {rule!r} needs both record and expr")
        selected.append({"name": name, "rules": rules})

    total = sum(len(group["rules"]) for group in selected)
    if total != EXPECTED_RECORD_RULES:
        counts = ", ".join(f"{group['name']}={len(group['rules'])}" for group in selected)
        die(f"selected {total} recording rules, expected {EXPECTED_RECORD_RULES} ({counts})")
    return {"groups": selected}


def convert_alert_rule(rule: dict, context: str, unique_name: bool) -> dict:
    """One upstream Prometheus alerting rule -> one Grafana provisioning rule.

    The upstream expression is evaluated as an instant Prometheus query (refId
    A) and the rule fires when a math expression (refId C) sees any number:
    `is_number($A)`. Upstream expressions already embed their thresholds and
    return only the offending series, and several of them legitimately return
    the value 0 (rules ending `== 0`), so `$A > 0` would never fire for those.
    """
    alertname = rule["alert"]
    severity = (rule.get("labels") or {}).get("severity")
    if not severity:
        die(f"{context}: alert {alertname!r} has no severity label to build its uid and title from")
    rewritten = substitute(rule, SELECTOR_REWRITE)
    assert_selectors_rewritten(context, rewritten)
    annotations = {
        key: VALUE_TEMPLATE.sub("$values.A.Value", value)
        for key, value in (rewritten.get("annotations") or {}).items()
    }
    return {
        "uid": alertname if unique_name else f"{alertname}-{severity[:4]}",
        "title": alertname if unique_name else f"{alertname} ({severity})",
        "condition": "C",
        "for": rewritten.get("for") or "0s",
        "noDataState": "OK",
        "execErrState": "Error",
        "isPaused": False,
        "labels": rewritten.get("labels") or {},
        "annotations": annotations,
        "data": [
            {
                "refId": "A",
                "queryType": "",
                "relativeTimeRange": {"from": 600, "to": 0},
                "datasourceUid": DATASOURCE_UID,
                "model": {
                    "editorMode": "code",
                    "expr": rewritten["expr"],
                    "instant": True,
                    "range": False,
                    "refId": "A",
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                    "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
                },
            },
            {
                "refId": "C",
                "queryType": "",
                "relativeTimeRange": {"from": 600, "to": 0},
                "datasourceUid": "__expr__",
                "model": {
                    "datasource": {"type": "__expr__", "uid": "__expr__"},
                    "expression": "is_number($A)",
                    "refId": "C",
                    "type": "math",
                },
            },
        ],
    }


def build_kubernetes_alert_groups(groups: dict[str, dict]) -> list[dict]:
    """The selected upstream alert rules as Grafana provisioning groups.

    One upstream group maps to one Grafana group (same name, folder Kubernetes).
    An alertname that upstream ships once becomes uid == title == alertname; a
    name shipped as a warning/critical pair gets the severity appended to both,
    because Grafana keys rules by uid and requires unique titles per folder.
    """
    pairs: list[tuple[str, dict]] = []
    for name in ALERT_GROUPS:
        group = groups.get(name)
        if group is None:
            die(f"upstream has no group {name!r}; the vendored revision changed")
        if any("record" in rule for rule in group["rules"]):
            die(f"upstream group {name!r} now carries record rules; split the selection explicitly")
        pairs.extend(
            (name, rule)
            for rule in group["rules"]
            if "alert" in rule and rule["alert"] not in EXCLUDED_ALERTS
        )

    names: dict[str, int] = {}
    for _, rule in pairs:
        names[rule["alert"]] = names.get(rule["alert"], 0) + 1

    grouped: dict[str, list[dict]] = {name: [] for name in ALERT_GROUPS}
    for name, rule in pairs:
        context = f"upstream group {name!r}"
        converted = convert_alert_rule(rule, context, unique_name=names[rule["alert"]] == 1)
        validate_rule(context, converted)
        grouped[name].append(converted)

    total = sum(len(rules) for rules in grouped.values())
    if total != EXPECTED_ALERT_RULES:
        counts = ", ".join(f"{name}={len(rules)}" for name, rules in grouped.items())
        die(f"selected {total} alert rules, expected {EXPECTED_ALERT_RULES} ({counts})")
    return [
        {
            "orgId": 1,
            "name": name,
            "folder": KUBE_FOLDER_TITLE,
            "interval": "60s",
            "rules": grouped[name],
        }
        for name in ALERT_GROUPS
    ]


def build() -> dict[Path, str]:
    """Return every generated file as {path: content}."""
    files: dict[Path, str] = {}

    dashboards_dir = SOURCE / "deploy" / "grafana" / "dashboards"
    alert_templates = sorted((SOURCE / "deploy" / "grafana" / "alerts").glob("*.json.tmpl"))
    dashboard_files = sorted(dashboards_dir.glob("*.json"))
    if not dashboard_files:
        die(f"no dashboards found in {dashboards_dir}")
    if not alert_templates:
        die(f"no alert templates found in {dashboards_dir.parent / 'alerts'}")

    # Market dashboards keep the diff-logic-cells source; the Kubernetes ones
    # come from upstream/. Both sets go through the same uid and file-name
    # registry: Grafana files a dashboard by uid, so a collision would silently
    # replace one of them at provision time, and the import-ready copies land in
    # one shared directory.
    dashboard_data: dict[str, str] = {}
    kube_dashboard_data: dict[str, str] = {}
    seen_uids: dict[str, str] = {}
    seen_assets: dict[str, str] = {}

    for path in dashboard_files:
        rendered = render_dashboard(path.name, path.read_text(encoding="utf-8"))
        register_dashboard(rendered, path, dashboard_data, files, seen_uids, seen_assets)

    # Only the upstream set is selector-checked, and only after the rewrite: a
    # kube-prometheus panel still selecting a scrape job this cluster does not
    # have would render empty forever. The market dashboards are exempt — they
    # select the capture hosts' own job labels, which reach Prometheus through
    # each host's Alloy unit rather than through this cluster's collectors.
    for path, rewrite in upstream_dashboards():
        rendered = render_dashboard(path.name, path.read_text(encoding="utf-8"), rewrite)
        assert_selectors_rewritten(str(path), json.loads(rendered))
        register_dashboard(rendered, path, kube_dashboard_data, files, seen_uids, seen_assets)

    sites = expected_sites(MEASUREMENT_CONFIGMAP)
    groups = [render_alerts(template, sites) for template in alert_templates]

    upstream_groups = load_upstream_groups()
    recording_rules = build_recording_rules(upstream_groups)
    kube_groups = build_kubernetes_alert_groups(upstream_groups)

    # Grafana keys a rule group by (folder, name) and a rule by uid, so two
    # generated groups that happen to share either would silently overwrite each
    # other's rules when the provisioning files load. It also rejects a
    # provisioning file with duplicate titles in one folder, and a rejected file
    # is fatal for the whole process. Fail loudly instead.
    all_groups = [*groups, *kube_groups]
    group_names = [group["name"] for group in all_groups]
    if len(set(group_names)) != len(group_names):
        duplicated = sorted({name for name in group_names if group_names.count(name) > 1})
        die(f"generated alert groups share a name: {', '.join(duplicated)}")
    rule_uids = [rule["uid"] for group in all_groups for rule in group["rules"]]
    if len(set(rule_uids)) != len(rule_uids):
        duplicated = sorted({uid for uid in rule_uids if rule_uids.count(uid) > 1})
        die(f"generated alert rules share uids: {', '.join(duplicated)}")
    kube_titles = [rule["title"] for group in kube_groups for rule in group["rules"]]
    if len(set(kube_titles)) != len(kube_titles):
        duplicated = sorted({title for title in kube_titles if kube_titles.count(title) > 1})
        die(f"generated rules in folder {KUBE_FOLDER_TITLE!r} share titles: {', '.join(duplicated)}")

    dashboard_configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": DASHBOARDS_CONFIGMAP},
        "data": dashboard_data,
    }
    alerting_configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": ALERTING_CONFIGMAP,
            "labels": {ALERTS_SIDECAR_LABEL: "1"},
        },
        "data": {
            "rules.yaml": yaml.safe_dump(
                {"apiVersion": 1, "groups": groups},
                sort_keys=False,
                default_flow_style=False,
                width=4096,
                allow_unicode=True,
            )
        },
    }
    kube_dashboard_configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": KUBE_DASHBOARDS_CONFIGMAP},
        "data": kube_dashboard_data,
    }
    kube_alerting_configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": KUBE_ALERTING_CONFIGMAP,
            "labels": {ALERTS_SIDECAR_LABEL: "1"},
        },
        "data": {"kubernetes-rules.yaml": yaml_block({"apiVersion": 1, "groups": kube_groups})},
    }
    prometheus_rules_configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": PROM_RULES_CONFIGMAP},
        "data": {"kubernetes-recording-rules.yml": yaml_block(recording_rules)},
    }

    for configmap in (
        dashboard_configmap,
        alerting_configmap,
        kube_dashboard_configmap,
        kube_alerting_configmap,
        prometheus_rules_configmap,
    ):
        assert_configmap_budget(configmap)

    files[MANIFESTS / "grafana-dashboards-configmap.yaml"] = GENERATED_HEADER + yaml_block(dashboard_configmap)
    files[MANIFESTS / "grafana-alerting-configmap.yaml"] = GENERATED_HEADER + yaml_block(alerting_configmap)
    files[MANIFESTS / "grafana-dashboards-kubernetes-configmap.yaml"] = (
        KUBE_GENERATED_HEADER + yaml_block(kube_dashboard_configmap)
    )
    files[MANIFESTS / "grafana-alerting-kubernetes-configmap.yaml"] = (
        KUBE_GENERATED_HEADER + yaml_block(kube_alerting_configmap)
    )
    files[MANIFESTS / "prometheus-rules-configmap.yaml"] = (
        KUBE_GENERATED_HEADER + yaml_block(prometheus_rules_configmap)
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE, help="checkout of paulkiernan/diff-logic-cells")
    parser.add_argument("--check", action="store_true", help="fail if any generated file differs from disk")
    args = parser.parse_args()

    global SOURCE
    SOURCE = args.source_dir.expanduser()
    if not (SOURCE / "deploy" / "grafana").is_dir():
        die(f"{SOURCE}/deploy/grafana is not a directory (pass --source-dir or set MSR_SOURCE_DIR)")

    files = build()
    stale: list[str] = []
    for path, content in sorted(files.items()):
        relative = path.relative_to(HERE)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current != content:
                stale.append(str(relative))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {relative}")

    if args.check and stale:
        print("generated assets are out of date; run without --check:", file=sys.stderr)
        for name in stale:
            print(f"  {name}", file=sys.stderr)
        return 1
    if args.check:
        print(f"generated assets match deploy/grafana in {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
