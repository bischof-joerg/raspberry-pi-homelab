#!/usr/bin/env python3

# Normalize Grafana dashboard JSON files for consistent UIDs and datasource references.
# This helps avoid provisioning conflicts and ensures dashboards use the expected Prometheus datasource.
# Usage: python3 normalize_dashboards.py

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Set, Tuple

ROOT = Path("monitoring/grafana/dashboards")
PROM_DS_UID = "${DS_PROMETHEUS}"

def slugify_uid(s: str) -> str:
    # Grafana UID is typically limited; keep it short & safe
    s = s.lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:40] or "dashboard"

def load_manifest_uids(manifest_path: Path) -> Dict[Path, str]:
    """
    Map absolute file path -> desired UID from manifest.
    """
    if not manifest_path.exists():
        return {}

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: Dict[Path, str] = {}
    for d in data.get("dashboards", []):
        folder = d["folder"]
        filename = d["filename"]
        uid = d.get("uid")
        if uid:
            out[(ROOT / folder / filename).resolve()] = uid
    return out

def iter_json_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.json"):
        if p.is_file():
            yield p

def patch_datasource(node: Any) -> None:
    """
    Recursively patch Prometheus datasource references to use ${DS_PROMETHEUS}.
    Handles common patterns:
      "datasource": {"type": "prometheus", "uid": "..."}
    """
    if isinstance(node, dict):
        ds = node.get("datasource")
        if isinstance(ds, dict):
            if ds.get("type") == "prometheus":
                ds["uid"] = PROM_DS_UID

        # Templating variables sometimes carry datasource blocks too
        if node.get("type") in ("query", "datasource") and isinstance(node.get("datasource"), dict):
            if node["datasource"].get("type") == "prometheus":
                node["datasource"]["uid"] = PROM_DS_UID

        for v in node.values():
            patch_datasource(v)

    elif isinstance(node, list):
        for it in node:
            patch_datasource(it)

def contains_angular(node: Any) -> bool:
    if isinstance(node, dict):
        if node.get("type") == "angular":
            return True
        return any(contains_angular(v) for v in node.values())
    if isinstance(node, list):
        return any(contains_angular(v) for v in node)
    return False

def main() -> int:
    manifest = Path("monitoring/grafana/dashboards/manifest.json")
    manifest_uids = load_manifest_uids(manifest)

    if not ROOT.exists():
        print(f"ERROR: {ROOT} not found", file=sys.stderr)
        return 2

    used_uids: Set[str] = set()
    patched: int = 0
    angular_hits: list[Path] = []

    # First pass: read all UIDs to detect duplicates
    all_docs: list[Tuple[Path, Dict[str, Any]]] = []
    for f in iter_json_files(ROOT):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                all_docs.append((f, data))
        except Exception as e:
            print(f"ERROR: invalid JSON: {f} ({e})", file=sys.stderr)
            return 3

    for f, data in all_docs:
        # Normalize for provisioning
        data["id"] = None

        # Prefer manifest UID for files that are in the manifest
        desired = manifest_uids.get(f.resolve())
        if desired:
            data["uid"] = desired
        else:
            # Ensure we have *some* stable UID
            existing = data.get("uid")
            if not isinstance(existing, str) or not existing.strip():
                # derive from relative path
                rel = f.relative_to(ROOT)
                data["uid"] = slugify_uid(str(rel.with_suffix("")).replace("/", "-"))
            else:
                data["uid"] = slugify_uid(existing)

        # Ensure uniqueness inside the repo (avoid provisioning collisions)
        uid = data["uid"]
        base = uid
        i = 2
        while uid in used_uids:
            uid = slugify_uid(f"{base}-{i}")
            i += 1
        data["uid"] = uid
        used_uids.add(uid)

        # Patch Prometheus datasources
        patch_datasource(data)

        # Optional cleanup: If present, keep gnet metadata but remove import-time __inputs to reduce noise
        if "__inputs" in data:
            # Keep if you want, but it often causes confusion; remove for IaC clarity
            data.pop("__inputs", None)

        # Track Angular usage
        if contains_angular(data):
            angular_hits.append(f)

        f.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        patched += 1

    print(f"Normalized dashboards: {patched}")
    if angular_hits:
        print("WARNING: Angular panels detected in:")
        for p in angular_hits:
            print(f"  - {p}")
        # Non-fatal; you decide whether to fail hard here.

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
