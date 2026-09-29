# tests/guards/test_54_vector_config_hash.py
#
# R1.12 (first slice of F1/F29, per-service variant): a change to stacks/monitoring/vector/vector.yaml
# must recreate vector on deploy. deploy.sh hashes the file's content into VECTOR_CONFIG_HASH and
# compose puts it on vector as the `homelab.config-hash` label; a new value makes compose recreate
# the container. The global MONITORING_CONFIG_HASH does not cover vector.yaml (F1).
#
# Static on purpose: deploy.sh is Pi-only and never executed here (C5). The runtime proof is
# tests/postdeploy/test_40_vector_pipeline.py::test_vector_label_matches_config_hash.

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy.sh"
COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
VECTOR_LABEL = "homelab.config-hash=${VECTOR_CONFIG_HASH:-unset}"
VECTOR_HASH_ASSIGNMENT = (
    'VECTOR_CONFIG_HASH="$(compute_file_hash "$REPO_ROOT/stacks/monitoring/vector/vector.yaml")"'
)


def _deploy() -> str:
    return DEPLOY.read_text(encoding="utf-8")


def _function(name: str) -> str:
    m = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}", _deploy(), flags=re.MULTILINE | re.DOTALL)
    assert m, f"❌ deploy.sh has no function {name}().\nFix: add it."
    return m.group(1)


def test_vector_carries_its_config_hash_label() -> None:
    labels = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]["vector"].get(
        "labels", []
    )
    assert VECTOR_LABEL in [str(label) for label in labels], (
        f"❌ vector lacks the label {VECTOR_LABEL!r} (F29); found {labels}.\n"
        "Fix: add it under vector's labels, so a vector.yaml change recreates the container."
    )


def test_compute_file_hash_hashes_content_and_refuses_missing_files() -> None:
    body = _function("compute_file_hash")
    assert "sha256sum" in body and "die" in body, (
        "❌ compute_file_hash() must hash with sha256sum and die on a missing file (F2).\n"
        f"Body:\n{body}"
    )
    assert "[[ -f" in body, (
        "❌ compute_file_hash() does not check that each file exists (F2: a skipped file "
        'silently drops out of the hash).\nFix: `[[ -f "$f" ]] || die ...` for every argument.'
    )


def test_deploy_computes_vector_hash_over_vector_yaml() -> None:
    assert VECTOR_HASH_ASSIGNMENT in _deploy(), (
        "❌ deploy.sh does not compute VECTOR_CONFIG_HASH over stacks/monitoring/vector/vector.yaml."
        f"\nFix: {VECTOR_HASH_ASSIGNMENT}"
    )


def test_deploy_exports_vector_hash_before_compose_up() -> None:
    text = _deploy()
    export = text.find("export VECTOR_CONFIG_HASH")
    up = text.find("up -d")
    assert export != -1 and up != -1 and export < up, (
        "❌ deploy.sh must `export VECTOR_CONFIG_HASH` before the first `compose ... up -d`, "
        "otherwise compose renders the label as `unset`.\nFix: export it next to "
        "MONITORING_CONFIG_HASH."
    )
