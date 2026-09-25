# tests/guards/test_40_volume_offenders.py
#
# Static proof for the postdeploy host check in tests/postdeploy/test_56 (finding F48,
# ADR-0008): on the Pi, every Docker volume is an offender. On the Pi itself the list is
# already empty, so the detection logic is exercised here with fixtures that mirror the
# volumes found on 2026-09-25: a compose-labelled legacy volume and an anonymous volume.

from __future__ import annotations

import json

import pytest

from tests._lib.docker_volumes import VolumeOffender, volume_offenders


def _offenders(output: str) -> list[VolumeOffender]:
    return volume_offenders(output)


def _line(name: str, labels: str = "", driver: str = "local") -> str:
    return json.dumps(
        {
            "Driver": driver,
            "Labels": labels,
            "Mountpoint": f"/var/lib/docker/volumes/{name}/_data",
            "Name": name,
            "Scope": "local",
        }
    )


LEGACY = _line(
    "compose_alertmanager-config",
    "com.docker.compose.project=compose,com.docker.compose.version=2.24.0,"
    "com.docker.compose.volume=alertmanager-config",
)
ANON_NAME = "de74cbca282a501d2c79b0cc923687ef87073ef12427a07e941ecb2532a2a1bf"


def test_no_volumes_means_no_offenders() -> None:
    assert _offenders("") == []
    assert _offenders("\n  \n") == []


def test_compose_labelled_volume_is_an_offender() -> None:
    [o] = _offenders(LEGACY + "\n")
    assert (o.name, o.driver, o.compose_project, o.anonymous) == (
        "compose_alertmanager-config",
        "local",
        "compose",
        False,
    )


def test_anonymous_volume_is_an_offender_by_name_or_label() -> None:
    by_name, by_label = _offenders(
        _line(ANON_NAME) + "\n" + _line("other", "com.docker.volume.anonymous=")
    )
    assert by_name.anonymous and by_name.compose_project is None
    assert by_label.anonymous


def test_every_volume_is_reported_in_order() -> None:
    names = [o.name for o in _offenders("\n".join([LEGACY, _line(ANON_NAME), _line("manual")]))]
    assert names == ["compose_alertmanager-config", ANON_NAME, "manual"]


def test_unparseable_line_fails_loudly() -> None:
    with pytest.raises(ValueError, match="docker volume ls"):
        _offenders("not json")
