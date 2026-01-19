#!/usr/bin/env python3
"""
Normalize Grafana dashboard JSONs for FILE PROVISIONING.

Goals:
- Ensure all Prometheus datasource references point to uid "DS_PROMETHEUS".
- Fix internal dashboard links by mapping old UIDs to new slugified UIDs.
- Ensure stable dashboard.uid (prefer manifest.json or filename-based).
- Set dashboard.id to null for provisioning.
- Avoid duplicate dashboard titles within the same folder.
- Optionally remove __inputs to avoid confusion.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

DASH_ROOT = Path("monitoring/grafana/dashboards")

# Provisioned datasource configuration
# must matchprovisioned datasource UID in grafana/provisioning/datasources/prometheus.yml
PROM_UID = "DS_PROMETHEUS"
PROM_NAME = "Prometheus"
# Grafana "internal" datasource marker used for annotations.
GRAFANA_INTERNAL_UID = "-- Grafana --"
GRAFANA_INTERNAL_TYPE = "grafana"

# If true, we keep __inputs. For provisioning, it's typically noise.
KEEP_INPUTS = False

# ----------------------------
# Helpers
# ----------------------------

_UID_ALLOWED = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


def slugify_uid(s: str, limit: int = 40) -> str:
    # 1. Lowercase and replace dots (common in filenames) with dashes
    s = (s or "").strip().lower().replace(".", "-")
    # 2. Remove anything not alphanumeric, dash, or underscore
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    # 3. Collapse multiple dashes and trim edges
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:limit] or "dashboard"


def ensure_uid(uid: str) -> str:
    uid = (uid or "").strip()
    if _UID_ALLOWED.match(uid):
        return uid
    # Keep gnet-ish prefixes somewhat readable when possible and restrict to allowed chars and length
    return slugify_uid(uid)


def iter_json_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.json"):
        if p.is_file() and not p.name.startswith(".") and p.name != "manifest.json":
            yield p


@dataclass(frozen=True)
class ManifestEntry:
    folder: str
    filename: str
    uid: Optional[str] = None


def load_manifest(manifest_path: Path) -> Dict[Path, ManifestEntry]:
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"manifest.json is invalid JSON: {e}")

    out: Dict[Path, ManifestEntry] = {}
    for d in data.get("dashboards", []):
        folder, filename = d.get("folder"), d.get("filename")
        if not folder or not filename:
            continue
        uid = d.get("uid")
        entry = ManifestEntry(folder=str(folder), filename=str(filename), uid=str(uid) if uid else None)
        out[(DASH_ROOT / entry.folder / entry.filename).resolve()] = entry
    return out


# ----------------------------
# Core patching logic
# ----------------------------

def normalize_datasource_value(ds_val: Any) -> Any:
    """
    Normalize various datasource representations:

    - {"type":"prometheus","uid":"..."}            -> uid=DS_PROMETHEUS
    - {"uid":"${DS_PROMETHEUS}"} (missing type)    -> assume prometheus
    - "Prometheus" or "${DS_PROMETHEUS}"           -> convert to object
    - {"type":"grafana","uid":"-- Grafana --"}     -> keep
    """
    # Object form
    if isinstance(ds_val, dict):
        if ds_val.get("type") == GRAFANA_INTERNAL_TYPE or ds_val.get("uid") == GRAFANA_INTERNAL_UID:
            return ds_val

        ds_type, ds_uid, ds_name = ds_val.get("type"), ds_val.get("uid"), ds_val.get("name")
        
        # If it looks like Prometheus in any way, normalize to uid DS_PROMETHEUS.
        looks_like_prom = (
            ds_type == "prometheus"
            or ds_uid in (PROM_UID, f"${{{PROM_UID}}}", "${DS_PROMETHEUS}")
            or ds_name == PROM_NAME
        )
        if looks_like_prom:
            return {"type": "prometheus", "uid": PROM_UID}
        return ds_val

    # String form
    if isinstance(ds_val, str):
        s = ds_val.strip()
        if s == GRAFANA_INTERNAL_UID:
            return {"type": GRAFANA_INTERNAL_TYPE, "uid": GRAFANA_INTERNAL_UID}
        # Common Prometheus variants (including the placeholder that breaks provisioning)
        if s in (PROM_NAME, PROM_UID, "${DS_PROMETHEUS}", f"${{{PROM_UID}}}"):
            return {"type": "prometheus", "uid": PROM_UID}
    
    return ds_val


def walk_and_patch(node: Any) -> Any:
    """
    Recursively patch datasource blocks in a generic way.
    """
    if isinstance(node, dict):
        # Normalize datasource fields
        if "datasource" in node:
            node["datasource"] = normalize_datasource_value(node["datasource"])

        # Some panels use "targets": [{"datasource": ...}, ...]
        # walk recursively for all children
        for k, v in list(node.items()):
            node[k] = walk_and_patch(v)
        return node
    
    if isinstance(node, list):
        return [walk_and_patch(x) for x in node]
    
    return node


def ensure_unique_titles_per_folder(docs: Iterable[Tuple[Path, Dict[str, Any]]]) -> None:
    seen: Dict[str, Set[str]] = {}
    for fpath, dash in docs:
        folder_key = str(fpath.parent.resolve())
        title = str(dash.get("title") or "").strip() or "Dashboard"
        uid = str(dash.get("uid") or "").strip() or "unknown"
        used = seen.setdefault(folder_key, set())
        
        new_title, i = title, 2
        while new_title in used:
            new_title = f"{title} ({uid})" if i == 2 else f"{title} ({uid}-{i})"
            i += 1
        dash["title"] = new_title
        used.add(new_title)


def main() -> int:
    if not DASH_ROOT.exists():
        print(f"ERROR: {DASH_ROOT} not found.", file=sys.stderr)
        return 2

    manifest_map = load_manifest(DASH_ROOT / "manifest.json")
    docs: list[Tuple[Path, Dict[str, Any]]] = []
    uid_mapping: Dict[str, str] = {}  # Map Old UID -> New UID for fixing links

    # Step 1: Load and determine NEW UIDs
    for f in iter_json_files(DASH_ROOT):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: invalid JSON: {f} ({e})", file=sys.stderr)
            return 3
        
        old_uid = data.get("uid")
        
        # Determine target UID
        entry = manifest_map.get(f.resolve())
        if entry and entry.uid:
            new_uid = ensure_uid(entry.uid)
        elif old_uid and _UID_ALLOWED.match(old_uid):
            new_uid = old_uid
        else:
            rel = f.resolve().relative_to(DASH_ROOT.resolve())
            new_uid = ensure_uid(slugify_uid(str(rel.with_suffix("")).replace("/", "-")))
            
        if old_uid and old_uid != new_uid:
            uid_mapping[old_uid] = new_uid
            
        data["uid"] = new_uid
        data["id"] = None
        docs.append((f, data))

    # Step 2: Global Search & Replace for UID links and Patch Content
    normalized_docs: list[Tuple[Path, Dict[str, Any]]] = []
    for f, dash in docs:
        # Convert to string to replace all internal references to old UIDs
        dump = json.dumps(dash)
        for old_uid, new_uid in uid_mapping.items():
            dump = dump.replace(f'"{old_uid}"', f'"{new_uid}"')
        
        dash = json.loads(dump)
        dash = walk_and_patch(dash)
        
        if not KEEP_INPUTS:
            dash.pop("__inputs", None)
            
        normalized_docs.append((f, dash))

    # Step 3: Title Deduplication
    ensure_unique_titles_per_folder(normalized_docs)

    # Step 4: Write back
    for f, dash in normalized_docs:
        f.write_text(json.dumps(dash, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Successfully normalized {len(normalized_docs)} dashboards and updated {len(uid_mapping)} internal links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())