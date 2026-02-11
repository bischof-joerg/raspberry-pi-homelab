#!/usr/bin/env python3
"""
Normalize Grafana dashboard JSONs for FILE PROVISIONING.

Main fixes:
1. DS_PROMETHEUS normalization.
2. Fix internal dashboard links by mapping old UIDs to new ones.
3. Stable UIDs via filename.
4. VictoriaLogs dashboard (gnetId 22759) normalization for non-K8s environments.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROM_UID = "DS_PROMETHEUS"
PROM_NAME = "Prometheus"
GRAFANA_INTERNAL_UID = "-- Grafana --"
GRAFANA_INTERNAL_TYPE = "grafana"

VLOGS_UID = "victorialogs"
VLOGS_NAME = "VictoriaLogs"
VLOGS_TYPE = "victoriametrics-logs-datasource"

KEEP_INPUTS = False

_UID_ALLOWED = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")

# --- VictoriaLogs Explorer (gnet 22759) environment normalization ---
# The upstream dashboard is Kubernetes-oriented; in this homelab we ingest docker/journald logs.
_K8S_TO_HOMELAB_FIELD_MAP = {
    "kubernetes.container_name": "container_name",
    "kubernetes.pod_labels.app.kubernetes.io/name": "service",
    "kubernetes.pod_namespace": "namespace",
}

# Upstream contains: AND ($query != "" or 1==1) which can collapse to invalid LogsQL (" != """).
_BAD_OPTIONAL_QUERY_PATTERNS = (
    ' AND ($query != "" or 1==1)',
    " AND ($query != '' or 1==1)",
    ' AND ($query != \\"\\\\" or 1==1)',
)


def dash_root() -> Path:
    p = Path("stacks/monitoring/grafana/dashboards")
    if p.exists():
        return p
    return Path("monitoring/grafana/dashboards")


def slugify_uid(s: str, limit: int = 40) -> str:
    s = (s or "").strip().lower().replace(".", "-")
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:limit] or "dashboard"


def ensure_uid(uid: str) -> str:
    uid = (uid or "").strip()
    return uid if _UID_ALLOWED.match(uid) else slugify_uid(uid)


def iter_json_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.json"):
        if p.is_file() and p.name != "manifest.json" and not p.name.startswith("."):
            yield p


def normalize_datasource_value(ds_val: Any) -> Any:
    if isinstance(ds_val, dict):
        if ds_val.get("type") == GRAFANA_INTERNAL_TYPE or ds_val.get("uid") == GRAFANA_INTERNAL_UID:
            return ds_val

        ds_type, ds_uid = ds_val.get("type"), ds_val.get("uid")

        # Prometheus normalization
        if ds_type == "prometheus" or ds_uid in (PROM_UID, "${DS_PROMETHEUS}", f"${{{PROM_UID}}}"):
            return {"type": "prometheus", "uid": PROM_UID}

        # VictoriaLogs normalization
        if ds_type == VLOGS_TYPE or ds_uid in (
            VLOGS_UID,
            "${DS_VICTORIALOGS}",
            "${victorialogs}",
            f"${{{VLOGS_UID}}}",
        ):
            return {"type": VLOGS_TYPE, "uid": VLOGS_UID}

        return ds_val

    # String placeholders -> normalize to dict
    if isinstance(ds_val, str):
        v = ds_val.strip()
        if v in (PROM_NAME, PROM_UID, "${DS_PROMETHEUS}"):
            return {"type": "prometheus", "uid": PROM_UID}
        if v in (VLOGS_NAME, VLOGS_UID, "${DS_VICTORIALOGS}"):
            return {"type": VLOGS_TYPE, "uid": VLOGS_UID}

    return ds_val


def patch_promql_expr(expr: Any, rel_path: str) -> Any:
    if not isinstance(expr, str):
        return expr

    # docker-engine-health-21040 expects instance=~'rpi-hub' upstream; in our setup we match job="docker-engine"
    if rel_path.endswith("docker/docker-engine-health-21040.json"):
        expr = expr.replace("{instance=~'rpi-hub'}", '{job="docker-engine"}')
        expr = expr.replace('{instance=~"rpi-hub"}', '{job="docker-engine"}')
        expr = expr.replace('{instance=~"rpi-hub.*"}', '{job="docker-engine"}')
    return expr


