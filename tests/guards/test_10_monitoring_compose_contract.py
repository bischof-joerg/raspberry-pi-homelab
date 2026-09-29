from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from tests._lib.compose import render_compose

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "stacks/monitoring/compose/.env.example"
MONITORING_DOC = REPO_ROOT / "docs/monitoring.md"

# Finding F46: `privileged: true` is an exception that needs an ADR (.claude/rules/docs-adr.md).
# Each entry maps a service to the ADR that records why it is privileged. Dropping `privileged`
# from a service (F46 step 4) must remove its entry here.
PRIVILEGED_ALLOWLIST = {
    "cadvisor": "docs/architecture/adr/ADR-0010-cadvisor-privileged-exception.md",
}
# F46 step 4: the ADR that records cadvisor running without `privileged` (supersedes ADR-0010).
CADVISOR_ADR = "docs/architecture/adr/ADR-0011-cadvisor-unprivileged.md"

REQUIRED_SERVICES = {
    "victoriametrics",
    "vmagent",
    "vmalert",
    "alertmanager",
    "grafana",
    "node-exporter",
    "cadvisor",
    "victorialogs",
    "vector",
}

OPTIONAL_SERVICES = {}

# Policy: Prometheus runtime must not exist in the monitoring stack.
BANNED_SERVICES = {"prometheus"}


def test_compose_renders():
    assert COMPOSE_FILE.exists(), f"Missing {COMPOSE_FILE}"
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    assert "services" in data and isinstance(data["services"], dict), "compose has no services"


def test_required_services_present_and_banned_absent():
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    services = set(data["services"].keys())

    missing = sorted(REQUIRED_SERVICES - services)
    assert not missing, "Missing required monitoring services:\n" + "\n".join(missing)

    present_banned = sorted(BANNED_SERVICES & services)
    assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)


def test_grafana_datasource_does_not_point_to_prometheus_runtime():
    """
    Static guard: Grafana may use datasource type 'prometheus' (PromQL compatibility),
    but its URL must not point at a Prometheus runtime service/host.
    """
    prov_dir = REPO_ROOT / "stacks/monitoring/grafana/provisioning/datasources"
    if not prov_dir.exists():
        return

    ymls = sorted(list(prov_dir.rglob("*.yml")) + list(prov_dir.rglob("*.yaml")))
    assert ymls, f"No datasource provisioning files found in {prov_dir}"

    bad = []
    for f in ymls:
        txt = f.read_text(encoding="utf-8", errors="replace").lower()
        if "http://prometheus" in txt or "https://prometheus" in txt or "prometheus:9090" in txt:
            bad.append(f.relative_to(REPO_ROOT).as_posix())

    assert not bad, "Grafana datasources reference Prometheus runtime:\n" + "\n".join(bad)


@cache
def _services() -> dict:
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    return data["services"]


def _privileged_services() -> set[str]:
    return {name for name, service in _services().items() if service.get("privileged") is True}


def test_privileged_services_are_allowlisted() -> None:
    unlisted = sorted(_privileged_services() - PRIVILEGED_ALLOWLIST.keys())
    assert not unlisted, (
        f"❌ Privileged services without an ADR-backed exception (F46): {unlisted}\n"
        "Fix: drop `privileged: true`, or write an ADR for the exception and add the service to "
        "PRIVILEGED_ALLOWLIST."
    )


def test_allowlist_has_no_stale_entries() -> None:
    # Guards the guard: an entry for a service that is no longer privileged would keep an
    # exception alive that nothing needs.
    stale = sorted(PRIVILEGED_ALLOWLIST.keys() - _privileged_services())
    assert not stale, (
        f"❌ PRIVILEGED_ALLOWLIST names services that are not privileged: {stale}\n"
        "Fix: remove the entry, and mark its ADR as superseded if the exception is gone."
    )


def test_allowlist_entries_cite_existing_adr() -> None:
    problems = []
    for service, adr in PRIVILEGED_ALLOWLIST.items():
        path = REPO_ROOT / adr
        if not path.is_file():
            problems.append(f"{service}: {adr} does not exist")
        elif service not in path.read_text(encoding="utf-8").lower():
            problems.append(f"{service}: {adr} does not name the service")
    assert not problems, (
        "❌ Privileged exceptions without a valid ADR (F46):\n"
        + "\n".join(f" - {p}" for p in problems)
        + "\nFix: write the ADR (four-digit form, .claude/rules/docs-adr.md) and name the service."
    )


@pytest.mark.xfail(strict=True, reason="F46 step 4: contract pinned before privileged is dropped")
def test_cadvisor_is_not_privileged() -> None:
    privileged = _services()["cadvisor"].get("privileged")
    assert privileged is not True, (
        f"❌ cadvisor sets privileged={privileged!r} (F46 step 4).\n"
        f"Fix: drop `privileged: true`; {CADVISOR_ADR} records that it is not needed. If metrics "
        "are missing without it, add the smallest `cap_add` set instead."
    )


@pytest.mark.xfail(strict=True, reason="F46 step 4: contract pinned before the doc is corrected")
def test_monitoring_doc_matches_cadvisor_privileges() -> None:
    text = MONITORING_DOC.read_text(encoding="utf-8")
    claims = [
        phrase
        for phrase in ("only cadvisor runs privileged", "one privileged container")
        if phrase in text.lower()
    ]
    assert not claims, (
        f"❌ docs/monitoring.md still calls cadvisor privileged (F46): {claims}\n"
        "Fix: describe cadvisor's actual privileges and link its ADR."
    )

    section = re.search(r"^### cAdvisor$(.*?)(?=^##)", text, flags=re.MULTILINE | re.DOTALL)
    assert section, "❌ docs/monitoring.md has no '### cAdvisor' section.\nFix: restore it."
    assert "privileged: true" not in section.group(1), (
        "❌ The cAdvisor section of docs/monitoring.md lists `privileged: true` (F46).\n"
        "Fix: remove it; the compose file no longer sets it."
    )
    adr_name = Path(CADVISOR_ADR).name
    assert adr_name in section.group(1), (
        f"❌ The cAdvisor section of docs/monitoring.md does not link {adr_name} (F46).\n"
        "Fix: link the ADR that records cadvisor's privileges."
    )
