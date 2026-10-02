from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from tests._lib.compose import render_compose
from tests._lib.compose_services import ONE_SHOT_SERVICES, long_running_services

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "stacks/monitoring/compose/.env.example"
MONITORING_DOC = REPO_ROOT / "docs/monitoring.md"
VECTOR_CONFIG = REPO_ROOT / "stacks/monitoring/vector/vector.yaml"

# Finding F46: `privileged: true` is an exception that needs an ADR (.claude/rules/docs-adr.md).
# Each entry maps a service to the ADR that records why it is privileged. Empty since F46 step 4
# dropped cadvisor's `privileged` (ADR-0011); a new entry needs its own ADR.
PRIVILEGED_ALLOWLIST: dict[str, str] = {}
# F46 step 4: the ADR that records cadvisor running without `privileged` (supersedes ADR-0010).
CADVISOR_ADR = "docs/architecture/adr/ADR-0011-cadvisor-unprivileged.md"
# F57: the capabilities cadvisor adds back after `cap_drop: [ALL]`. DAC_OVERRIDE is the only one
# it used with its own credentials in the cap_capable trace of 2026-10-01; every other granted
# check ran with overlayfs's mounter credentials (ADR-0011, amendment 2026-10-01).
CADVISOR_CAP_ADD = {"DAC_OVERRIDE"}

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
    "socket-proxy",
}

OPTIONAL_SERVICES = {}

# Finding F34: every service's networks are fixed here, so joining a network is a reviewed change.
# vector is on `apps` on purpose (operator, 2026-09-29): the apps stack (R6) is prepared, and
# vector is to process data from app services there. docker_logs does not use `apps`.
# The renderer has none at all (`network_mode: none`, F8). `docker-api` carries only the Docker
# socket proxy and its consumers (F30, ADR-0012, tests/guards/test_53).
EXPECTED_NETWORKS: dict[str, set[str]] = {
    "alertmanager": {"monitoring"},
    "alertmanager-config-render": set(),
    "victoriametrics": {"monitoring"},
    "vmagent": {"monitoring"},
    "vmalert": {"monitoring"},
    "grafana": {"monitoring"},
    "node-exporter": {"monitoring"},
    "cadvisor": {"monitoring"},
    "victorialogs": {"monitoring"},
    "vector": {"monitoring", "apps", "docker-api"},
    "socket-proxy": {"docker-api"},
}
NO_NETWORK_SERVICES = {"alertmanager-config-render"}

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


def test_every_service_has_an_expected_network_set() -> None:
    # Guards the guard: a service missing from EXPECTED_NETWORKS would never be checked.
    services = set(_services())
    assert services == EXPECTED_NETWORKS.keys(), (
        "❌ EXPECTED_NETWORKS does not match the compose services (F34).\n"
        f"Missing: {sorted(services - EXPECTED_NETWORKS.keys())}, "
        f"stale: {sorted(EXPECTED_NETWORKS.keys() - services)}\n"
        "Fix: add or remove the entry, with the reason for any network beyond `monitoring`."
    )


def test_services_join_only_their_expected_networks() -> None:
    wrong = {
        name: sorted(service.get("networks") or {})
        for name, service in _services().items()
        if name in EXPECTED_NETWORKS
        and set(service.get("networks") or {}) != EXPECTED_NETWORKS[name]
    }
    assert not wrong, (
        f"❌ Services with unexpected networks (F34): {wrong}\n"
        f"Expected: { {n: sorted(EXPECTED_NETWORKS[n]) for n in wrong} }\n"
        "Fix: revert the network change, or update EXPECTED_NETWORKS and record the reason."
    )


def test_no_network_services_have_network_mode_none() -> None:
    wrong = {
        name: _services()[name].get("network_mode")
        for name in NO_NETWORK_SERVICES
        if _services()[name].get("network_mode") != "none"
    }
    assert not wrong, (
        f"❌ Services meant to run without a network do not set `network_mode: none`: {wrong}\n"
        "Fix: restore `network_mode: none` (F8)."
    )


