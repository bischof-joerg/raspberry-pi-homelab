# Repository findings – raspberry-pi-homelab

- **Status:** handed over 2026-09-23 (Phase 6 of `.claude/ClaudeTransition.md`), input for roadmap
  stage **R1**.
- **Nature:** proposals. Nothing here has been fixed by Claude — C1 forbade it during the
  transition. Each entry is written so that it can become one increment (`increment-plan` skill).
- **Single source of truth.** This file holds the full entries; `ClaudeTransition.md` §3.6 keeps a
  one-line index only. Change a finding here, then keep the index in step.
- **Mechanical check (V6.2):** `python3 .claude/tools/check_findings.py` — every entry has
  Evidence, Impact, Proposed fix, Test and Acceptance; every cited repo path exists; a path marked
  *(absent)* really is absent; the IDs here, in the index below and in §3.6 are the same set.

## How to read an entry

| Field | Meaning |
|---|---|
| **Evidence** | Repository paths (`file:line`) and the verification state. **[V date]** = read in the file on that date. **[I]** = inference; the entry names the check that would settle it. |
| **Impact** | What goes wrong, and for whom. |
| **Proposed fix** | The smallest change that removes the defect. Ordering hints where one fix depends on another. |
| **Test** | Layer (`tests/precommit`, `tests/guards`, `tests/postdeploy`) and the file to extend or create — test-first per D1. |
| **Acceptance** | An observable pass/fail statement. If you cannot check it, the finding is not closed. |

Verification dates: F1–F24 were first recorded 2026-09-16 on a Windows copy of the repository
(decision E1) and partly re-verified later; the date given is the latest read. On 2026-09-23 only
the findings whose status could plausibly have changed were re-read (F5, F10, F14, F21, F22, F23).
Re-verifying **every** entry against `main` is the R1 exit criterion (`ClaudeTransition.md` §10.3);
line numbers drift, so re-read before fixing.

Caution carried over from the transition (§5.2 there): three times a Claude artefact cited a
document as saying something it does not say. A cited file existing is not the file agreeing. Read
the cited lines before acting on any entry.

## Index

Severity: **High** = credential exposure, host-root equivalence, or a safety mechanism that does
not work; **Med** = drift, fragility or a missing test for a real contract; **Low** = hygiene.
The R1 column is a suggested grouping into increments (see the end of this file).

| ID | Title | Area | Sev | Status | R1 |
|---|---|---|---|---|---|
| F1 | Config hash is driven by a single runtime file | Deploy | High | open | d |
| F2 | Hash list names a missing file and two unmounted ones | Deploy | Med | open | d |
| F3 | Images pinned by tag, not by digest | Supply chain | Med | open | g |
| F4 | Renovate manages compose images only | Supply chain | Med | open | g |
| F5 | `README.md` describes a stack that no longer exists | Docs | Low | open | i |
| F6 | ADR numbering and titles are inconsistent | Docs | Low | open | i |
| F7 | Missing restart policy / healthchecks | Hardening | Med | open | f |
| F8 | Renderer installs `gettext` from the network at every run | Supply chain | Med | open | a |
| F9 | Backup scripts have no tests although ADR-009 requires them | Backup | High | open | R2 |
| F10 | pytest version drift between pre-commit and `.venv` | Toolchain | Low | addressed | – |
| F11 | `.gitattributes` does not pin LF for all text types | Toolchain | Low | open | h |
| F12 | `.env.example` duplicates keys and holds host-derived values | Secrets | Low | open | i |
| F13 | Compose mounts a templates directory that does not exist | Deploy | Med | open | d |
| F14 | DevWorkflow committed before `make ci` | Docs | Low | addressed | – |
| F15 | UFW is not reconciled on deploy | Exposure | Med | open | c |
| F16 | Network bootstrap on deploy skips subnet/bridge validation | Host | Med | open | e |
| F17 | `daemon.json` applied before the network it references exists | Host | Med | open | e |
| F18 | Any `daemon.json` change restarts Docker during deploy | Host | Med | open | e |
| F19 | Host-specific literals in reconciliation scripts | Host | Low | open | e |
| F20 | `ensure-journald-read.sh` default user does not match its use | Host | Low | open | e |
| F21 | Toolchain drift between `.venv` and pre-commit | Toolchain | Med | partly | h |
| F22 | Three diverging sources of dev dependencies | Toolchain | Med | open | h |
| F23 | Tests marked `lint` are never run by any gate | Tests | Med | open | h |
| F24 | Renovate validator hook runs a floating image tag | Supply chain | Med | open | g |
| F25 | JSON test scans git-ignored files | Tests | Low | open | h |
| F26 | Alertmanager SMTP password written world-readable | Secrets | High | addressed | a |
| F26b | The same password persists in every backup archive | Secrets | High | partly | a |
| F27 | Container uid left to image defaults for 8 of 10 services | Hardening | Med | open | f |
| F28 | cadvisor mounts the Docker socket read-write | Privilege | High | open | b |
| F29 | Config-hash label missing on 5 of 10 services | Deploy | High | open | d |
| F30 | vector is effectively host root via the Docker socket | Privilege | High | open | b |
| F31 | Grafana admin credentials default to empty | Secrets | High | open | c |
| F32 | Grafana runs without `read_only` on a wrong justification | Hardening | Med | open | f |
| F33 | vector has no healthcheck | Hardening | Low | open | f |
| F34 | vector joins the `apps` network without a reason | Privilege | Med | open | b |
| F35 | Renderer swallows errors despite `set -euo pipefail` | Secrets | Med | addressed | a |
| F36 | Renderer builds YAML without escaping | Secrets | Med | open | a |
| F37 | `alpine:3.24` is a floating minor tag | Supply chain | Med | open | g |
| F38 | `depends_on` ignores existing healthchecks | Hardening | Low | open | f |
| F39 | German comment in the renderer script | Docs | Low | addressed | a |
| F40 | Volume naming rule contradicted the implementation | Docs | Low | addressed | – |
| F41 | No static guard for the compose hardening contract | Tests | Med | partly | f |
| F42 | LAN exposure of 3000/9428 is recorded in no document | Exposure | Med | partly | c |
| F43 | ADR-0001 promises subnet validation the deploy path skips | Docs | Med | open | e |
| F44 | Stale image tag in a Markdown example | Supply chain | Low | open | g |
| F45 | UFW very likely does not govern the published ports | Exposure | High | open | c |
| F46 | cadvisor's privileged mode is undocumented; docs say the opposite | Privilege | High | open | b |
| F47 | cadvisor doctor test never runs; its skip hides a compose error | Tests | Med | open | h |

