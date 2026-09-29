# tests/guards/test_53_socket_proxy_contract.py
#
# Finding F30 (R1.10): vector reads the Docker API only through `socket-proxy`
# (wollomatic/socket-proxy), which allows GET on the endpoints vector's docker_logs source uses
# and nothing else. The proxy is the only service with the Docker socket and the Docker group,
# sits only on the internal `docker-api` network (R1.9) and publishes no port.
#
# Endpoints, read from the vector v0.53.0 source (src/sources/docker_logs/mod.rs, 2026-09-29):
# events, list_containers, inspect_container, logs. bollard prefixes paths with /v1.<n>.
#
# F57 (R1.11): cadvisor v0.60.5 (container/docker/{factory,client,docker}.go, read 2026-09-29)
# calls Info (/info), ServerVersion (/version), Ping and ContainerInspect (/containers/<id>/json)
# through github.com/moby/moby/client. Ping sends HEAD /_ping (unversioned) first and falls back
# to GET only on a non-200 answer, so HEAD is allowed on exactly /_ping and nowhere else.
# ImageList (/images/json) serves only cadvisor's web UI status page and stays refused.

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
VECTOR_CONFIG = REPO_ROOT / "stacks/monitoring/vector/vector.yaml"

PROXY = "socket-proxy"
PROXY_URL = "http://socket-proxy:2375"
# Exact x.y.z tag, never the floating `1` tag the image also publishes.
PROXY_IMAGE = re.compile(r"^wollomatic/socket-proxy:\d+\.\d+\.\d+$")
# Flags that open a method other than GET and HEAD. Both are read-only.
OTHER_METHODS = ("POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE", "OPTIONS")
# GET paths the allowlist must accept (vector) and must refuse (file access, write-ish reads).
MUST_ALLOW = (
    "/v1.47/events",
    "/v1.47/containers/json",
    "/v1.47/containers/0123abcd/json",
    "/v1.47/containers/0123abcd/logs",
    "/containers/json",
)
# GET paths cadvisor needs in addition (R1.11, F57).
CADVISOR_GET = ("/_ping", "/version", "/v1.47/version", "/info", "/v1.47/info")
CADVISOR = "cadvisor"
CADVISOR_DOCKER_FLAG = "--docker=tcp://socket-proxy:2375"
R1_11 = pytest.mark.xfail(strict=True, reason="R1.11: cadvisor not on socket-proxy yet (F57)")
MUST_REFUSE = (
    "/v1.47/containers/0123abcd/archive",
    "/v1.47/containers/0123abcd/export",
    "/v1.47/containers/0123abcd/attach/ws",
    "/v1.47/images/json",
    "/v1.47/secrets",
    "/v1.47/containers/0123abcd/logs/../archive",
    "/v1.47/containers/../json",
)


@cache
def _raw_services() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]


def _proxy() -> dict:
    services = _raw_services()
    assert PROXY in services, f"❌ No `{PROXY}` service in compose (F30).\nFix: add it."
    return services[PROXY]


def _flags() -> dict[str, str]:
    flags = {}
    for arg in _proxy().get("command", []):
        name, _, value = str(arg).lstrip("-").partition("=")
        flags[name] = value
    return flags


def test_proxy_image_is_pinned_exactly() -> None:
    image = _proxy().get("image", "")
    assert PROXY_IMAGE.match(image), (
        f"❌ socket-proxy image {image!r} is not pinned to an exact x.y.z tag.\n"
        "Fix: pin wollomatic/socket-proxy:<x.y.z> (compose-stacks.md, IN10)."
    )


def test_proxy_is_hardened_and_unexposed() -> None:
    proxy = _proxy()
    problems = []
    if proxy.get("ports"):
        problems.append(f"publishes ports {proxy['ports']}")
    if proxy.get("read_only") is not True:
        problems.append("read_only is not true")
    if proxy.get("cap_drop") != ["ALL"]:
        problems.append(f"cap_drop is {proxy.get('cap_drop')!r}, not [ALL]")
    if not any("no-new-privileges" in str(o) for o in proxy.get("security_opt", [])):
        problems.append("no no-new-privileges")
    if str(proxy.get("user", "")).split(":")[0] != "65534":
        problems.append(f"user is {proxy.get('user')!r}, not 65534")
    if proxy.get("privileged"):
        problems.append("privileged")
    if "healthcheck" not in proxy:
        problems.append("no healthcheck")
    assert not problems, (
        "❌ socket-proxy breaks the hardening contract (F30):\n"
        + "\n".join(f" - {p}" for p in problems)
        + "\nFix: restore the settings; the proxy holds the Docker socket."
    )


def test_proxy_mounts_only_the_socket_read_only() -> None:
    volumes = [str(v) for v in _proxy().get("volumes", [])]
    assert volumes == ["/var/run/docker.sock:/var/run/docker.sock:ro"], (
        f"❌ socket-proxy mounts {volumes}.\n"
        "Fix: mount only /var/run/docker.sock:/var/run/docker.sock:ro."
    )


def test_proxy_allows_get_only() -> None:
    flags = _flags()
    opened = [f"allow{m}" for m in OTHER_METHODS if f"allow{m}" in flags]
    assert not opened, (
        f"❌ socket-proxy opens methods other than GET and HEAD: {opened} (F30).\n"
        "Fix: remove them; a new method needs an ADR-0012 amendment."
    )
    assert flags.get("allowGET"), "❌ socket-proxy has no -allowGET allowlist.\nFix: add it."


