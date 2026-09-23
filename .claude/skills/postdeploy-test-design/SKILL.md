---
name: postdeploy-test-design
description: Design focused postdeploy pytest checks with actionable failure messages. Use when an increment adds runtime behaviour that needs proving on the Pi.
---

# Postdeploy test design

Postdeploy tests are the only place where the system's actual runtime behaviour is asserted. They
run on the Pi after `deploy.sh`, never in CI and never here (C5).

## What belongs here, and what does not

| Question | Layer |
|---|---|
| Is this file well-formed, does this contract hold in the repo? | `tests/precommit` |
| Must this invariant never regress? | `tests/guards` |
| Is the container running, healthy, reachable, returning real data? | `tests/postdeploy` |

If a check can pass on a laptop with no containers, it is not a postdeploy test.

## Design each check

1. **One behaviour per test**, named for the behaviour: `test_grafana_api_health_returns_ok`, not
   `test_grafana`.
2. **Assert meaning, not presence.** "Endpoint returns 200" is weak; "the datasource query returns
   at least one series" is what the hint means by *endpoints return meaningful data*.
3. **Actionable failure message** — expected, found, and the fix. Follow the existing style: a `❌`
   line, then a `Fix:` line naming the command or file.
4. **Reuse the helpers**: `tests/_lib/http.py`, `tests/_lib/compose.py`, `tests/_lib/paths.py`,
   `tests/_helpers.py`, `tests/conftest.py`. Do not write a fresh HTTP wrapper.
5. **Mark it `postdeploy`** — the marker is registered in `pyproject.toml`, and `addopts` carries
   `-m "not postdeploy"`, which is what keeps it out of CI.
6. **Name the file** `test_<NN>_<topic>.py`, continuing the numbering in `tests/postdeploy/`.

## Cover the failure modes that actually happen here

Drawn from the findings, these are the ones this system has produced:

- A config change that does **not** recreate the container, because the config hash misses the file
  or the service carries no hash label (F1/F29). Assert the running config, not the file on disk.
- UFW drift: postdeploy **detects** it, nothing reconciles it (F15). Keep detecting.
- Network attributes on a fresh host: subnet, gateway and bridge may never have been validated
  (F16, F43). Assert the actual values, not just that the network exists.
- A service with no healthcheck reports nothing useful (F7) — then assert behaviour directly.

## Boundaries

Write the test. Never run it: it needs the Pi, and reaching the Pi is denied (C5). Say clearly in
the report that the test is unproven until the operator deploys — an untested test is a hypothesis.
