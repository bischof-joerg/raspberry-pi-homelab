#!/usr/bin/env python3
"""
Normalize Grafana dashboard JSONs for FILE PROVISIONING.

Goals (for your setup):
- Ensure all Prometheus datasource references point to uid "DS_PROMETHEUS"
  (NOT "${DS_PROMETHEUS}" because provisioning does not resolve that placeholder).
- Keep Grafana internal datasource ("-- Grafana --") untouched.
- Ensure stable dashboard.uid (prefer manifest.json if present).
- Set dashboard.id to null for provisioning.
- Avoid duplicate dashboard titles within the same folder (Grafana will restrict
  provisioning DB write access when duplicates exist).
- Optionally remove __inputs to avoid confusion.

Repo conventions:
- Dashboards live under: monitoring/grafana/dashboards/<folder>/*.json
- Optional manifest:       monitoring/grafana/dashboards/manifest.json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

DASH_ROOT = Path("monitoring/grafana/dashboards")

# This must match your provisioned datasource UID in grafana/provisioning/datasources/prometheus.yml
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
    s = (s or "").strip()
    s = s.lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    s = s[:limit]
    return s or "dashboard"


def ensure_uid(uid: str) -> str:
    uid = (uid or "").strip()
    if _UID_ALLOWED.match(uid):
        return uid
    # Keep gnet-ish prefixes somewhat readable when possible and restrict to allowed chars and length
    return slugify_uid(uid)


def iter_json_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.json"):
        if p.is_file():
            yield p


@dataclass(frozen=True)
class ManifestEntry:
    folder: str
    filename: str
    uid: Optional[str] = None


def load_manifest(manifest_path: Path) -> Dict[Path, ManifestEntry]:
    """
    Expected shape (example):
    {
      "dashboards": [
        {"folder":"docker","filename":"docker-engine-health-21040.json","uid":"gnet-docker-21040"},
        ...
      ]
    }
    """
    if not manifest_path.exists():
        return {}

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"manifest.json is invalid JSON: {e}")

    out: Dict[Path, ManifestEntry] = {}
    for d in data.get("dashboards", []):
        folder = d.get("folder")
        filename = d.get("filename")
        if not folder or not filename:
            continue
        uid = d.get("uid")
        entry = ManifestEntry(folder=str(folder), filename=str(filename), uid=str(uid) if uid else None)
        out[(DASH_ROOT / entry.folder / entry.filename).resolve()] = entry
    return out


# ----------------------------
# Core patching logic
# ----------------------------

def is_grafana_internal_ds(ds_obj: Dict[str, Any]) -> bool:
    return ds_obj.get("type") == GRAFANA_INTERNAL_TYPE or ds_obj.get("uid") == GRAFANA_INTERNAL_UID


def prom_ds_object() -> Dict[str, str]:
    return {"type": "prometheus", "uid": PROM_UID}


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
        if is_grafana_internal_ds(ds_val):
            return ds_val

        ds_type = ds_val.get("type")
        ds_uid = ds_val.get("uid")
        ds_name = ds_val.get("name")

        # If it looks like Prometheus in any way, normalize to uid DS_PROMETHEUS.
        looks_like_prom = (
            ds_type == "prometheus"
            or ds_uid in (PROM_UID, f"${{{PROM_UID}}}", "${DS_PROMETHEUS}")
            or ds_name == PROM_NAME
        )
        if looks_like_prom:
            ds_val["type"] = "prometheus"
            ds_val["uid"] = PROM_UID
            # Remove conflicting keys if present
            if "name" in ds_val:
                ds_val.pop("name", None)
        return ds_val

    # String form
    if isinstance(ds_val, str):
        s = ds_val.strip()
        if s == GRAFANA_INTERNAL_UID:
            return {"type": GRAFANA_INTERNAL_TYPE, "uid": GRAFANA_INTERNAL_UID}

        # Common Prometheus variants (including the placeholder that breaks provisioning)
        if s in (PROM_NAME, PROM_UID, "${DS_PROMETHEUS}", f"${{{PROM_UID}}}"):
            return prom_ds_object()

        # Unknown string: leave it as-is (better than breaking other plugins)
        return ds_val

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


def contains_angular(node: Any) -> bool:
    """
    Best-effort detection of Angular panels (deprecated).
    """
    if isinstance(node, dict):
        if node.get("type") == "angular":
            return True
        return any(contains_angular(v) for v in node.values())
    if isinstance(node, list):
        return any(contains_angular(v) for v in node)
    return False


def make_default_uid_for_file(path: Path) -> str:
    rel = path.resolve().relative_to(DASH_ROOT.resolve())
    # e.g. docker/docker-engine-health-21040 -> docker-docker-engine-health-21040
    return ensure_uid(slugify_uid(str(rel.with_suffix("")).replace("/", "-")))


def ensure_unique_titles_per_folder(docs: Iterable[Tuple[Path, Dict[str, Any]]]) -> None:
    """
    Grafana provisioning can become read-only if duplicate titles exist in the same folder.
    We ensure uniqueness by suffixing duplicates with " (<uid>)".
    """
    seen: Dict[str, Set[str]] = {}  # folder_key -> set of titles
    for fpath, dash in docs:
        folder_key = str(fpath.parent.resolve())
        title = str(dash.get("title") or "").strip() or "Dashboard"
        uid = str(dash.get("uid") or "").strip() or "unknown"

        used = seen.setdefault(folder_key, set())
        if title not in used:
            used.add(title)
            continue

        # Duplicate title: disambiguate
        new_title = f"{title} ({uid})"
        # If still duplicated, add incremental suffix
        i = 2
        while new_title in used:
            new_title = f"{title} ({uid}-{i})"
            i += 1

        dash["title"] = new_title
        used.add(new_title)


def main() -> int:
    if not DASH_ROOT.exists():
        print(f"ERROR: {DASH_ROOT} not found (run from repo root).", file=sys.stderr)
        return 2

    manifest_path = DASH_ROOT / "manifest.json"
    manifest_map = load_manifest(manifest_path)

    # Load all dashboards
    docs: list[Tuple[Path, Dict[str, Any]]] = []
    for f in iter_json_files(DASH_ROOT):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: invalid JSON: {f} ({e})", file=sys.stderr)
            return 3
        if not isinstance(data, dict):
            print(f"ERROR: dashboard JSON is not an object: {f}", file=sys.stderr)
            return 3
        docs.append((f, data))

    # Assign/normalize UIDs + patch content
    used_uids: Set[str] = set()
    angular_files: list[Path] = []

    for f, dash in docs:
        # Provisioning expects id null/absent. Use null for explicitness.
        dash["id"] = None

        # Prefer manifest UID if present
        entry = manifest_map.get(f.resolve())
        if entry and entry.uid:
            dash_uid = ensure_uid(entry.uid)
        else:
            # If existing uid is present, normalize it; otherwise derive from filename
            existing = dash.get("uid")
            if isinstance(existing, str) and existing.strip():
                dash_uid = ensure_uid(existing.strip())
            else:
                dash_uid = make_default_uid_for_file(f)

        # Ensure uniqueness across repo (defensive)
        base = dash_uid
        i = 2
        while dash_uid in used_uids:
            dash_uid = ensure_uid(f"{base}-{i}")
            i += 1
        dash["uid"] = dash_uid
        used_uids.add(dash_uid)

        # Patch datasources recursively
        dash = walk_and_patch(dash)

        # Remove __inputs unless explicitly kept
        if not KEEP_INPUTS:
            dash.pop("__inputs", None)

        # Angular detection (non-fatal)
        if contains_angular(dash):
            angular_files.append(f)

    # Ensure unique titles per folder
    ensure_unique_titles_per_folder(docs)

    # Write back
    for f, dash in docs:
        f.write_text(json.dumps(dash, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Normalized dashboards: {len(docs)}")
    if angular_files:
        print("WARNING: Angular panels detected (deprecated):")
        for p in angular_files:
            print(f"  - {p}")

    # Quick guard: prove that no dashboard still references the broken placeholder
    # (datasource uid literal "${DS_PROMETHEUS}")
    bad_hits = 0
    for f in iter_json_files(DASH_ROOT):
        txt = f.read_text(encoding="utf-8", errors="replace")
        if '"uid": "${DS_PROMETHEUS}"' in txt:
            bad_hits += 1
            print(f"WARNING: still contains uid placeholder '${{DS_PROMETHEUS}}': {f}")
    if bad_hits:
        print("WARNING: Some dashboards still contain '${DS_PROMETHEUS}'. This will break file provisioning.")
        # Non-fatal; you may choose to return 4 here.

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
