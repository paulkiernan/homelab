#!/usr/bin/env python3
"""Vendor the upstream dashboards and rules this app provisions, byte for byte.

Why these files are committed here:

  ArgoCD deploys this app from the repository alone, so every file Grafana and
  Prometheus load at runtime has to exist in git. The kube-prometheus
  dashboards, their recording rules, and the OpenCost and Kepler dashboards are
  upstream projects with their own review and release cadence; re-deriving them
  at deploy time would need network access, a jsonnet toolchain and a moving
  target. So each source is fetched once at a pinned revision and committed,
  and generate-assets.py adapts the vendored copies offline and
  deterministically.

  Nothing under upstream/ may be hand-edited, reformatted or reordered: those
  bytes ARE the upstream revision, and upstream/SOURCES.json records the
  sha256 of every one of them. A hand edit is how a dashboard silently
  diverges from the revision this repository claims to ship, so --check holds
  each file to a hash this script owns: PINS for the four rules files and the
  two single-file dashboards, DASHBOARDS for the 16 dashboards split out of
  the kube-prometheus ConfigMapList. That list's own pin can only be enforced
  at fetch time (its bytes are not committed under upstream/), which is
  exactly why the split dashboards carry their own hashes in DASHBOARDS.

  A pin is a deliberate commit, never a side effect. To bump one, put the new
  URL or revision in PINS and run the script: it downloads first and refuses to
  write anything on a hash mismatch, printing the sha256 it actually received.
  Confirm that revision is the one you mean to vendor, paste the hash into
  PINS, and commit the script together with the re-fetched files. A pin that no
  longer matches is a prompt to look at upstream, not to re-pin quietly.

  There is no json/yaml library here on purpose: the only file that would need
  a real YAML parser is the kube-prometheus ConfigMapList, and its single
  dashboard per ConfigMap is recovered by reading one block scalar back at a
  fixed indent, with json.loads proving every extracted block. That keeps the
  script runnable from a bare Python 3 install.

Usage:

  python3 fetch-upstream.py           download every pin, rewrite upstream/
  python3 fetch-upstream.py --check   verify upstream/ offline against PINS, SOURCES.json
                                      and the per-dashboard DASHBOARDS hashes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "upstream"
SOURCES = UPSTREAM / "SOURCES.json"

KUBE_PROMETHEUS_COMMIT = "e98ba309f76b5838ef0fa89c24b73e67edf3ecd4"
KUBE_PROMETHEUS = (
    "https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/"
    f"{KUBE_PROMETHEUS_COMMIT}/manifests/"
)

# A PINS record normally says "write these bytes to this file under upstream/".
# grafana-dashboardDefinitions.yaml is the one exception: it is a single
# ConfigMapList holding 33 dashboards, so its destination is this sentinel and
# the dashboards named in DASHBOARDS are split out of it instead.
SPLIT_DASHBOARDS = "kube-prometheus/dashboards/"

# The kube-prometheus dashboards this app provisions, as {name: sha256 of the
# bytes that key holds in the pinned ConfigMapList}. The rest of the list
# targets components the local Prometheus does not scrape (apiserver,
# scheduler, controller-manager, kube-proxy, Alertmanager, Grafana), Windows
# nodes, or the multi-cluster aggregations that have no meaning in one cluster.
#
# The hashes are the vendored ones from upstream/SOURCES.json and are what
# --check compares each split dashboard against: the ConfigMapList they are cut
# from is never written to upstream/, so its PINS record (and therefore the
# list's own pin) is only enforceable while fetching. With these hashes, a hand
# edit of a split dashboard fails --check even if SOURCES.json is edited to
# match it, which is the point.
DASHBOARDS: dict[str, str] = {
    "k8s-resources-cluster.json": "37a6ba0e60d97c7e0535f5615f7e3242a706c67195688fba1a59cb48ce55c4d3",
    "k8s-resources-namespace.json": "d1a4142e91a91827994ba53e2e410afaec07e845bb44548a01059058de2cb98b",
    "k8s-resources-node.json": "5ab31515f6b1750267ac5fc06eccdee0317c6f282d1f640ebf3f631ec9dd274d",
    "k8s-resources-pod.json": "edb2e31de3ccbb152a82dd405b01f79dd71adc5f82240d38612c640cede40d61",
    "k8s-resources-workload.json": "d1d6abe96929076089c3869fd205cfaefc4ef150f69ede9d3af02252ac994a40",
    "k8s-resources-workloads-namespace.json": "4c51dd5f58bd0adc437716d121c69021eac6d05e0a4c1b0e2278ec5fca0f1dd9",
    "cluster-total.json": "ea2edc93ac2f49b55b63819feab1e0c36b57196383a607fa6abefb1d8680ab74",
    "namespace-by-pod.json": "c9e0672548c5465439c8eed25e3e1a1b11e3257da2d8916e24b6e23707fe0d03",
    "namespace-by-workload.json": "d9f94c257e5a353e353a7dd213e8b4f4ce29c557bc98b3a324c1a99c16b08285",
    "pod-total.json": "de2edbd37ec323f4e0f7d66ae5ab3be6c4a70d21f3a1f82a42d52dd714e4d5de",
    "workload-total.json": "14588ca08b77e9b2e5f87a2ea744ddf00716a9bd7c25905e116125b60fc7b9c1",
    "kubelet.json": "8d9d3bd084307a5142ed7ee6aa33c625f38b892a63e4eac1fd000fd327aedaab",
    "node-cluster-rsrc-use.json": "7b89997b56a9f7f982359608a506b27ff48e95fc5e764cff9acb767a8b4ac0a5",
    "node-rsrc-use.json": "4b866ac2c4e13a2e51ce1578a598ea7941e1ca1a4a986c651ac5dd59b5b90bde",
    "nodes.json": "898df568cad9cd8ab4a0dd55bcda29e447d4b1619d45745e590bafe983666b83",
    "persistentvolumesusage.json": "c21c46955a391edfcbb86420831e0d0c360f9232fa8c9625798251183521affb",
}

# (url, destination under upstream/, sha256 of the bytes that url serves).
PINS = [
    # kube-prometheus main e98ba309f76b5838ef0fa89c24b73e67edf3ecd4 (2026-09-18).
    (
        KUBE_PROMETHEUS + "kubernetesControlPlane-prometheusRule.yaml",
        "kube-prometheus/kubernetesControlPlane-prometheusRule.yaml",
        "757b5ad26bad2a9f04a77f8052d65724722aaa192b36499462d16ef06bd2490f",
    ),
    (
        KUBE_PROMETHEUS + "nodeExporter-prometheusRule.yaml",
        "kube-prometheus/nodeExporter-prometheusRule.yaml",
        "ae160575bd33a4d17281180caf0ccdd513957a66cb790f25627ff1dd110a9a2a",
    ),
    (
        KUBE_PROMETHEUS + "kubeStateMetrics-prometheusRule.yaml",
        "kube-prometheus/kubeStateMetrics-prometheusRule.yaml",
        "aa2eea1c3e82c6a100648c26a4f032e8831071f169ab7a5a6bc46f60d4b5ba5e",
    ),
    (
        KUBE_PROMETHEUS + "kubePrometheus-prometheusRule.yaml",
        "kube-prometheus/kubePrometheus-prometheusRule.yaml",
        "5bf4529862bf908953a6331c926d9a21435a69b0946187bbf40fcb17e62231c6",
    ),
    (
        KUBE_PROMETHEUS + "grafana-dashboardDefinitions.yaml",
        SPLIT_DASHBOARDS,
        "56e92938f62fa295002d95648def049b1706da2f7d7c0376382f362a343a4813",
    ),
    # OpenCost / Overview, adinhodovic/opencost-mixin revision 8.
    (
        "https://grafana.com/api/dashboards/22208/revisions/8/download",
        "opencost/overview.json",
        "3f6eeddce09abdf967fcf856c692125a3dbb3f01240cbd8541656ffadd603359",
    ),
    # Kepler Exporter Dashboard, matching the kepler release-0.8.0 image the
    # cluster runs. The plan of record listed a first-12 prefix of
    # 1b7268ae87ca for this URL; the bytes served there (identical across the
    # v0.7.12, v0.8.0, v0.9.0 tags and the release-0.8.0 branch, checked
    # 2026-09-19) are 937e5e5850c2... and carry the dashboard this app wants
    # (uid NhnADUW4zIBM, title "Kepler Exporter Dashboard", querying exactly
    # the kepler_container_* series the collector allow-list keeps). The
    # recorded prefix is therefore a transcription error, called out here so
    # the audit trail survives, rather than a revision that needs re-pinning.
    (
        "https://raw.githubusercontent.com/sustainable-computing-io/kepler/v0.8.0/grafana-dashboards/Kepler-Exporter.json",
        "kepler/kepler-exporter.json",
        "937e5e5850c290fd63e359f41c8dacf7bbe3b3e962a154b879f446a42abc6afe",
    ),
]

# Every data key in the ConfigMapList is written as `    <name>.json: |-` with
# the block indented six spaces (verified against the pinned revision; a
# reformat upstream would show up as a pin mismatch long before it got here).
DATA_KEY = re.compile(r"    ([A-Za-z0-9._-]+\.json): \|-\s*")
BLOCK_INDENT = 6


def die(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "homelab-fetch-upstream/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def extract_dashboards(text: str, url: str) -> dict[str, bytes]:
    """Split a kube-prometheus ConfigMapList into {destination: dashboard bytes}."""
    lines = text.split("\n")
    blocks: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        match = DATA_KEY.fullmatch(lines[index])
        if match is None:
            index += 1
            continue
        name = match.group(1)
        index += 1
        body: list[str] = []
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                body.append("")
                index += 1
                continue
            if len(line) - len(line.lstrip(" ")) < BLOCK_INDENT:
                break
            body.append(line[BLOCK_INDENT:])
            index += 1
        while body and not body[-1]:
            body.pop()
        blocks.setdefault(name, []).append("\n".join(body))

    dashboards: dict[str, bytes] = {}
    for key in DASHBOARDS:
        found = blocks.get(key)
        if not found:
            die(f"{key} is missing from {url}")
        if len(found) > 1:
            die(f"{key} appears {len(found)} times in {url}")
        content = (found[0] + "\n").encode("utf-8")
        dashboard = json.loads(content)
        if not isinstance(dashboard, dict) or not dashboard.get("uid") or not dashboard.get("title"):
            die(f"{key} in {url} is not a Grafana dashboard (needs a uid and a title)")
        dashboards[SPLIT_DASHBOARDS + key] = content
    return dashboards


def fetch() -> int:
    # Download and verify everything before writing anything, so a moved
    # upstream revision cannot leave a half-updated tree behind.
    downloads: dict[str, bytes] = {}
    for url, destination, pinned in PINS:
        data = download(url)
        actual = hashlib.sha256(data).hexdigest()
        if actual != pinned:
            die(
                f"pin mismatch for {url}\n"
                f"  pinned: {pinned}\n"
                f"  actual: {actual}\n"
                "nothing was written: confirm the revision you want, paste the actual\n"
                "hash into PINS, and commit the script with the re-fetched files"
            )
        downloads[destination] = data
        print(f"fetched {url} ({len(data)} bytes, sha256 matches pin)")

    files: dict[str, bytes] = {}
    urls: dict[str, str] = {}
    for url, destination, _ in PINS:
        if destination == SPLIT_DASHBOARDS:
            split = extract_dashboards(downloads[destination].decode("utf-8"), url)
            files.update(split)
            urls.update(dict.fromkeys(split, url))
            continue
        files[destination] = downloads[destination]
        urls[destination] = url

    sources = {
        name: {"url": urls[name], "sha256": hashlib.sha256(files[name]).hexdigest()}
        for name in sorted(files)
    }
    for name in sorted(files):
        path = UPSTREAM / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[name])
        print(f"wrote upstream/{name}")
    SOURCES.write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote upstream/SOURCES.json ({len(files)} files)")
    return 0


def check() -> int:
    if not SOURCES.is_file():
        die(f"{SOURCES.relative_to(HERE)} is missing; run the script without --check to vendor the pins")

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    problems: list[str] = []

    # SOURCES.json is the manifest itself, so it is not one of the files it lists.
    on_disk = {
        path.relative_to(UPSTREAM).as_posix()
        for path in UPSTREAM.rglob("*")
        if path.is_file() and path != SOURCES
    }
    for name in sorted(set(sources) - on_disk):
        problems.append(f"missing from upstream/: {name}")
    for name in sorted(on_disk - set(sources)):
        problems.append(f"upstream/{name} is not in SOURCES.json (remove it or add a pin)")

    for name in sorted(set(sources) & on_disk):
        actual = hashlib.sha256((UPSTREAM / name).read_bytes()).hexdigest()
        if actual != sources[name]["sha256"]:
            problems.append(
                f"hash drift in upstream/{name}\n"
                f"    SOURCES.json: {sources[name]['sha256']}\n"
                f"    on disk:      {actual}"
            )

    for url, destination, pinned in PINS:
        if destination == SPLIT_DASHBOARDS:
            for key, dashboard_hash in DASHBOARDS.items():
                name = SPLIT_DASHBOARDS + key
                record = sources.get(name)
                if record is None:
                    problems.append(f"SOURCES.json has no entry for {name} of {url}")
                elif record["url"] != url:
                    problems.append(f"upstream/{name} records {record['url']}, not {url}")
                # The ConfigMapList's own bytes are never written to upstream/, so its
                # PINS record is only enforceable while fetching. This is the check that
                # survives offline: a hand edit of a split dashboard fails even when
                # SOURCES.json is edited to match it.
                if name in on_disk:
                    actual = hashlib.sha256((UPSTREAM / name).read_bytes()).hexdigest()
                    if actual != dashboard_hash:
                        problems.append(
                            f"hash drift in upstream/{name}\n"
                            f"    DASHBOARDS: {dashboard_hash}\n"
                            f"    on disk:    {actual}"
                        )
            continue
        record = sources.get(destination)
        if record is None:
            problems.append(f"SOURCES.json has no entry for the pinned destination {destination}")
            continue
        if record["url"] != url:
            problems.append(f"upstream/{destination} records url {record['url']}, not the pinned {url}")
        if record["sha256"] != pinned:
            problems.append(
                f"upstream/{destination} records {record['sha256']}, not the pinned {pinned}"
            )

    if problems:
        print("upstream/ does not match SOURCES.json, PINS and DASHBOARDS:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"upstream/ matches SOURCES.json, PINS and DASHBOARDS ({len(sources)} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify upstream/ against SOURCES.json, PINS and DASHBOARDS; no network access",
    )
    args = parser.parse_args()
    return check() if args.check else fetch()


if __name__ == "__main__":
    raise SystemExit(main())