def test_long_running_services_restart_unless_stopped() -> None:
    # F7: measured on 2026-09-29 - after a reboot, victorialogs (no `restart`) stayed Exited while
    # every service with `unless-stopped` came back. A deploy never shows this: `up -d` starts all.
    wrong = {
        name: _services()[name].get("restart")
        for name in long_running_services(_services())
        if _services()[name].get("restart") != "unless-stopped"
    }
    assert not wrong, (
        f"❌ Long-running services without `restart: unless-stopped` (F7): {wrong}\n"
        "They stay down after a reboot until the next deploy.\n"
        "Fix: add `restart: unless-stopped`, or list a run-once service in ONE_SHOT_SERVICES "
        "(tests/_lib/compose_services.py)."
    )


def test_one_shot_services_exist_and_do_not_restart() -> None:
    # Guards the class list: a renamed one-shot service would otherwise count as long-running.
    wrong = {
        name: _services()[name].get("restart") if name in _services() else "<missing>"
        for name in sorted(ONE_SHOT_SERVICES)
        if name not in _services() or _services()[name].get("restart") != "no"
    }
    assert not wrong, (
        f'❌ ONE_SHOT_SERVICES entries missing from compose or not `restart: "no"` (F7): {wrong}\n'
        "Fix: update ONE_SHOT_SERVICES in tests/_lib/compose_services.py or the compose service."
    )


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


def test_cadvisor_is_not_privileged() -> None:
    privileged = _services()["cadvisor"].get("privileged")
    assert privileged is not True, (
        f"❌ cadvisor sets privileged={privileged!r} (F46 step 4).\n"
        f"Fix: drop `privileged: true`; {CADVISOR_ADR} records that it is not needed. If metrics "
        "are missing without it, add the smallest `cap_add` set instead."
    )


def test_every_service_drops_all_capabilities() -> None:
    # F41 (cap_drop part), F57: a service keeps Docker's default capability set unless it drops it.
    wrong = {
        name: service.get("cap_drop")
        for name, service in _services().items()
        if service.get("cap_drop") != ["ALL"]
    }
    assert not wrong, (
        f"❌ Services without `cap_drop: [ALL]` (F41, F57): {wrong}\n"
        "Fix: add `cap_drop: [ALL]` and add back only measured capabilities with `cap_add`."
    )


def test_cadvisor_cap_add_is_the_measured_set() -> None:
    cap_add = {
        name: sorted(service["cap_add"])
        for name, service in _services().items()
        if service.get("cap_add")
    }
    expected = {"cadvisor": sorted(CADVISOR_CAP_ADD)}
    assert cap_add == expected, (
        f"❌ cap_add differs from the measured set (F57): {cap_add}, expected {expected}\n"
        "Fix: add a capability only after measuring that the service needs it, and record it in "
        "the service's ADR and here."
    )
    adr_text = (REPO_ROOT / CADVISOR_ADR).read_text(encoding="utf-8")
    unnamed = sorted(cap for cap in CADVISOR_CAP_ADD if cap not in adr_text)
    assert not unnamed, (
        f"❌ {CADVISOR_ADR} does not name cadvisor's added capabilities {unnamed} (F57).\n"
        "Fix: record the measurement that justifies each one in the ADR."
    )


# Docker accepts the option bare or with `:true` / `=true`; `false` switches it off.
NO_NEW_PRIVILEGES = {"no-new-privileges", "no-new-privileges:true", "no-new-privileges=true"}
NEW_PRIVILEGES_ALLOWED = {"no-new-privileges:false", "no-new-privileges=false"}


def test_every_service_sets_no_new_privileges() -> None:
    # F41 (no-new-privileges part), F57; .claude/rules/compose-stacks.md requires it everywhere.
    def blocks_new_privileges(service: dict) -> bool:
        opts = {str(opt).strip() for opt in service.get("security_opt", [])}
        return bool(NO_NEW_PRIVILEGES & opts) and not NEW_PRIVILEGES_ALLOWED & opts

    wrong = {
        name: service.get("security_opt")
        for name, service in _services().items()
        if not blocks_new_privileges(service)
    }
    assert not wrong, (
        f"❌ Services without `no-new-privileges` (F41, F57): {wrong}\n"
        "Fix: add `security_opt: [no-new-privileges=true]` to each service."
    )


# F41 (read_only part): services still writing to their root filesystem, each with the open finding
# that tracks it. cadvisor left it in R1.21 (F57; `docker diff` showed only mount targets).
READ_ONLY_EXCEPTIONS = {"grafana": "F41"}
FINDINGS_REPORT = REPO_ROOT / ".claude/reports/repo-findings.md"


def _writable_services() -> set[str]:
    return {name for name, service in _services().items() if service.get("read_only") is not True}


