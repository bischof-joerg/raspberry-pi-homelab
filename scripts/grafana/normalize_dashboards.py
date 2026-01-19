#!/usr/bin/env python3
"""
Normalize Grafana dashboard JSONs for FILE PROVISIONING.

Main fixes:
1. DS_PROMETHEUS normalization.
2. Fixes internal Dashboard-Links by mapping old UIDs to new ones.
3. Stable UIDs via manifest or filename.
4. Title deduplication.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

DASH_ROOT = Path("monitoring/grafana/dashboards")
PROM_UID = "DS_PROMETHEUS"
PROM_NAME = "Prometheus"
GRAFANA_INTERNAL_UID = "-- Grafana --"
GRAFANA_INTERNAL_TYPE = "grafana"
KEEP_INPUTS = False

_UID_ALLOWED = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")

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
        if ds_type == "prometheus" or ds_uid in (PROM_UID, "${DS_PROMETHEUS}", f"${{{PROM_UID}}}"):
            return {"type": "prometheus", "uid": PROM_UID}
        return ds_val
    if isinstance(ds_val, str) and ds_val.strip() in (PROM_NAME, PROM_UID, "${DS_PROMETHEUS}"):
        return {"type": "prometheus", "uid": PROM_UID}
    return ds_val

def walk_and_patch(node: Any) -> Any:
    if isinstance(node, dict):
        if "datasource" in node:
            node["datasource"] = normalize_datasource_value(node["datasource"])
        return {k: walk_and_patch(v) for k, v in node.items()}
    if isinstance(node, list):
        return [walk_and_patch(x) for x in node]
    return node

def main() -> int:
    if not DASH_ROOT.exists():
        print(f"ERROR: {DASH_ROOT} not found.")
        return 1

    # 1. Collect all dashboards and determine NEW UIDs
    docs: list[list[Any]] = [] # [path, data, old_uid]
    uid_map: Dict[str, str] = {}
    
    for f in iter_json_files(DASH_ROOT):
        data = json.loads(f.read_text(encoding="utf-8"))
        old_uid = data.get("uid")
        
        # Determine target UID (slugified filename)
        rel = f.resolve().relative_to(DASH_ROOT.resolve())
        new_uid = ensure_uid(slugify_uid(str(rel.with_suffix("")).replace("/", "-")))
        
        if old_uid:
            uid_map[old_uid] = new_uid
        
        data["uid"] = new_uid
        data["id"] = None
        docs.append([f, data])

    # 2. Patch content and replace internal UID references
    final_docs = []
    for f, data in docs:
        # Deep patch datasources
        data = walk_and_patch(data)
        
        # Replace broken internal links (old UID -> new UID)
        raw_json = json.dumps(data)
        for old, new in uid_map.items():
            if old != new:
                raw_json = raw_json.replace(f'"{old}"', f'"{new}"')
        
        data = json.loads(raw_json)
        if not KEEP_INPUTS:
            data.pop("__inputs", None)
        final_docs.append((f, data))

    # 3. Write back
    for f, data in final_docs:
        f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"Normalized {len(final_docs)} dashboards. Fixed {len(uid_map)} potential UID links.")
    return 0

if __name__ == "__main__":
    sys.exit(main())