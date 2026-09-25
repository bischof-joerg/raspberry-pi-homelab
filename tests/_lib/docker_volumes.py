from __future__ import annotations

import json
import re
from dataclasses import dataclass

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
ANONYMOUS_LABEL = "com.docker.volume.anonymous"
ANONYMOUS_NAME = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class VolumeOffender:
    name: str
    driver: str
    compose_project: str | None
    anonymous: bool


def _labels(raw: str) -> dict[str, str]:
    """`docker volume ls` renders labels as one "k=v,k2=v2" string."""
    pairs = (item.partition("=") for item in raw.split(",") if item)
    return {key: value for key, _, value in pairs}


def volume_offenders(output: str) -> list[VolumeOffender]:
    """
    Parse `docker volume ls --format '{{json .}}'` (one JSON object per line).
    On the Pi every volume is an offender (ADR-0008, F48), so all are returned in order.
    Only names and labels are read - never the mountpoint contents.
    """
    offenders: list[VolumeOffender] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Unparseable `docker volume ls --format '{{{{json .}}}}'` line: {line!r}"
            ) from e
        name = str(entry.get("Name", ""))
        labels = _labels(str(entry.get("Labels") or ""))
        offenders.append(
            VolumeOffender(
                name=name,
                driver=str(entry.get("Driver", "")),
                compose_project=labels.get(COMPOSE_PROJECT_LABEL) or None,
                anonymous=ANONYMOUS_LABEL in labels or bool(ANONYMOUS_NAME.fullmatch(name)),
            )
        )
    return offenders