def _patch_vlogs_explorer_strings(s: str) -> str:
    for old, new in _K8S_TO_HOMELAB_FIELD_MAP.items():
        s = s.replace(old, new)

    for pat in _BAD_OPTIONAL_QUERY_PATTERNS:
        s = s.replace(pat, "")

    # common variant without leading space
    s = s.replace('AND ($query != "" or 1==1)', "")
    return s


def patch_logsql_for_environment(node: Any, rel_path: str) -> Any:
    if not isinstance(node, (dict, list)):
        return node

    # apply ONLY to that dashboard file
    if not rel_path.endswith(
        "victorialogs/victorialogs-explorer-22759.json"
    ) and not rel_path.endswith("victorialogs-explorer-22759.json"):
        return node

    def walk(x: Any) -> Any:
        if isinstance(x, dict):
            out: dict[str, Any] = {}
            for k, v in x.items():
                if k == "field" and isinstance(v, str):
                    out[k] = _patch_vlogs_explorer_strings(v)
                    continue

                if isinstance(v, str) and k in (
                    "expr",
                    "definition",
                    "query",
                    "url",
                    "legendFormat",
                    "title",
                ):
                    out[k] = _patch_vlogs_explorer_strings(v)
                    continue

                if isinstance(v, str) and ("kubernetes." in v or '$query != "" or 1==1' in v):
                    out[k] = _patch_vlogs_explorer_strings(v)
                    continue

                out[k] = walk(v)
            return out

        if isinstance(x, list):
            return [walk(i) for i in x]

        if isinstance(x, str) and ("kubernetes." in x or '$query != "" or 1==1' in x):
            return _patch_vlogs_explorer_strings(x)

        return x

    return walk(node)


def walk_and_patch_with_context(node: Any, rel_path: str) -> Any:
    if isinstance(node, dict):
        if "datasource" in node:
            node["datasource"] = normalize_datasource_value(node["datasource"])
        if "expr" in node:
            node["expr"] = patch_promql_expr(node["expr"], rel_path)

        node = patch_logsql_for_environment(node, rel_path)
        return {k: walk_and_patch_with_context(v, rel_path) for k, v in node.items()}

    if isinstance(node, list):
        return [walk_and_patch_with_context(x, rel_path) for x in node]

    return node


def main() -> int:
    root = dash_root()
    if not root.exists():
        print(f"ERROR: dashboards root not found: {root}")
        return 1

    docs: list[tuple[Path, dict]] = []
    uid_map: dict[str, str] = {}

    # phase 1: compute deterministic uid per file and build old->new mapping
    for f in iter_json_files(root):
        data = json.loads(f.read_text(encoding="utf-8"))
        old_uid = data.get("uid")

        rel = f.resolve().relative_to(root.resolve())
        new_uid = ensure_uid(slugify_uid(str(rel.with_suffix("")).replace("/", "-")))

        if old_uid:
            uid_map[str(old_uid)] = new_uid

        data["uid"] = new_uid
        data["id"] = None
        docs.append((f, data))

    # phase 2: patch datasources/queries and rewrite internal links using uid_map
    final_docs: list[tuple[Path, dict]] = []
    for f, data in docs:
        rel = str(f.resolve().relative_to(root.resolve())).replace("\\", "/")
        data = walk_and_patch_with_context(data, rel)

        raw_json = json.dumps(data)
        for old, new in uid_map.items():
            if old != new:
                raw_json = raw_json.replace(f'"{old}"', f'"{new}"')

        data = json.loads(raw_json)
        if not KEEP_INPUTS:
            data.pop("__inputs", None)

        final_docs.append((f, data))

    for f, data in final_docs:
        f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"Normalized {len(final_docs)} dashboards. Fixed {len(uid_map)} potential UID links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