@R1_11
def test_proxy_allows_head_on_ping_only() -> None:
    # moby's client pings with HEAD /_ping first (cadvisor, F57); nothing else needs HEAD.
    head = _flags().get("allowHEAD")
    assert head is not None, "❌ socket-proxy has no -allowHEAD.\nFix: -allowHEAD=/_ping."
    pattern = re.compile(f"^(?:{head})$")
    probes = ("/_ping", "/v1.47/_ping", "/v1.47/containers/json", "/containers/x/archive", "/info")
    matched = [p for p in probes if pattern.match(p)]
    assert matched == ["/_ping"], (
        f"❌ -allowHEAD={head!r} matches {matched}, expected exactly ['/_ping'] (F57).\n"
        "Fix: -allowHEAD=/_ping."
    )


@R1_11
def test_proxy_get_allowlist_covers_cadvisor() -> None:
    pattern = re.compile(f"^(?:{_flags()['allowGET']})$")
    refused = [p for p in CADVISOR_GET if not pattern.match(p)]
    assert not refused, (
        f"❌ -allowGET refuses paths cadvisor needs: {refused} (F57).\n"
        "Fix: add _ping, version and info (with or without the /v1.<n> prefix)."
    )


@R1_11
def test_cadvisor_uses_the_proxy() -> None:
    cadvisor = _raw_services()[CADVISOR]
    command = [str(a) for a in cadvisor.get("command", [])]
    problems = []
    if CADVISOR_DOCKER_FLAG not in command:
        problems.append(f"command lacks {CADVISOR_DOCKER_FLAG}")
    if CADVISOR not in _flags().get("allowfrom", "").split(","):
        problems.append("socket-proxy -allowfrom does not name cadvisor")
    if "docker-api" not in (cadvisor.get("networks") or []):
        problems.append("cadvisor is not on docker-api")
    assert not problems, (
        "❌ cadvisor does not read the Docker API through socket-proxy (F57):\n"
        + "\n".join(f" - {p}" for p in problems)
        + "\nFix: set the flag, name cadvisor in -allowfrom, attach it to docker-api."
    )


def test_proxy_get_allowlist_refuses_file_and_image_access() -> None:
    # The proxy anchors the pattern with ^...$ itself (README) and matches r.URL.Path.
    pattern = re.compile(f"^(?:{_flags()['allowGET']})$")
    refused = [p for p in MUST_ALLOW if not pattern.match(p)]
    allowed = [p for p in MUST_REFUSE if pattern.match(p)]
    assert not refused and not allowed, (
        f"❌ -allowGET is wrong (F30). Refuses needed paths: {refused}; "
        f"allows forbidden paths: {allowed}.\n"
        "Fix: allow only what the consumers use (vector: events, containers/json, "
        "containers/<id>/json, containers/<id>/logs; cadvisor: _ping, version, info)."
    )


def test_proxy_listens_for_named_clients_only() -> None:
    flags = _flags()
    assert flags.get("listenip") == "0.0.0.0", (
        f"❌ -listenip is {flags.get('listenip')!r}; the default 127.0.0.1 is unreachable for "
        "other containers.\nFix: -listenip=0.0.0.0 (reach is limited by the network and -allowfrom)."
    )
    allowfrom = set(flags.get("allowfrom", "").split(","))
    assert "vector" in allowfrom and allowfrom <= {"vector", "cadvisor", "127.0.0.1/32"}, (
        f"❌ -allowfrom is {sorted(allowfrom)}.\n"
        "Fix: name the consumers (vector; cadvisor from R1.11) plus 127.0.0.1/32 for the "
        "postdeploy probe from the proxy's own namespace."
    )


def test_docker_api_network_carries_proxy_traffic_only() -> None:
    services = _raw_services()
    members = {n for n, s in services.items() if "docker-api" in (s.get("networks") or [])}
    networks = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8")).get("networks") or {}
    network = networks.get("docker-api")
    assert network == {"external": True, "name": "docker-api"}, (
        f"❌ The docker-api network is declared as {network!r}.\n"
        "Fix: declare it external (bootstrapped by scripts/network/bootstrap-networks.sh, R1.9)."
    )
    assert list(_proxy().get("networks", [])) == ["docker-api"], (
        f"❌ socket-proxy joins {_proxy().get('networks')}.\nFix: attach it to docker-api only."
    )
    assert members <= {PROXY, "vector", "cadvisor"} and "vector" in members, (
        f"❌ docker-api members: {sorted(members)}.\n"
        "Fix: only socket-proxy and its consumers (vector; cadvisor from R1.11) join docker-api."
    )


def test_vector_uses_the_proxy() -> None:
    config = yaml.safe_load(VECTOR_CONFIG.read_text(encoding="utf-8"))
    host = config["sources"]["docker"].get("docker_host")
    assert host == PROXY_URL, (
        f"❌ vector's docker_logs source uses docker_host={host!r} (F30).\n"
        f"Fix: set docker_host: {PROXY_URL} in stacks/monitoring/vector/vector.yaml."
    )


def test_vector_has_no_docker_group() -> None:
    group_add = [str(g) for g in _raw_services()["vector"].get("group_add", [])]
    assert "${DOCKER_GID}" not in group_add, (
        "❌ vector still joins the Docker group via group_add (F30).\n"
        "Fix: remove ${DOCKER_GID}; vector reads the Docker API through socket-proxy."
    )