## Secrets and credentials

### F26 – Alertmanager SMTP password written world-readable

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:94-117` — the renderer writes `/out/alertmanager.yml` containing `auth_password` (line 100) and runs `chmod 0644` (line 117); `docs/architecture/adr/ADR-0007-secrets-and-env-files.md` defines `root:root 600` for secrets. [V 2026-09-23]
- **Impact:** With `ALERT_EMAIL_ENABLED=1`, every local user on the Pi can read the SMTP password at `/srv/data/stacks/monitoring/alertmanager-config/alertmanager.yml`. It leaves the ADR-0007 regime.
- **Proposed fix:** `chmod 0640` plus a group Alertmanager can read (it runs as `nobody`); change together with the directory mode in F26b.
- **Test:** `tests/postdeploy/test_22_alertmanager_config_rendered.py` — assert mode `0640` and owner/group of the rendered file; `tests/guards` — assert the compose renderer script contains no `chmod 0644` for that file.
- **Acceptance:** On the Pi, `stat -c '%a %U:%G'` on the rendered file shows `640` and a non-world group; the postdeploy test fails if the mode is widened again.
- **Resolution (R1.1, 2026-09-25):** renderer writes `0640` via temp file + `chgrp 65534` + `mv`; alertmanager pinned to `user: "65534:65534"`. Guard `tests/guards/test_30_alertmanager_renderer_contract.py`, postdeploy `test_22`. **First deploy (`2fdfb10`) failed:** with `user: "0:65534"` and `cap_drop: [ALL]`, `apk add gettext` could not chown its files to `root:root` ("failed to preserve …: owner", `10 errors`, exit 10), so alertmanager stayed `Created`. Fix-forward: renderer `user: "0:0"` + `group_add: ["65534"]` (an owner may chgrp to a supplementary group without `CAP_CHOWN`; verified on the Pi with `docker run --user 0:0 --group-add 65534 --cap-drop ALL alpine:3.24` → `0:65534`), `umask 027` after `apk add`. Pi acceptance pending deploy.

### F26b – The same password persists in every backup archive

- **Evidence:** `scripts/backup/backup.sh:383-385` archives `${STACK_DATA_ROOT}/alertmanager-config`; `stacks/monitoring/compose/init-permissions.sh:111,112,146` reconciles the directory to `0:0` mode `0755`. [V 2026-09-23]
- **Impact:** Rotating the SMTP password is not complete until backup retention ages out; a restore re-materialises the file at `0644`; the directory is traversable by everyone. At rest the archive is GPG-encrypted, which is acceptable.
- **Proposed fix:** Directory to `0750` with the Alertmanager-readable group in `init-permissions.sh`; document "rotation completes after retention" in `docs/operations/BackupVerifyRestore.md`; ensure restore re-applies the F26 mode.
- **Test:** `tests/postdeploy` — directory mode `0750`; backup fixture test (R2, F9) — a restored tree yields `0640` on the rendered file.
- **Acceptance:** Directory mode is `750` after deploy; a restore dry-run in the fixture harness produces no world-readable credential file.
- **Resolution (R1.1, 2026-09-25) — partly:** `init-permissions.sh` reconciles the directory to `0:nogroup 750` and strips other-bits recursively (its `--check` detects restore leftovers); rotation note in `docs/operations/BackupVerifyRestore.md` §6.2; postdeploy `test_55`. **Open:** the restore fixture test, which belongs to R2/F9.

### F31 – Grafana admin credentials default to empty

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:246-247` uses `${GRAFANA_ADMIN_USER:-}` / `${GRAFANA_ADMIN_PASSWORD:-}`. [V 2026-09-23]; what Grafana does with empty values [I — check with `docker compose config` and Grafana's startup log with the variables unset, in WSL].
- **Impact:** A missing or incomplete host env file starts a LAN-exposed Grafana (port 3000) with whatever Grafana does for empty credentials, instead of failing the deploy.
- **Proposed fix:** Use `${VAR:?message}` so `docker compose config` fails fast; `deploy.sh` secrets validation should list both variables.
- **Test:** `tests/precommit/test_30_compose_config.py` — with a fixture env that omits both variables, `docker compose config` must fail and name them.
- **Acceptance:** `docker compose config` without the two variables exits non-zero with a message naming them; with them it passes.

### F35 – Renderer swallows errors despite `set -euo pipefail`

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:121,123` — `cp … 2>/dev/null || true` and `chmod -R … || true`. [V 2026-09-23]
- **Impact:** A failed copy or permission change leaves a stale or unreadable Alertmanager config while the renderer reports success; the error surfaces later and elsewhere.
- **Proposed fix:** Remove `|| true`; handle the one legitimate "source may not exist" case with an explicit `[ -e ]` test.
- **Test:** `tests/guards` — static check that the renderer command contains no `|| true`.
- **Acceptance:** The guard test fails on any reintroduced `|| true`; a forced failure in the renderer makes the one-shot container exit non-zero.
- **Resolution (R1.1, 2026-09-25):** `|| true` and `2>/dev/null` removed; `cp -a` (which cannot preserve the repo owner without `CAP_CHOWN`, the error that was being swallowed) replaced by `cp -R`. Guard in `tests/guards/test_30_alertmanager_renderer_contract.py`. The forced-failure half is not tested; it needs the renderer extracted to a script (F36).

### F36 – Renderer builds YAML without escaping

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:95-102` — `printf '… "%s"'` with SMTP values. [V 2026-09-23]
- **Impact:** A password containing `"` or `\` breaks the file or injects YAML keys into `alertmanager.yml`.
- **Proposed fix:** Render with `envsubst` into a template that quotes values, or escape `\` and `"` before `printf`; validate the result with `amtool check-config` in the renderer.
- **Test:** `tests/precommit` — run the renderer logic (extracted to a script) against fixture values containing `"`, `\` and `:`; parse the output with PyYAML.
- **Acceptance:** Fixture values round-trip unchanged through render and YAML parse.

### F8 – Renderer installs `gettext` from the network at every run

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` renderer service (`apk add gettext`), image `alpine:3.24` at line 44. [V 2026-09-16]
- **Impact:** Every deploy depends on the Alpine mirror being reachable; the installed package version is not pinned, so the renderer is non-deterministic (C6). It also couples the renderer's user/group to package installation: the R1.1 group change broke `apk add` on deploy (see F26), which no static test could catch.
- **Proposed fix:** Use an image that already contains `envsubst` (pinned by digest), or drop `envsubst` in favour of shell-only rendering.
- **Test:** `tests/guards` — no `apk add`/`apt-get install` inside any compose `command`/`entrypoint`.
- **Acceptance:** The renderer runs with networking disabled (`network_mode: none`) and still produces the file.

### F39 – German comment in the renderer script

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:113`. [V 2026-09-23]
- **Impact:** Violates decision E6 (English only); minor.
- **Proposed fix:** Translate while touching the renderer for F26/F35/F36.
- **Test:** None beyond review; optionally `tests/guards` flags umlauts in `stacks/**`.
- **Acceptance:** `grep -nP '[äöüÄÖÜß]'` over `stacks/` returns nothing. *(Corrected 2026-09-25: this grep was already green before the fix — the comment has no umlauts. The guard checks for German words in the renderer script instead.)*
- **Resolution (R1.1, 2026-09-25):** comment translated; `test_renderer_script_is_english_only` in `tests/guards/test_30_alertmanager_renderer_contract.py`.

### F12 – `.env.example` duplicates keys and holds host-derived values

- **Evidence:** `stacks/monitoring/compose/.env.example` lists `DOCKER_GID` / `SYSTEMD_JOURNAL_GID` twice; `docs/architecture/adr/ADR-0007-secrets-and-env-files.md` §4 says host-derived values are computed by `deploy.sh`. [V 2026-09-16]
- **Impact:** Operators copy wrong or duplicate values into the host env file; the later key silently wins.
- **Proposed fix:** Remove the duplicates and the host-derived keys, with a comment pointing to `deploy.sh`.
- **Test:** `tests/precommit` — `.env.example` has unique keys and none of the host-derived names.
- **Acceptance:** The test passes and fails on a duplicated key.

## Privilege and the Docker socket

### F46 – cadvisor's privileged mode is undocumented; docs say the opposite

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:304-336` (`user: root`, `privileged: true`, `pid: host`, `/dev/kmsg`, `/:/rootfs:ro`, socket `:rw`); `docs/monitoring.md:29` "No privileged containers", `:197` "run with minimal privileges"; no ADR mentions cadvisor. [V 2026-09-23]
- **Impact:** The most privileged container in the stack rests on an inline comment. The one document that discusses it states the opposite, so a reader trusting the docs is misled. Claude's own artefacts repeated the claim until corrected (`ClaudeTransition.md` 5.2).
- **Proposed fix:** In order: (1) F28 — socket to `:ro`; (2) correct `docs/monitoring.md`; (3) write the ADR `docs-adr.md` requires for a privilege exception; (4) separately and testably, try dropping `privileged` using `--docker_only=true` (:329) and the cgroup mount (:317).
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — an explicit allowlist of privileged services that references the ADR; `tests/postdeploy/test_25_cadvisor_metrics.py` proves metrics still flow after each step.
- **Acceptance:** The guard test fails for any privileged service not on the allowlist; the allowlist entry cites an existing ADR; `docs/monitoring.md` no longer contradicts the compose file.

### F28 – cadvisor mounts the Docker socket read-write

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:319` (`/var/run/docker.sock` `:rw`) in the privileged container. [V 2026-09-23]; whether `:ro` suffices for cadvisor [I — deploy with `:ro` and run `tests/postdeploy/test_25_cadvisor_metrics.py`].
- **Impact:** A writable Docker API inside a privileged container is host root. Recorded history: this finding originally named vector's `:ro` socket as the safe contrast; that was wrong (F30) and was corrected 2026-09-23.
- **Proposed fix:** Change to `:ro` as its own increment; keep only if postdeploy stays green.
- **Test:** `tests/guards` — no `docker.sock` mount without `:ro`; `tests/postdeploy/test_25_cadvisor_metrics.py`.
- **Acceptance:** Compose shows `:ro`; cadvisor container metrics still present after deploy.

### F30 – vector is effectively host root via the Docker socket

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:377-379` (`group_add: ${DOCKER_GID}`), `:392` (socket `:ro`). [V 2026-09-23]; socket semantics [I — standard Docker behaviour: `:ro` protects the socket inode, not the API].
- **Impact:** Any compromise of vector (a log parser exposed to arbitrary log content) grants full Docker API access, i.e. host root.
- **Proposed fix:** Replace direct socket access with a filtering proxy that allows only the read endpoints vector needs (containers list, logs, events), or switch vector to journald-only collection for container logs.
- **Test:** `tests/guards` — vector has no `docker.sock` mount and no `group_add` with the Docker GID once fixed; `tests/postdeploy/test_40_vector_pipeline.py` proves container logs still arrive.
- **Acceptance:** vector cannot call a write endpoint (e.g. `POST /containers/create` via the proxy returns 403); log pipeline test green.

### F34 – vector joins the `apps` network without a reason

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:368`; `stacks/monitoring/vector/vector.yaml:12` filters to `com.docker.compose.project=homelab-home-prod-mon`. [V 2026-09-23]; purpose [I — ask the operator].
- **Impact:** Widens the reach of a container that already has socket access (F30) into the network future app stacks will use.
- **Proposed fix:** Remove `apps` from vector's networks, or record the reason in the compose file and an ADR.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — expected network set per service.
- **Acceptance:** vector is attached only to `monitoring` (or the reason is documented and the test encodes it).

## Exposure and firewall

### F45 – UFW very likely does not govern the published ports

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:243,347` publish `3000` and `9428` on all interfaces; `scripts/network/cleanup-ufw.sh:446,474` add INPUT-chain rules only; no `ufw route` / `DOCKER-USER` rule in `scripts/`, `docs/` or `stacks/`; `stacks/core/docker/daemon.json` does not set `"iptables": false`; `tests/postdeploy/test_35_network_and_ufw.py:210-244,327-342`. [V 2026-09-23]; effective reachability [I — from a host outside `LAN_CIDR`, `curl` both ports; operator only, C5].
- **Impact:** Docker's published-port traffic is DNAT'd through `FORWARD`, not `INPUT`, so the allowlist is very likely inert and both UIs are reachable from anything that can route to the Pi. The postdeploy test asserts rule **presence**; its one real negative test targets `9323`, a host port on the INPUT path, so it passes for a reason that does not generalise.
- **Proposed fix:** Bind both ports to the LAN address in compose, or add `ufw route` / `DOCKER-USER` rules — plus a negative postdeploy check.
- **Test:** `tests/postdeploy/test_35_network_and_ufw.py` — a negative reachability check from a non-`LAN_CIDR` source (or, if that is impractical on the Pi, assert the published bind address).
- **Acceptance:** A connection from outside `LAN_CIDR` to 3000/9428 is refused, measured by a test, not inferred from rule presence.

### F42 – LAN exposure of 3000/9428 is recorded in no document

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md` mentions neither port; a grep over `docs/` finds only timestamps and in-container examples. The exposure is intentional per `scripts/network/cleanup-ufw.sh`, `stacks/monitoring/compose/.env.example` and `tests/postdeploy/test_35_network_and_ufw.py`. [V 2026-09-23]
- **Impact:** A deliberate exposure without a record gets copied as precedent. The Claude rule that called it "documented" was corrected on 2026-09-23 (hence *partly*); the documentation gap remains.
- **Proposed fix:** Amend ADR-0001 (or a new ADR) with the two ports, their purpose and the intended source restriction — after F45 is decided, so the ADR records the working mechanism.
- **Test:** `tests/guards` — every published non-loopback port in compose appears in the network ADR.
- **Acceptance:** The guard test passes and fails when a new LAN port is published without an ADR entry.

### F15 – UFW is not reconciled on deploy

- **Evidence:** `deploy.sh` does not call `scripts/network/cleanup-ufw.sh`; `Makefile` has no target for it; `Todo.txt` notes the gap. [V 2026-09-16]
- **Impact:** UFW drift is detected by postdeploy (`tests/postdeploy/test_35_network_and_ufw.py`) but never corrected; a fresh host has no firewall policy from the repository.
- **Proposed fix:** R1 decision (ADR) on which host state `deploy.sh` reconciles; if UFW is in, call the script in `--apply` mode from `deploy.sh` behind a flag, idempotently. Depends on F45.
- **Test:** `tests/postdeploy/test_35_network_and_ufw.py` stays the detector; add a `tests/guards` check that `deploy.sh` invokes the reconciler when the ADR says so.
- **Acceptance:** After deploying onto a host with a manually deleted rule, postdeploy is green without manual action.

## Deploy path and config hash

### F1 – Config hash is driven by a single runtime file

- **Evidence:** `deploy.sh:177` `compute_monitoring_config_hash` lists four files; of these `stacks/monitoring/alertmanager/alertmanager.yml` (absent) is skipped, while `stacks/monitoring/vmalert/vmalert.yml` and `stacks/monitoring/victoriametrics/victoriametrics.yml` are mounted by no container. Only `stacks/monitoring/vmagent/vmagent.yml` counts. [V 2026-09-23]
- **Impact:** Changes to `vmalert/rules/*`, `stacks/monitoring/vector/vector.yaml`, the Alertmanager template or Grafana provisioning do not change the hash, so containers are not recreated and the deploy silently keeps old configuration. Together with F29 the mechanism is close to inert.
- **Proposed fix:** Derive the hash input from the compose file's bind-mounted config paths (one list, one source), or hash each service's mounted config into its own label.
- **Test:** `tests/guards` — every read-only config bind mount in compose is covered by the hash input; a missing file in the hash list fails the test.
- **Acceptance:** Changing any mounted config file changes the affected service's label value (checked in the guard test by computing the hash over a fixture change).

### F2 – Hash list names a missing file and two unmounted ones

- **Evidence:** `deploy.sh:177`; `stacks/monitoring/alertmanager/alertmanager.yml` (absent), only `stacks/monitoring/alertmanager/alertmanager.yml.tmpl` exists; `stacks/monitoring/vmalert/vmalert.yml`, `stacks/monitoring/victoriametrics/victoriametrics.yml` unmounted. [V 2026-09-23]
- **Impact:** The list looks complete and is not; the `[[ -f ]]` filter hides the missing file.
- **Proposed fix:** Fixed by F1's derived list; until then, fail on a missing listed file instead of skipping it.
- **Test:** Same guard test as F1.
- **Acceptance:** No listed hash input is absent or unmounted.

### F29 – Config-hash label missing on 5 of 10 services

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `homelab.config-hash` on five services; missing on `victoriametrics`, `node-exporter`, `cadvisor`, `victorialogs`, `vector`. [V 2026-09-23]
- **Impact:** Even a correct hash cannot recreate these services; `vector.yaml` changes trigger nothing at all.
- **Proposed fix:** Add the label to every service that mounts configuration (together with F1).
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — every service with a config bind mount carries the label.
- **Acceptance:** The test enumerates the services and fails when one lacks the label.

### F13 – Compose mounts a templates directory that does not exist

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:67` mounts `../alertmanager/templates`; `stacks/monitoring/alertmanager/templates` (absent). [V 2026-09-23]; Pi-side effect [I — on the Pi, `stat` the path: Docker creates it root-owned and empty].
- **Impact:** A root-owned empty directory appears in the working tree on the Pi, which can later block `git pull --ff-only` if templates are added.
- **Proposed fix:** Add the directory with a `.gitkeep`, or remove the mount.
- **Test:** `tests/guards` — every relative bind-mount source in compose exists in the repository.
- **Acceptance:** The guard test passes and fails on a mount to a non-existent path.

### F43 – ADR-0001 promises subnet validation the deploy path skips

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md:37-41`; `scripts/network/bootstrap-networks.sh` validates only when `MONITORING_SUBNET` etc. are set; `deploy.sh` does not export them. [V 2026-09-23]
- **Impact:** The ADR states a guarantee ("guarded against subnet overlap") that the deploy path does not deliver. `.claude/rules/host-runtime.md` describes reality correctly; the ADR is the defect.
- **Proposed fix:** Correct the ADR, or fix F16 so the promise becomes true — decide in the R1 host-reconciliation ADR.
- **Test:** Follows F16.
- **Acceptance:** ADR text and `deploy.sh` behaviour agree, checked by reading both after the change.

### F16 – Network bootstrap on deploy skips subnet/bridge validation

- **Evidence:** `deploy.sh` calls `scripts/network/bootstrap-networks.sh` without subnet/bridge variables; `scripts/network/cleanup-ufw.sh`, `stacks/core/docker/daemon.json` (`metrics-addr 172.20.0.1:9323`) and `tests/postdeploy/test_35_network_and_ufw.py` depend on `br-monitoring` / `172.20.0.0/16`. [V 2026-09-16]; fresh-host effect [I].
- **Impact:** On a fresh host `monitoring` would be created with a random subnet and bridge name, breaking the firewall rules and the Docker metrics address.
- **Proposed fix:** Export the network parameters from one versioned source in `deploy.sh`.
- **Test:** `tests/guards` — `deploy.sh` passes the subnet and bridge variables; `tests/postdeploy/test_35_network_and_ufw.py` already checks the attributes.
- **Acceptance:** Deploying onto a host without the `monitoring` network yields `br-monitoring` / `172.20.0.0/16`.

### F17 – `daemon.json` applied before the network it references exists

- **Evidence:** `deploy.sh` main order — `scripts/host/ensure-docker-daemon-json.sh` runs before `scripts/network/bootstrap-networks.sh`; `stacks/core/docker/daemon.json` binds `metrics-addr` to the monitoring gateway. [V 2026-09-16]; Docker behaviour on a missing address [I].
- **Impact:** On a fresh host Docker may fail to start or silently not expose metrics.
- **Proposed fix:** Bootstrap networks first, or make the metrics address independent of the bridge. Decide in the R1 ADR.
- **Test:** `tests/guards` — order assertion on `deploy.sh`; `tests/postdeploy/test_05_docker_daemon_json_and_metrics.py`.
- **Acceptance:** The order test encodes the chosen sequence; metrics test green after a fresh-host deploy.

### F18 – Any `daemon.json` change restarts Docker during deploy

- **Evidence:** `scripts/host/ensure-docker-daemon-json.sh` with `RESTART_DOCKER_ON_CHANGE=1` as called by `deploy.sh`. [V 2026-09-16]
- **Impact:** A one-line daemon change restarts every container during an ordinary deploy, without a maintenance window or a backup step.
- **Proposed fix:** Split into plan/apply like `scripts/host-runtime/`: deploy reports the pending change, an explicit operator target applies and restarts.
- **Test:** `tests/guards` — `deploy.sh` does not enable the restart flag by default.
- **Acceptance:** A deploy with a changed `daemon.json` does not restart Docker and prints the pending action.

### F19 – Host-specific literals in reconciliation scripts

- **Evidence:** `scripts/network/cleanup-ufw.sh` (usage path `/home/admin/iac/…`, bridge names `br-abe`, `br-bd2` in a regex); `scripts/network/bootstrap-networks.sh` (fixed temp file `/tmp/bootstrap-networks.overlap`). [V 2026-09-16]
- **Impact:** Stale literals mislead and may match or miss the wrong bridges; a fixed temp file races.
- **Proposed fix:** Remove the stale names, use `mktemp`, derive paths from the repo root.
- **Test:** `tests/guards` — no `/home/` literals and no fixed `/tmp/` paths in `scripts/`.
- **Acceptance:** Guard test passes; ShellCheck clean.

### F20 – `ensure-journald-read.sh` default user does not match its use

- **Evidence:** `scripts/host/ensure-journald-read.sh` defaults `TARGET_USER=vector`; `deploy.sh` passes `admin`; vector runs as uid 65532 with the GID via `group_add`. [V 2026-09-16]; relevance of `admin` membership [I].
- **Impact:** Confusing default; the step may be unnecessary for vector.
- **Proposed fix:** Decide whether the user membership is needed; remove the step or fix the default and document it.
- **Test:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py` proves journald ingestion either way.
- **Acceptance:** Journald logs arrive in VictoriaLogs with the step removed or corrected.

## Compose hardening

### F41 – No static guard for the compose hardening contract

- **Evidence:** `tests/guards/test_10_monitoring_compose_contract.py:12-22` — checks presence only. `vector` was missing from `REQUIRED_SERVICES` and was **added 2026-09-24** (Phase 8, V8.2); the hardening contract itself is still open. [V 2026-09-24]
- **Impact:** Every hardening property in this report can regress silently; F7, F27, F28, F29, F32, F33 and F38 all need this test as their home.
- **Proposed fix:** Extend the guard test into a per-service contract: pinned image, `read_only`, `cap_drop`, `no-new-privileges`, healthcheck, `user`, restart policy, allowed exceptions listed explicitly.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` itself.
- **Acceptance:** Removing any contract property from any service makes the test fail with the service and property named.

### F7 – Missing restart policy and healthchecks

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `victorialogs` has no `restart` and no healthcheck; `node-exporter` and `cadvisor` have no healthcheck. [V 2026-09-16]
- **Impact:** A crashed VictoriaLogs stays down; unhealthy exporters are not visible to `depends_on`.
- **Proposed fix:** Add `restart: unless-stopped` and healthchecks.
- **Test:** F41 contract test; `tests/postdeploy/test_10_containers.py` asserts `healthy`.
- **Acceptance:** All services report `healthy` after deploy.

### F33 – vector has no healthcheck

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:362-393`. [V 2026-09-23]
- **Impact:** A stuck log pipeline shows as running.
- **Proposed fix:** Enable vector's API health endpoint and check it.
- **Test:** F41 contract test; `tests/postdeploy/test_40_vector_pipeline.py`.
- **Acceptance:** `docker inspect` shows a health status for vector.

### F27 – Container uid left to image defaults for 8 of 10 services

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `user:` only on `node-exporter` (65534) and `vector` (65532). [V 2026-09-23]; actual uid per image [I — `docker image inspect -f '{{.Config.User}}'` per pinned image].
- **Impact:** An image bump can silently change the runtime uid — exactly the drift pinning prevents elsewhere.
- **Proposed fix:** Pin `user:` explicitly per service, with the documented exceptions.
- **Test:** F41 contract test.
- **Acceptance:** Every service has `user:` or an explicit exception entry.

### F32 – Grafana runs without `read_only` on a wrong justification

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:271-276` — the comment claims `read_only` would break the data volume; it covers the root filesystem only. [V 2026-09-23]; feasibility with a tmpfs `/tmp` [I].
- **Impact:** A writable root filesystem in the only LAN-exposed UI.
- **Proposed fix:** `read_only: true` plus `tmpfs: /tmp`; fix the comment.
- **Test:** F41 contract test; `tests/postdeploy/test_20_health_endpoints.py`.
- **Acceptance:** Grafana healthy with `read_only: true`.

### F38 – `depends_on` ignores existing healthchecks

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:175-177,206-210,372-374` use `service_started`. [V 2026-09-23]
- **Impact:** Dependants start before their upstream is ready; startup is order-dependent.
- **Proposed fix:** `condition: service_healthy` where the upstream has a healthcheck.
- **Test:** F41 contract test.
- **Acceptance:** No `service_started` against a service that has a healthcheck.

## Supply chain and pinning

### F3 – Images pinned by tag, not by digest

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml`, all ten images. [V 2026-09-23 via `image-pin-audit`]
- **Impact:** A re-pushed tag changes what deploys without a repository change.
- **Proposed fix:** `image: name:tag@sha256:…`, with Renovate `pinDigests` so updates stay controlled.
- **Test:** `tests/guards` — every compose image reference carries a digest.
- **Acceptance:** The test passes for all images and fails for a tag-only reference.

### F37 – `alpine:3.24` is a floating minor tag

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:44`. [V 2026-09-23]
- **Impact:** The weakest pin in the file; patch level floats.
- **Proposed fix:** Full version plus digest (with F3), or remove the image via F8.
- **Test:** F3 guard test.
- **Acceptance:** No compose image tag matches `^\d+\.\d+$`.

### F4 – Renovate manages compose images only

- **Evidence:** `renovate.json5` `enabledManagers: ["docker-compose"]`; `.github/workflows/ci.yml` uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4`; `.pre-commit-config.yaml` hook revs; pip ranges; the Grafana plugin pin. [V 2026-09-23]
- **Impact:** Everything outside compose drifts without a proposal; Actions tags are mutable.
- **Proposed fix:** Enable `github-actions`, `pre-commit`, `pip_requirements` managers; pin Actions by SHA; a regex manager for the Grafana plugin.
- **Test:** `tests/precommit` — every manager in a required list is enabled; `scripts/renovate/validate-config.sh` validates syntax.
- **Acceptance:** A Renovate dry run (`make renovate-check`, operator) lists proposals for each manager.

### F24 – Renovate validator hook runs a floating image tag

- **Evidence:** `scripts/renovate/validate-config.sh` runs `renovate/renovate:43`; `Makefile:85` pins the same image by digest; `.pre-commit-config.yaml` calls the script. [V 2026-09-23]
- **Impact:** Two versions of the validator; the hook needs Docker and a registry pull.
- **Proposed fix:** Share the digest pin from one place (e.g. a variable file read by both).
- **Test:** `tests/precommit` — both references resolve to the same digest.
- **Acceptance:** The test fails when one of the two drifts.

### F44 – Stale image tag in a Markdown example

- **Evidence:** `stacks/core/docker/docker-daemon-json-handling.md:93` shows `grafana/grafana:11.0.0`; deployed is `11.6.16` (`stacks/monitoring/compose/docker-compose.yml:239`); `renovate.json5` reads compose files only. [V 2026-09-23]
- **Impact:** Documentation examples drift permanently; readers copy old versions.
- **Proposed fix:** Replace with a placeholder (`grafana/grafana:<pinned>`) or reference the compose file.
- **Test:** `tests/guards` — no concrete `image:` tags in Markdown outside ADRs.
- **Acceptance:** The guard test passes.

## Toolchain and tests

### F9 – Backup scripts have no tests although ADR-009 requires them

- **Evidence:** `docs/architecture/adr/ADR-009-backup-verify-restore.md` DD-012 and §14.2; no backup test under `tests/`; the scripts in `scripts/backup/` already implement exit codes (`scripts/backup/common.sh:12-17`), locking and restore guards. [V 2026-09-23 via `backup-progress`]
- **Impact:** Five of seven ADR-009 requirements are implemented but unproven; the ADR's own acceptance rule is unmet.
- **Proposed fix:** R2 — fixture tests from ADR-009 §14.2 using the existing fixture overrides.
- **Test:** New `tests/backup/` (or `tests/guards`) fixture suite running in CI.
- **Acceptance:** Fixture tests for exit codes, lock contention and restore guards green in CI; `make backup`/`backup_verify` green on the Pi.

### F21 – Toolchain drift between `.venv` and pre-commit

- **Evidence:** `requirements-dev.txt` now pins `ruff==0.14.11`, `shellcheck-py==0.10.0.1`, `yamllint==1.35.1`, enforced by `tests/precommit/test_50_toolchain_version_parity.py` (R0.0, commit `3b109f6`); still open: `make venv` upgrades pip unpinned (`Makefile:233-234`), pytest is a range. [V 2026-09-23]. **Measured 2026-09-24:** one `make ci` run prints `[venv] upgrading pip` **seven times**, because every sub-`make` (`ci-doctor`, `ci-precommit`, `precommit`, `hooks`, `ci-tests`, `test`, …) depends on `venv`. Since Phase 8 Claude runs `make ci` too, so this now happens on every Claude gate run. [V]
- **Impact:** The linters now agree; pip and pytest can still differ between machines. Each gate run makes seven network round-trips to PyPI and may change the pip version mid-run.
- **Proposed fix:** Pin pip in `make venv` (`pip install pip==<version>`). Make `venv` idempotent: skip the install when a stamp file is newer than `requirements-dev.txt`. Decide whether pytest gets an exact pin in both places.
- **Test:** Extend `tests/precommit/test_50_toolchain_version_parity.py` to the pytest pin in the pre-commit hook.
- **Acceptance:** Parity test covers pytest; `make venv` produces the same pip version twice.

### F22 – Three diverging sources of dev dependencies

- **Evidence:** `pyproject.toml` `[project.optional-dependencies].dev` (`ruff>=0.14.11`, `pytest>=8`, `typeguard>=4`, `yamllint>=1.33`); `requirements-dev.txt` (exact pins); `.pre-commit-config.yaml` `pytest-precommit` `additional_dependencies`. [V 2026-09-23]
- **Impact:** `pip install .[dev]` yields a different toolchain than `make venv`; `typeguard` exists only in one list.
- **Proposed fix:** Make `requirements-dev.txt` the only source; drop the `dev` extra or generate it.
- **Test:** `tests/precommit/test_50_toolchain_version_parity.py` — the extra is absent or identical.
- **Acceptance:** One source of dev dependencies, enforced by the test.

### F23 – Tests marked `lint` are never run by any gate

- **Evidence:** `tests/precommit/test_15_json_valid.py:22`, `tests/precommit/test_20_yamllint.py:11`, `tests/precommit/test_25_no_merge_conflict_markers.py:31`, `tests/precommit/test_35_large_files.py:54` carry `@pytest.mark.lint`; `Makefile:286` selects `-m precommit`, `Makefile:292` ignores `tests/precommit`; nothing in `Makefile`, `pyproject.toml` or `.github/workflows/ci.yml` selects `lint`. Three files say the check moved to pre-commit hooks. [V 2026-09-23]
- **Impact:** Four test files are dead code that looks like coverage. (Sharpened 2026-09-23: originally recorded for `test_15` only.)
- **Proposed fix:** Delete the four files (pre-commit hooks `check-json`, `check-yaml`, `check-merge-conflict`, `check-added-large-files` cover them), or run `-m lint` in a gate.
- **Test:** `tests/precommit` — every marker registered in `pyproject.toml` is selected by at least one `Makefile` target.
- **Acceptance:** No test exists that no gate runs.

### F47 – The cadvisor doctor test never runs; its skip hides a compose error

- **Evidence:** `tests/doctor/test_35_cadvisor_flags.py:36-55` renders the compose file with a test env that sets neither `DOCKER_GID` nor `SYSTEMD_JOURNAL_GID`, and calls `pytest.skip` on **any** non-zero exit of `docker compose config`. `stacks/monitoring/compose/docker-compose.yml:377` `group_add` then receives two empty values. Measured in `make ci` on 2026-09-24: `SKIPPED [1] tests/doctor/test_35_cadvisor_flags.py:52: … services.vector.group_add items at 0 and 1 are equal`. [V 2026-09-24]
- **Impact:** The cadvisor flag checks have never run in CI or locally, but the result reads "1 skipped", which looks like a platform limitation. It is the same false-green class as F23: a test that exists but cannot fail.
- **Proposed fix:** Set both GIDs to distinct dummy values in the test env. Skip only when the compose plugin is missing; any other `config` failure must `pytest.fail` with stderr.
- **Test:** The test itself. A negative check: an env without the GIDs must make it **fail**, not skip.
- **Acceptance:** `make ci` shows `test_35_cadvisor_flags` as PASSED. Removing a GID from its env produces FAILED with the compose stderr.

### F25 – JSON test scans git-ignored files

- **Evidence:** `tests/precommit/test_15_json_valid.py:13-19` rglobs every `*.json`, including git-ignored files; it fails on the operator's JSONC editor settings. [V 2026-09-18, run result `1 failed, 3 passed`]
- **Impact:** Invisible today only because of F23; would fail as soon as the test is re-enabled.
- **Proposed fix:** Resolved by deleting the test (F23), or iterate `git ls-files '*.json'` instead of `rglob`.
- **Test:** The test itself on a fixture tree with an ignored invalid file.
- **Acceptance:** An ignored invalid JSON file does not fail the test; a tracked one does.

### F11 – `.gitattributes` does not pin LF for all text types

- **Evidence:** `.gitattributes` covers sh/yml/yaml/json/toml but not `*.md`, `*.py`, `Makefile`, `*.json5`. [V 2026-09-16]
- **Impact:** On the Windows side of the operator's machine a checkout can introduce CRLF (K9 in `ClaudeTransition.md`).
- **Proposed fix:** `* text=auto eol=lf` plus explicit binary types.
- **Test:** `tests/precommit` — no tracked text file contains `\r`.
- **Acceptance:** `git ls-files --eol` shows `lf` for all text files.

### F10 – pytest version drift between pre-commit and `.venv`

- **Evidence:** `.pre-commit-config.yaml` `pytest>=8.0,<9.0`; `requirements-dev.txt` `pytest>=8.0,<9.0`; `.venv` reports `pytest 8.4.2`. [V 2026-09-23]
- **Impact:** None any more — the pytest 9 bytecode seen on the Windows copy is not reproducible in the WSL `.venv`.
- **Proposed fix:** None; the exact-pin question is carried by F21.
- **Test:** Covered by F21's parity test extension.
- **Acceptance:** Closed when F21's parity test includes pytest.

## Documentation and ADRs

F46, F42 and F43 are documentation defects too; they are listed under privilege, exposure and
deploy because their fix starts in code and ends in the document.

### F5 – `README.md` describes a stack that no longer exists

- **Evidence:** `README.md:20,24` (Prometheus, Loki, Promtail), `README.md:56,71,85-86` (env file paths that differ from ADR-0007's `/etc/raspberry-pi-homelab/monitoring.env`). [V 2026-09-23]
- **Impact:** The entry point of the repository contradicts the implementation and the secrets model.
- **Proposed fix:** Rewrite from `.claude/CLAUDE.md` §3–§6 and `docs/monitoring.md`; link, do not duplicate.
- **Test:** `tests/guards/test_00_no_prometheus_artifacts.py` — extend to `README.md`; a link checker for relative links.
- **Acceptance:** No mention of Prometheus/Loki/Promtail; every relative link resolves.

### F6 – ADR numbering and titles are inconsistent

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md` (titled ADR-0004), `docs/architecture/adr/ADR-0008-bind-mounts-only.md` (titled ADR-000X), `docs/architecture/adr/ADR-009-backup-verify-restore.md` (three digits). [V 2026-09-16]
- **Impact:** References are ambiguous; `.claude/rules/docs-adr.md` expects `ADR-NNNN`.
- **Proposed fix:** Align titles with filenames; rename ADR-009 to ADR-0009 and update references.
- **Test:** `tests/guards` — ADR filename number equals the title number and has four digits.
- **Acceptance:** The guard test passes for all ADRs.

### F14 – DevWorkflow committed before `make ci`

- **Evidence:** `docs/operations/DevWorkflow.md:16,34,83-84` now require `make ci` before every commit (R0.0b, commit `6fa7493`). [V 2026-09-23]
- **Impact:** None any more.
- **Proposed fix:** None.
- **Test:** None needed; `.claude/rules/` and the `change-review` skill enforce the order in Claude's work.
- **Acceptance:** Closed — the document states validate-then-commit.

### F40 – Volume naming rule contradicted the implementation

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:17,19,146,260,360,387` use `/srv/data/stacks/monitoring/<service>`; `docs/architecture/adr/ADR-0008-bind-mounts-only.md` agrees; `.claude/CLAUDE.md` §4 and `.claude/rules/compose-stacks.md` were corrected 2026-09-23. [V 2026-09-23]
- **Impact:** None in the repository; the error was in `ChatGPTHint.txt` §4 and was copied into Claude's artefacts.
- **Proposed fix:** None. Do not migrate data to satisfy the old naming.
- **Test:** None.
- **Acceptance:** Closed — rule, `CLAUDE.md` and ADR-0008 agree.

## Suggested R1 increments

Security first, then the mechanisms other fixes depend on. One increment = one branch commit
series per `CLAUDE.md` §8; each needs its own tests before merge.

| Inc | Scope | Findings | Why this order |
|---|---|---|---|
| a | Alertmanager renderer: modes, errors, escaping, determinism | F26, F26b, F35, F36, F8, F39 | Live credential exposure; one service, one script |
| b | Docker socket and privilege | F28, F30, F34, F46 | Host-root equivalence; F28 is a one-line first step |
| c | LAN exposure and firewall contract | F45, F31, F42, F15 | F45 needs a Pi-side measurement first; decides F15 |
| d | Config hash that works | F1, F2, F29, F13 | Makes every later config change actually deploy |
| f | Compose contract guard test | F41, F7, F33, F27, F32, F38 | One test file becomes the home of all hardening checks |
| e | Host reconciliation ADR | F16, F17, F18, F43, F19, F20 | Needs an ADR decision before code (roadmap R1 exit) |
| g | Supply chain | F3, F37, F4, F24, F44 | Digest pins + Renovate coverage together |
| h | Toolchain and dead tests | F21, F22, F23, F25, F47, F11 | Low risk, quick |
| i | Docs | F5, F6, F12 | Last, so they describe the fixed state |
| R2 | Backup tests | F9 | Roadmap stage R2 |

Closed or nothing left to do: F10, F14, F40.