def test_every_service_has_a_read_only_rootfs() -> None:
    wrong = {
        name: _services()[name].get("read_only")
        for name in sorted(_writable_services() - READ_ONLY_EXCEPTIONS.keys())
    }
    assert not wrong, (
        f"❌ Services without `read_only: true` (F41, F57): {wrong}\n"
        "Fix: measure the writes (`docker diff` minus the mount targets in `.Mounts`), set "
        "`read_only: true` and add a `tmpfs` only for a measured path."
    )


def test_read_only_exceptions_are_current() -> None:
    # Guards the guard: an exception for a service that is read-only now, or one whose finding
    # is no longer in the report, keeps a gap open that nothing tracks.
    stale = sorted(READ_ONLY_EXCEPTIONS.keys() - _writable_services())
    report = FINDINGS_REPORT.read_text(encoding="utf-8")
    untracked = sorted(
        f"{name}: {finding}"
        for name, finding in READ_ONLY_EXCEPTIONS.items()
        if f"### {finding} " not in report
    )
    assert not stale and not untracked, (
        f"❌ READ_ONLY_EXCEPTIONS is out of date (F41): read-only now {stale}, "
        f"finding not open in {FINDINGS_REPORT.name} {untracked}\n"
        "Fix: remove the entry, or name the open finding that tracks the service's writes."
    )


# F57: a host device is host access the compose file grants in one line. Each entry maps a service
# to the ADR that records why it needs its devices. Empty: cadvisor's /dev/kmsg fed only its OOM
# watcher (container_oom_events_total), which no rule or dashboard reads (operator, 2026-10-02).
DEVICES_ALLOWLIST: dict[str, str] = {}


def test_no_service_maps_host_devices() -> None:
    # Set equality: catches an unlisted service and a stale entry alike.
    mapped = {
        name: service["devices"] for name, service in _services().items() if service.get("devices")
    }
    assert mapped.keys() == DEVICES_ALLOWLIST.keys(), (
        f"❌ Host devices differ from DEVICES_ALLOWLIST (F57): {mapped}, "
        f"allowlisted {sorted(DEVICES_ALLOWLIST)}\n"
        "Fix: drop the `devices` entry, or record the measured need in an ADR and add the "
        "service to DEVICES_ALLOWLIST; remove an entry whose service maps no device."
    )


# F57: `pid: host` shows a service every host process. Each entry maps a service to the open
# finding that tracks it. cadvisor reads process data through the host's /proc under /rootfs
# (measured 2026-10-02, ADR-0011); node-exporter is tracked by F72.
PID_HOST_ALLOWLIST: dict[str, str] = {"node-exporter": "F72"}


@pytest.mark.xfail(strict=True, reason="R1.23: cadvisor still sets pid: host (F57)")
def test_no_service_shares_the_host_pid_namespace() -> None:
    # Set equality: catches an unlisted service and a stale entry alike.
    shared = sorted(name for name, service in _services().items() if service.get("pid") == "host")
    report = FINDINGS_REPORT.read_text(encoding="utf-8")
    untracked = sorted(
        f"{name}: {finding}"
        for name, finding in PID_HOST_ALLOWLIST.items()
        if f"### {finding} " not in report
    )
    assert shared == sorted(PID_HOST_ALLOWLIST) and not untracked, (
        f"❌ Services with `pid: host` differ from PID_HOST_ALLOWLIST (F57): {shared}, "
        f"allowlisted {sorted(PID_HOST_ALLOWLIST)}, finding not open {untracked}\n"
        "Fix: drop `pid: host`, or name the open finding or ADR that tracks it in "
        "PID_HOST_ALLOWLIST; remove an entry whose service no longer sets it."
    )


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


def test_vector_api_listens_on_loopback_only() -> None:
    # F58: vector joins monitoring, apps and docker-api; an API on 0.0.0.0 is reachable from every
    # container on them. The only caller, postdeploy test_20, queries from vector's own namespace.
    api = yaml.safe_load(VECTOR_CONFIG.read_text(encoding="utf-8")).get("api") or {}
    address = str(api.get("address", ""))
    host = address.rpartition(":")[0]
    assert not api.get("enabled") or host == "127.0.0.1", (
        f"❌ vector's API listens on {address!r} (F58).\n"
        "Fix: set api.address to 127.0.0.1:8686 in stacks/monitoring/vector/vector.yaml."
    )
