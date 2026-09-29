# Repository findings – raspberry-pi-homelab

- **Status:** handed over 2026-09-23 (Phase 6 of the transition, now archived in
  `.claude/ClaudeTransition.md`); worked off in roadmap stage **R1** since 2026-09-25.
- **Nature:** each entry is written so that it can become one increment (`increment-plan` skill).
  Fixed entries keep their history in a **Resolution** line and carry status `addressed`.
- **Single source of truth.** This file holds the full entries and the index below. The grouping
  into R1 increments, with what is open and done per group, lives in `.claude/roadmap.md` §6.
- **Mechanical check (V6.2):** `python3 .claude/tools/check_findings.py` — every entry has
  Evidence, Impact, Proposed fix, Test and Acceptance; every cited repo path exists; a path marked
  *(absent)* really is absent; the IDs here and in the index are the same set; the roadmap groups
  agree with the index's status and R1 columns.

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
Re-verifying **every** entry against `main` is the R1 exit criterion (`.claude/roadmap.md` §4);
line numbers drift, so re-read before fixing.

Caution carried over from the transition (§5.2 there): three times a Claude artefact cited a
document as saying something it does not say. A cited file existing is not the file agreeing. Read
the cited lines before acting on any entry.

## Index

Severity: **High** = credential exposure, host-root equivalence, or a safety mechanism that does
not work; **Med** = drift, fragility or a missing test for a real contract; **Low** = hygiene.
The R1 column is the grouping into increments; per-group status and order in `.claude/roadmap.md` §6.

| ID | Title | Area | Sev | Status | R1 |
|---|---|---|---|---|---|
| F1 | Config hash is driven by a single runtime file | Deploy | High | open | d |
| F2 | Hash list names a missing file and two unmounted ones | Deploy | Med | open | d |
| F3 | Images pinned by tag, not by digest | Supply chain | Med | open | g |
| F4 | Renovate manages compose images only | Supply chain | Med | open | R2d |
| F5 | `README.md` describes a stack that no longer exists | Docs | Low | open | R2b |
| F6 | ADR numbering and titles are inconsistent | Docs | Low | open | R2b |
| F7 | Missing restart policy / healthchecks | Hardening | Med | open | f |
| F8 | Renderer installs `gettext` from the network at every run | Supply chain | Med | addressed | a |
| F9 | Backup scripts have no tests although ADR-009 requires them | Backup | High | open | R3 |
| F10 | pytest version drift between pre-commit and `.venv` | Toolchain | Low | addressed | – |
| F11 | `.gitattributes` does not pin LF for all text types | Toolchain | Low | open | h |
| F12 | `.env.example` duplicates keys and holds host-derived values | Secrets | Low | open | R2b |
| F13 | Compose mounts a templates directory that does not exist | Deploy | Med | open | d |
| F14 | DevWorkflow committed before `make ci` | Docs | Low | addressed | – |
| F15 | UFW is not reconciled on deploy | Exposure | Med | open | c |
| F16 | Network bootstrap on deploy skips subnet/bridge validation | Host | Med | open | e |
| F17 | `daemon.json` applied before the network it references exists | Host | Med | open | e |
| F18 | Any `daemon.json` change restarts Docker during deploy | Host | Med | open | e |
| F19 | Host-specific literals in reconciliation scripts | Host | Low | open | e |
| F20 | `ensure-journald-read.sh` default user does not match its use | Host | Low | open | e |
| F21 | Toolchain drift between `.venv` and pre-commit | Toolchain | Med | addressed | h |
| F22 | Three diverging sources of dev dependencies | Toolchain | Med | addressed | h |
| F23 | Tests marked `lint` are never run by any gate | Tests | Med | open | h |
| F24 | Renovate validator hook runs a floating image tag | Supply chain | Med | open | g |
| F25 | JSON test scans git-ignored files | Tests | Low | open | h |
| F26 | Alertmanager SMTP password written world-readable | Secrets | High | addressed | a |
| F26b | The same password persists in every backup archive | Secrets | High | partly | a |
| F27 | Container uid left to image defaults for 8 of 10 services | Hardening | Med | open | f |
| F28 | cadvisor mounts the Docker socket read-write | Privilege | High | addressed | b |
| F29 | Config-hash label missing on 5 of 10 services | Deploy | High | open | d |
| F30 | vector is effectively host root via the Docker socket | Privilege | High | addressed | b |
| F31 | Grafana admin credentials default to empty | Secrets | High | open | c |
| F32 | Grafana runs without `read_only` on a wrong justification | Hardening | Med | open | f |
| F33 | vector has no healthcheck | Hardening | Low | open | f |
| F34 | vector joins the `apps` network without a reason | Privilege | Med | addressed | b |
| F35 | Renderer swallows errors despite `set -euo pipefail` | Secrets | Med | addressed | a |
| F36 | Renderer builds YAML without escaping | Secrets | Med | addressed | a |
| F37 | `alpine:3.24` is a floating minor tag | Supply chain | Med | addressed | g |
| F38 | `depends_on` ignores existing healthchecks | Hardening | Low | open | f |
| F39 | German comment in the renderer script | Docs | Low | addressed | a |
| F40 | Volume naming rule contradicted the implementation | Docs | Low | addressed | – |
| F41 | No static guard for the compose hardening contract | Tests | Med | partly | f |
| F42 | LAN exposure of 3000/9428 is recorded in no document | Exposure | Med | partly | c |
| F43 | ADR-0001 promises subnet validation the deploy path skips | Docs | Med | open | e |
| F44 | Stale image tag in a Markdown example | Supply chain | Low | open | g |
| F45 | UFW very likely does not govern the published ports | Exposure | High | open | c |
| F46 | cadvisor's privileged mode is undocumented; docs say the opposite | Privilege | High | addressed | b |
| F47 | cadvisor doctor test never runs; its skip hides a compose error | Tests | Med | open | h |
| F48 | Orphaned named alertmanager-config volumes held an old SMTP password | Secrets | High | addressed | a |
| F49 | Postdeploy as root writes `__pycache__` into the Pi checkout | Tests | Low | addressed | h |
| F50 | The WSL layer (Python, Docker Desktop, apt) is neither documented nor checked | Toolchain | Med | open | R2d |
| F51 | Host upgrade apply does not execute the reviewed plan | Host | High | open | R3b |
| F52 | Mutating host-runtime scripts have no backup gate | Host | High | open | R3b |
| F53 | host-runtime scripts are untestable off the Pi and untested | Tests | Med | open | R3b |
| F54 | Docker packages upgrade uncontrolled inside the routine APT upgrade | Host | Med | open | R3b |
| F55 | Plan output, audit and runtime-updates doc disagree; audit gaps pass silently | Host | Low | open | R3b |
| F56 | Deploy log records postdeploy as `passed` without counts; the evidence is not kept | Tests | Med | open | h |
| F57 | cadvisor is host-root equivalent via the Docker socket, root and `pid: host` | Privilege | High | open | b |
| F58 | vector's API listens on all interfaces of two networks | Privilege | Low | open | b |
| F59 | `make ci` never runs the pre-commit hooks on new, untracked files | Toolchain | Low | open | h |

## Secrets and credentials

### F26 – Alertmanager SMTP password written world-readable

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:94-117` — the renderer writes `/out/alertmanager.yml` containing `auth_password` (line 100) and runs `chmod 0644` (line 117); `docs/architecture/adr/ADR-0007-secrets-and-env-files.md` defines `root:root 600` for secrets. [V 2026-09-23]
- **Impact:** With `ALERT_EMAIL_ENABLED=1`, every local user on the Pi can read the SMTP password at `/srv/data/stacks/monitoring/alertmanager-config/alertmanager.yml`. It leaves the ADR-0007 regime.
- **Proposed fix:** `chmod 0640` plus a group Alertmanager can read (it runs as `nobody`); change together with the directory mode in F26b.
- **Test:** `tests/postdeploy/test_22_alertmanager_config_rendered.py` — assert mode `0640` and owner/group of the rendered file; `tests/guards` — assert the compose renderer script contains no `chmod 0644` for that file.
- **Acceptance:** On the Pi, `stat -c '%a %U:%G'` on the rendered file shows `640` and a non-world group; the postdeploy test fails if the mode is widened again.
- **Resolution (R1.1, 2026-09-25):** renderer writes `0640` via temp file + `chgrp 65534` + `mv`; alertmanager pinned to `user: "65534:65534"`. Guard `tests/guards/test_30_alertmanager_renderer_contract.py`, postdeploy `test_22`. **First deploy (`2fdfb10`) failed:** with `user: "0:65534"` and `cap_drop: [ALL]`, `apk add gettext` could not chown its files to `root:root` ("failed to preserve …: owner", `10 errors`, exit 10), so alertmanager stayed `Created`. Fix-forward: renderer `user: "0:0"` + `group_add: ["65534"]` (an owner may chgrp to a supplementary group without `CAP_CHOWN`; verified on the Pi with `docker run --user 0:0 --group-add 65534 --cap-drop ALL alpine:3.24` → `0:65534`), `umask 027` after `apk add`. **Accepted 2026-09-25** after merge `2657096` (PR #15): on the Pi `stat` shows the directory `750 root:nogroup` and `alertmanager.yml` `640 root:nogroup`; postdeploy 58 passed, 4 skipped, including `test_22` and `test_55`.

### F26b – The same password persists in every backup archive

- **Evidence:** `scripts/backup/backup.sh:383-385` archives `${STACK_DATA_ROOT}/alertmanager-config`; `stacks/monitoring/compose/init-permissions.sh:111,112,146` reconciles the directory to `0:0` mode `0755`. [V 2026-09-23]
- **Impact:** Rotating the SMTP password is not complete until backup retention ages out; a restore re-materialises the file at `0644`; the directory is traversable by everyone. At rest the archive is GPG-encrypted, which is acceptable.
- **Proposed fix:** Directory to `0750` with the Alertmanager-readable group in `init-permissions.sh`; document "rotation completes after retention" in `docs/operations/BackupVerifyRestore.md`; ensure restore re-applies the F26 mode.
- **Test:** `tests/postdeploy` — directory mode `0750`; backup fixture test (R3, F9) — a restored tree yields `0640` on the rendered file.
- **Acceptance:** Directory mode is `750` after deploy; a restore dry-run in the fixture harness produces no world-readable credential file.
- **Resolution (R1.1, 2026-09-25) — partly:** `init-permissions.sh` reconciles the directory to `0:nogroup 750` and strips other-bits recursively (its `--check` detects restore leftovers); rotation note in `docs/operations/BackupVerifyRestore.md` §6.2; postdeploy `test_55`. **Open:** the restore fixture test, which belongs to R3/F9 (stage R2 before the re-plan of 2026-09-26).

### F48 – Orphaned named alertmanager-config volumes held an old SMTP password

- **Evidence:** measured by the operator on the Pi on 2026-09-25 (not in the repository): three dangling named volumes — `compose_alertmanager-config` (created 2026-01-03; its `/var/lib/docker/volumes/compose_alertmanager-config/_data/alertmanager.yml` 557 bytes, mode 600, `grep -c auth_password` = 1), `homelab-home-prod-mon_alertmanager-config` (created 2026-02-02; 356-byte file dated 2025-01-15, older than the volume — very likely the image's default config copied in [I]) and `monitoring_alertmanager-config` (0-byte file). No container referenced them. The repository declares no named volumes (`docs/architecture/adr/ADR-0008-bind-mounts-only.md`); `tests/postdeploy/test_56_monitoring_no_volume_mounts.py` inspects containers only, so dangling volumes are invisible to it. The anonymous volume from the R1.2 deploy (F8) was a fourth case. [V 2026-09-25]
- **Impact:** A credential persisted outside the ADR-0007 secrets regime and outside the ADR-009 backup inventory, invisible to every test. Access was root-only (`/var/lib/docker`); the operator judged rotation unnecessary because nobody else has access to the Pi.
- **Proposed fix:** Done 2026-09-25: all four volumes removed individually (`docker volume rm`, no `prune`); `docker volume ls` is empty. **Open:** prevent recurrence — extend `test_56` to fail on dangling volumes and on any volume carrying a `com.docker.compose.project` label. Optionally let `deploy.sh` run `up -d --renew-anon-volumes`, so compose never carries anonymous volumes over to a recreated container; that changes the deploy for every service and belongs to group d/e.
- **Test:** `tests/postdeploy/test_56_monitoring_no_volume_mounts.py` — add a check over `docker volume ls` (dangling, compose project label).
- **Acceptance:** `docker volume ls` on the Pi is empty (measured 2026-09-25), and the extended test fails as soon as a dangling or compose-labelled volume appears.
- **Resolution (2026-09-25):** stricter than proposed (operator decision, variant a): `test_host_has_no_docker_volumes` in `tests/postdeploy/test_56_monitoring_no_volume_mounts.py` fails on **any** Docker volume on the Pi and reports names and labels only; parsing in `tests/_lib/docker_volumes.py`, proven by `tests/guards/test_40_volume_offenders.py`; enforcement recorded in ADR-0008. `--renew-anon-volumes` remains an open option for group d/e. **Accepted 2026-09-25** after merge `acdd38b` (PR #20): postdeploy 60 passed, 4 skipped, including `test_host_has_no_docker_volumes`. The failing direction is proven statically by `test_40`, not on the Pi (no experiments on the deploy target).

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
- **Resolution (R1.1, 2026-09-25):** `|| true` and `2>/dev/null` removed; `cp -a` (which cannot preserve the repo owner without `CAP_CHOWN`, the error that was being swallowed) replaced by `cp -R`. Guard in `tests/guards/test_30_alertmanager_renderer_contract.py`. The forced-failure half is covered since R1.2: `test_control_characters_abort_without_leaking` in `tests/guards/test_31_alertmanager_renderer_render.py` asserts a non-zero exit and no output file.

### F36 – Renderer builds YAML without escaping

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:95-102` — `printf '… "%s"'` with SMTP values. [V 2026-09-23]
- **Impact:** A password containing `"` or `\` breaks the file or injects YAML keys into `alertmanager.yml`.
- **Proposed fix:** Render with `envsubst` into a template that quotes values, or escape `\` and `"` before `printf`; validate the result with `amtool check-config` in the renderer.
- **Test:** `tests/precommit` — run the renderer logic (extracted to a script) against fixture values containing `"`, `\` and `:`; parse the output with PyYAML.
- **Acceptance:** Fixture values round-trip unchanged through render and YAML parse.
- **Resolution (R1.2, 2026-09-25):** renderer extracted to `stacks/monitoring/alertmanager/render-config.sh` (POSIX sh). Values are emitted as double-quoted YAML scalars with `\` and `"` escaped character by character in awk; control characters (including newlines) abort with exit 2 and name the variable, never the value; `amtool check-config` validates the result in the image. Tests: `tests/guards/test_31_alertmanager_renderer_render.py` (host sh/awk round-trip), `tests/guards/test_32_alertmanager_renderer_container.py` (pinned image with the compose flags). **Accepted 2026-09-25** after merge `44f09b0` (PR #18): postdeploy 59 passed, 4 skipped; alertmanager healthy with configured receivers.

### F8 – Renderer installs `gettext` from the network at every run

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` renderer service (`apk add gettext`), image `alpine:3.24` at line 44. [V 2026-09-16]
- **Impact:** Every deploy depends on the Alpine mirror being reachable; the installed package version is not pinned, so the renderer is non-deterministic (C6). It also couples the renderer's user/group to package installation: the R1.1 group change broke `apk add` on deploy (see F26), which no static test could catch.
- **Proposed fix:** Use an image that already contains `envsubst` (pinned by digest), or drop `envsubst` in favour of shell-only rendering.
- **Test:** `tests/guards` — no `apk add`/`apt-get install` inside any compose `command`/`entrypoint`.
- **Acceptance:** The renderer runs with networking disabled (`network_mode: none`) and still produces the file.
- **Resolution (R1.2, 2026-09-25):** `envsubst` replaced by awk; the renderer now uses the pinned `prom/alertmanager:v0.34.0` image (BusyBox sh/awk plus amtool) with `network_mode: none` and `read_only: true`. Guard `test_no_service_installs_packages_at_runtime` covers every service; postdeploy `test_22` asserts exit code 0 and network mode `none`. **R1.2 deploy (`07b4448`): postdeploy failed** on `test_56` - the image declares `VOLUME /alertmanager`, which the renderer left uncovered, so Docker created an anonymous volume (ADR-0008); all other 58 checks passed. Fix-forward: `tmpfs: [/alertmanager]` on the renderer; `test_renderer_covers_every_image_volume` in `tests/guards/test_32_alertmanager_renderer_container.py` checks every image VOLUME against the compose mounts. The first redeploy still failed `test_56`: compose carries anonymous volumes over to a recreated container, so a one-time `docker compose rm -s -f -v alertmanager-config-render` was needed. **Accepted 2026-09-25** after merge `44f09b0` (PR #18): `test_22` (exit code 0, network mode `none`) and `test_56` green; `HostConfig.Tmpfs` is `{"/alertmanager":""}` and all mounts are bind mounts.

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
- **Progress (2026-09-25):** step (1) done via F28 (merge `f2a3172`); the socket is now `:ro`. The compose line numbers above predate R1.2 and have shifted (cadvisor now starts near line 251) — re-read before fixing. Next: steps (2) + (3) as one docs/ADR increment with the allowlist guard, then (4).
- **Progress (2026-09-28):** steps (2) + (3) done as R1.3, merge `ed8e008` (PR #27); ADR-0010 Accepted by the operator; deploy done without recreating cadvisor, postdeploy `tests: passed`. `docs/monitoring.md` no longer denies privileged containers; its cAdvisor section lists the privileges and all mounts and links `docs/architecture/adr/ADR-0010-cadvisor-privileged-exception.md` (drafted Proposed, Accepted before merge). The ADR records the Pi 5 necessity as unmeasured; the flag predates `3a50de5` (2026-02-02) with no recorded test. Guard: `PRIVILEGED_ALLOWLIST` in `tests/guards/test_10_monitoring_compose_contract.py` — `test_privileged_services_are_allowlisted`, `test_allowlist_has_no_stale_entries`, `test_allowlist_entries_cite_existing_adr`, `test_monitoring_doc_does_not_deny_privileged_containers` (the last two strict xfail in the tests commit `8802d3a`). No compose change. Status `partly`: step (4), dropping `privileged`, remains.
- **Progress (2026-09-29):** step (4) implemented on `fix/r1-cadvisor-unprivileged`. Baseline measured by the operator on the Pi on 2026-09-29 while privileged [V]: cadvisor exports `container_last_seen`, `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, `container_memory_rss`, `container_memory_cache`, `container_network_receive_bytes_total` and `container_network_transmit_bytes_total` with `name=` for alertmanager, grafana and victoriametrics (one series per service; 55 name prefixes in the `uniq -c` output, whose regex `[a-z_]+` truncates names with digits such as `container_cpu_load_average_10s`). Tests commit `5d760d6`: guards `test_cadvisor_is_not_privileged` and `test_monitoring_doc_matches_cadvisor_privileges` (strict xfail, failing for the intended reason with `--runxfail`); postdeploy `test_cadvisor_container_is_not_privileged` and the family check in `test_cadvisor_exports_named_container_metrics`. Fix: `privileged: true` removed, `PRIVILEGED_ALLOWLIST` empty, `docs/architecture/adr/ADR-0011-cadvisor-unprivileged.md` Proposed. Whether the network families survive without `CAP_SYS_PTRACE` is [I] until postdeploy on the Pi; if not, fix-forward with the smallest `cap_add` (ADR-0011 Decision 3). Status stays `partly` until deploy and postdeploy are green.
- **Resolution (2026-09-29):** merge `68a3118` (PR #31; commits `5d760d6` tests, `f113690` fix) deployed by the operator. Measured on the Pi [V 2026-09-29]: `HostConfig.Privileged` = `false` on the recreated cadvisor; the family listing matches the baseline line for line, network families included, so `CAP_SYS_PTRACE` was not needed and the `cap_add` fallback was not used. Postdeploy green; the operator reports 63 passed, 4 skipped. ADR-0011 Accepted and ADR-0010 Superseded by the operator the same day. What remains is outside F46's scope (an undocumented privilege) and is recorded as F57: cadvisor still reaches the Docker API through its socket (the class F30 describes, but F30 names only vector), runs as root with `pid: host`, and has no `cap_drop` or `read_only` (F7 covers only its missing healthcheck).

### F28 – cadvisor mounts the Docker socket read-write

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:319` (`/var/run/docker.sock` `:rw`) in the privileged container. [V 2026-09-23]; whether `:ro` suffices for cadvisor [I — deploy with `:ro` and run `tests/postdeploy/test_25_cadvisor_metrics.py`].
- **Impact:** A writable Docker API inside a privileged container is host root. Recorded history: this finding originally named vector's `:ro` socket as the safe contrast; that was wrong (F30) and was corrected 2026-09-23.
- **Proposed fix:** Change to `:ro` as its own increment; keep only if postdeploy stays green.
- **Test:** `tests/guards` — no `docker.sock` mount without `:ro`; `tests/postdeploy/test_25_cadvisor_metrics.py`.
- **Acceptance:** Compose shows `:ro`; cadvisor container metrics still present after deploy.
- **Resolution (2026-09-25):** socket mounted `:ro`; nothing else in cadvisor changed. Guard `tests/guards/test_50_docker_socket_mounts.py` (every runtime socket `:ro`, and the expected mounts exist); postdeploy `tests/postdeploy/test_25_cadvisor_metrics.py` checks `name=`-labelled container metrics live from cadvisor (not from VictoriaMetrics, whose lookback would hide a regression) and `RW=false` on the mount. **Security gain is near zero on its own:** cadvisor stays privileged, root and `pid: host`, and `:ro` never restricts the Docker API (F30). The real step is F46 (4). **Accepted 2026-09-25** after merge `f2a3172` (PR #24): cadvisor recreated, postdeploy 62 passed, 4 skipped on two consecutive deploys, including `test_cadvisor_exports_named_container_metrics` against the freshly started cadvisor and `test_cadvisor_docker_socket_is_read_only`.

### F30 – vector is effectively host root via the Docker socket

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:377-379` (`group_add: ${DOCKER_GID}`), `:392` (socket `:ro`). [V 2026-09-23]; socket semantics [I — standard Docker behaviour: `:ro` protects the socket inode, not the API].
- **Impact:** Any compromise of vector (a log parser exposed to arbitrary log content) grants full Docker API access, i.e. host root.
- **Proposed fix:** Replace direct socket access with a filtering proxy that allows only the read endpoints vector needs (containers list, logs, events), or switch vector to journald-only collection for container logs.
- **Test:** `tests/guards` — vector has no `docker.sock` mount and no `group_add` with the Docker GID once fixed; `tests/postdeploy/test_40_vector_pipeline.py` proves container logs still arrive.
- **Acceptance:** vector cannot call a write endpoint (e.g. `POST /containers/create` via the proxy returns 403); log pipeline test green.
- **Progress (2026-09-29):** implemented as R1.10 on `feat/r1-socket-proxy`, after the network `docker-api` (R1.9). Tests commit `099899a`: guards `tests/guards/test_53_socket_proxy_contract.py` and two in `tests/guards/test_50_docker_socket_mounts.py` (11 strict xfails, each failing for its own reason with `--runxfail`), postdeploy `tests/postdeploy/test_26_docker_socket_proxy.py`. Fix: service `socket-proxy` (`wollomatic/socket-proxy:1.13.1`, tag read from Docker Hub on 2026-09-29, arm64 present) is the only holder of the socket and the Docker group besides cadvisor (F57, R1.11); GET only on `events`, `containers/json`, `containers/<id>/json`, `containers/<id>/logs` — the four calls in vector v0.53.0 `src/sources/docker_logs/mod.rs` [V 2026-09-29]; vector without socket mount and `${DOCKER_GID}`, `docker_host: http://socket-proxy:2375`. The proxy answers a refused method with 405, not the 403 assumed above, and a refused path with 403 (`cmd/socket-proxy/handlehttprequest.go` [V 2026-09-29]). `docs/architecture/adr/ADR-0012-docker-api-socket-proxy.md` Proposed; it records that `containers/<id>/json` still exposes container environments, secrets included. Whether vector needs no further endpoint is [I] until postdeploy on the Pi (`test_proxy_blocked_no_consumer_request`, `test_40`). Status `partly` until deploy and postdeploy are green.
- **Progress (2026-09-29, deploy of merge `393b99d`, PR #37):** socket-proxy created and healthy, vector recreated; postdeploy `64 passed, 4 skipped, 7 deselected` [V 2026-09-29, operator]. The seven checks of `tests/postdeploy/test_26_docker_socket_proxy.py` did not run: the module lacked the `postdeploy` marker, and `deploy.sh` selects with `-m postdeploy`. What the deploy does prove: `tests/postdeploy/test_40_vector_pipeline.py` passed, so container logs reach VictoriaLogs through the proxy, and `docker logs … socket-proxy-1 | grep -c 'blocked request'` = `0` [V 2026-09-29, operator], so vector made no refused request — the four allowlisted endpoints suffice. Not yet proven: POST 405, `archive` 403, vector without socket mount and Docker group. Fix-forward (IN8) on `fix/r1-socket-proxy-postdeploy-marker`: guard `tests/guards/test_43_postdeploy_markers.py` (strict xfail in `73cbb07`), then the marker in test_26. ADR-0012 back to Proposed by the operator until then.
- **Resolution (2026-09-29):** fix-forward merge `72a00dc` (PR #38; commits `73cbb07` guard, `bda03b0` marker) deployed by the operator; no container recreated. Postdeploy `71 passed, 4 skipped`, nothing deselected, so all seven checks of `tests/postdeploy/test_26_docker_socket_proxy.py` ran green [V 2026-09-29, operator]. The proxy log holds exactly the two probes, both from the proxy's own namespace [V 2026-09-29, operator]: `reason="method not allowed" method=POST URL=/containers/create client=127.0.0.1:49918 response=405` and `reason="path not allowed" method=GET URL="/containers/homelab-home-prod-mon-socket-proxy-1/archive?path=/" client=127.0.0.1:49928 response=403`; no refused request from vector. vector runs without the socket mount and without the Docker group, and container logs still reach VictoriaLogs (`tests/postdeploy/test_40_vector_pipeline.py`). ADR-0012 Accepted by the operator. What remains is outside F30: `containers/<id>/json` still exposes container environments, secrets included (ADR-0012 "Negative / Tradeoffs"); cadvisor's own socket access is F57 (R1.11).

### F34 – vector joins the `apps` network without a reason

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:368`; `stacks/monitoring/vector/vector.yaml:12` filters to `com.docker.compose.project=homelab-home-prod-mon`. [V 2026-09-23]; purpose [I — ask the operator].
- **Impact:** Widens the reach of a container that already has socket access (F30) into the network future app stacks will use.
- **Proposed fix:** Remove `apps` from vector's networks, or record the reason in the compose file and an ADR.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — expected network set per service.
- **Acceptance:** vector is attached only to `monitoring` (or the reason is documented and the test encodes it).
- **Resolution (2026-09-29):** the reason exists and is now recorded — the operator decided on 2026-09-29 that vector stays on `apps`: the apps stack (R6) is prepared, and vector is to process data from app services there. No vector source uses the network yet; `docker_logs` reads through the Docker API, not over a network. Recorded in a comment at vector's `networks` in `stacks/monitoring/compose/docker-compose.yml` and in `docs/services/vector.md`; no ADR, since the R6 stack design will decide how app data reaches vector. Guard: `EXPECTED_NETWORKS` in `tests/guards/test_10_monitoring_compose_contract.py` pins the network set of every service (`test_every_service_has_an_expected_network_set`, `test_services_join_only_their_expected_networks`, `test_no_network_services_have_network_mode_none`). No runtime change. The reach this gives vector's API is recorded as F58; vector's socket access remains F30.

### F58 – vector's API listens on all interfaces of two networks

- **Evidence:** `stacks/monitoring/vector/vector.yaml:1-4` (`api.enabled: true`, `address: 0.0.0.0:8686`); vector joins `monitoring` and `apps` (`stacks/monitoring/compose/docker-compose.yml`, F34). Nothing outside the container uses the port: the only caller is `tests/postdeploy/test_20_health_endpoints.py:18`, which queries `127.0.0.1:8686` inside vector's network namespace. [V 2026-09-29]; reachability from another container [I — from a container on `apps`, `wget -qO- http://vector:8686/health`; operator only, C5].
- **Impact:** Every container on `monitoring`, and every future app container on `apps`, can query vector's API (health, topology, component metrics). Low today; it grows with R6, and it adds to the reach of a service that has Docker API access until F30 is fixed.
- **Proposed fix:** Bind the API to `127.0.0.1:8686`; `test_20` keeps working because it queries from inside the namespace.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — vector's API address in `stacks/monitoring/vector/vector.yaml` is loopback; `tests/postdeploy/test_20_health_endpoints.py` stays green.
- **Acceptance:** The guard passes; after deploy, `http://vector:8686/health` from another container on `monitoring` is refused, while `test_20` passes.

### F57 – cadvisor is host-root equivalent via the Docker socket, root and `pid: host`

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:251-287` — after F46 step (4) cadvisor is no longer privileged, but still runs `user: root` with `pid: host`, the device `/dev/kmsg`, host `/` as `/rootfs:ro`, and `/var/run/docker.sock` plus the containerd socket (both `:ro`); no `cap_drop`, no `read_only`, no `security_opt`. [V 2026-09-29]; ADR-0011 "Negative / Tradeoffs" records the same. F30 describes this socket class for vector only; F7 covers only cadvisor's missing healthcheck.
- **Impact:** A compromise of cadvisor, which parses host-controlled data and is reachable from every container on the `monitoring` network, still gives full Docker API access (`:ro` does not restrict the API), i.e. host root. Dropping `privileged` removed all-capabilities and all-devices, not this path.
- **Proposed fix:** Decide together with F30, since both need read-only Docker API access: a filtering socket proxy that allows only the read endpoints cadvisor and vector use, shared or per service. Then drop what cadvisor does not need, each step measured by `tests/postdeploy/test_25_cadvisor_metrics.py`: `cap_drop: [ALL]` plus only the capabilities that prove necessary, `no-new-privileges`, `read_only` with a `tmpfs`, and whether `pid: host` and `/dev/kmsg` are needed with `--docker_only=true`.
- **Test:** `tests/guards/test_50_docker_socket_mounts.py` — no service mounts the raw socket once the proxy exists; `tests/guards/test_10_monitoring_compose_contract.py` — cadvisor's expected `cap_add`/`cap_drop`/`security_opt` set; postdeploy `test_25` family check after each step.
- **Acceptance:** cadvisor cannot call a write endpoint of the Docker API; every family in `REQUIRED_FAMILIES` still flows; its remaining rights are listed in ADR-0011 or a successor.
- **Progress (2026-09-29, R1.11 attempted and reverted):** the socket part was tried as R1.11 — merge `768e3fb` (PR #40; `611e704` tests, `cdf15f8` fix): cadvisor with `--docker=tcp://socket-proxy:2375`, no Docker or containerd socket, proxy allowlist extended by GET `_ping`/`version`/`info` and HEAD `/_ping`. Postdeploy failed: `test_cadvisor_exports_named_container_metrics` found no `name=` series, and the live count `grep -c 'name="homelab-home-prod-mon-'` on cadvisor's `/metrics` was `0` [V 2026-09-29, operator]. Cause, measured on the Pi [V 2026-09-29, operator]: cadvisor logged `Registration of the docker container factory failed: unable to create containerd client: containerd: cannot unix dial containerd api service: dial unix /run/containerd/containerd.sock: connect: no such file or directory`; `docker info` reports `overlayfs 29.5.2 [[driver-type io.containerd.snapshotter.v1]]` — Docker uses the containerd image store. In cadvisor v0.60.5 (`container/docker/factory.go`, read 2026-09-29) the Docker factory creates a containerd client whenever the storage driver is the containerd snapshotter, and a failure aborts the whole registration; no flag turns it off. The proxy log held no `blocked request` at all, so the Docker API calls themselves were not the problem. The containerd API is gRPC and cannot be filtered by socket-proxy; the containerd socket alone grants host root (tasks in the `moby` namespace). Reverted per IN8: merge `4d498a1` (PR #41, revert commit `82fe60f`, tree identical to `5ce0854`); postdeploy `71 passed, 4 skipped`, the proxy log holds only the two `127.0.0.1` probes, cadvisor exports `634` `name=` series again [V 2026-09-29, operator]. **Consequence:** the socket part of F57 cannot be solved with socket-proxy while Docker uses the containerd image store. Open options, none decided: (a) switch the Docker daemon to the classic `overlay2` graph driver — a `daemon.json` change that restarts Docker (F18) and rebuilds every image and container, needs its own ADR and a proven backup (R3), and whether cadvisor then no longer needs containerd is [I]; (b) accept the socket risk explicitly in ADR-0011 or a successor; (c) drop cadvisor's Docker integration (`name=` labels, on which vmalert rules and dashboards depend) — not viable today. The other hardening steps (`cap_drop`, `no-new-privileges`, `read_only`, `pid: host`, `/dev/kmsg`) are independent of the sockets and remain open. Status stays `open`.

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
- **Progress (2026-09-29, R1.12):** the operator chose the per-service variant, started with vector because F58 changes `stacks/monitoring/vector/vector.yaml`, which no hash covered. `deploy.sh` gained `compute_file_hash` (content only, no paths; dies on a missing file) and exports `VECTOR_CONFIG_HASH`; vector carries `homelab.config-hash=${VECTOR_CONFIG_HASH:-unset}`. Tests commit `f2e01b2`: `tests/guards/test_54_vector_config_hash.py` (4 strict xfails, static), postdeploy `test_vector_label_matches_config_hash` in `tests/postdeploy/test_40_vector_pipeline.py`. The global `MONITORING_CONFIG_HASH` and the other services are unchanged; status stays `open`.

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
- **Progress (2026-09-29, R1.12):** vector now carries the label, with its own per-service value `VECTOR_CONFIG_HASH` (see F1). The generic "every config-mounting service carries a label" test is still missing; status stays `open`.

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
- **Resolution (R1.2, 2026-09-25):** removed via F8 - the renderer uses `prom/alertmanager:v0.34.0`; no compose image has a two-part tag any more. A guard for the acceptance belongs to F3 (group g). The postdeploy tests still start helper containers from `alpine:3.20`; that is test tooling, not a compose image, and stays with F3. Deployed with merge `44f09b0`; the Pi no longer pulls `alpine:3.24`.

### F4 – Renovate manages compose images only

- **Evidence:** `renovate.json5` `enabledManagers: ["docker-compose"]`; `.github/workflows/ci.yml` uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4`; `.pre-commit-config.yaml` hook revs; pip ranges; the Grafana plugin pin. [V 2026-09-23]
- **Impact:** Everything outside compose drifts without a proposal; Actions tags are mutable.
- **Proposed fix:** Enable `github-actions`, `pre-commit`, `pip_requirements` managers; pin Actions by SHA; a regex manager for the Grafana plugin.
- **Test:** `tests/precommit` — every manager in a required list is enabled; `scripts/renovate/validate-config.sh` validates syntax.
- **Acceptance:** A Renovate dry run (`make renovate-check`, operator) lists proposals for each manager.
- **Re-planned (2026-09-26):** moved from group g to stage R2d (dev-environment lifecycle, `.claude/roadmap.md` §9.2). The pins in `requirements-dev.txt` and `.pre-commit-config.yaml` must move in one PR, because `tests/precommit/test_50_toolchain_version_parity.py` requires them to match; Actions digest pinning may stay with F3.
- **Progress (2026-09-29):** a second unmanaged class found while planning R1.11: helper images hardcoded in the postdeploy tests — `curlimages/curl:8.11.1` (`tests/postdeploy/test_20_health_endpoints.py:26`, `tests/postdeploy/test_25_cadvisor_metrics.py:13`, `tests/postdeploy/test_26_docker_socket_proxy.py:28`), `alpine:3.20` (`tests/postdeploy/test_22_victorialogs_stats_query.py:125`, `tests/postdeploy/test_25_cadvisor_metrics.py:41`, `tests/postdeploy/test_31_vmagent_targets.py:21`, `tests/postdeploy/test_35_docker_engine_metrics.py:74`, `tests/postdeploy/test_35_network_and_ufw.py:139`), `busybox:1.36` (`tests/postdeploy/test_40_vector_pipeline.py:95`). Renovate cannot see them: `renovate.json5:14` enables only `docker-compose`, and `renovate.json5:30` limits it to the monitoring compose file [V 2026-09-29]. Proposed addition to the fix: one constants module for these images plus a `regex` manager for it (or a `customManagers` entry matching `*_IMAGE = "…"` under `tests/`); test: every image literal under `tests/` comes from that module.

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
- **Proposed fix:** R3 — fixture tests from ADR-009 §14.2 using the existing fixture overrides.
- **Test:** New `tests/backup/` (or `tests/guards`) fixture suite running in CI.
- **Acceptance:** Fixture tests for exit codes, lock contention and restore guards green in CI; `make backup`/`backup_verify` green on the Pi.

### F21 – Toolchain drift between `.venv` and pre-commit

- **Evidence:** `requirements-dev.txt` now pins `ruff==0.14.11`, `shellcheck-py==0.10.0.1`, `yamllint==1.35.1`, enforced by `tests/precommit/test_50_toolchain_version_parity.py` (R0.0, commit `3b109f6`); still open: `make venv` upgrades pip unpinned (`Makefile:233-234`), pytest is a range. [V 2026-09-23]. **Measured 2026-09-24:** one `make ci` run prints `[venv] upgrading pip` **seven times**, because every sub-`make` (`ci-doctor`, `ci-precommit`, `precommit`, `hooks`, `ci-tests`, `test`, …) depends on `venv`. Since Phase 8 Claude runs `make ci` too, so this now happens on every Claude gate run. [V]
- **Impact:** The linters now agree; pip and pytest can still differ between machines. Each gate run makes seven network round-trips to PyPI and may change the pip version mid-run.
- **Proposed fix:** Pin pip in `make venv` (`pip install pip==<version>`). Make `venv` idempotent: skip the install when a stamp file is newer than `requirements-dev.txt`. Decide whether pytest gets an exact pin in both places.
- **Test:** Extend `tests/precommit/test_50_toolchain_version_parity.py` to the pytest pin in the pre-commit hook.
- **Acceptance:** Parity test covers pytest; `make venv` produces the same pip version twice.
- **Progress (2026-09-28, R1.5 on `chore/r1-toolchain`):** every direct dev dependency pinned with `==` in `requirements-dev.txt` (the four former ranges at the versions measured in `.venv`: `pytest==8.4.2`, `requests==2.32.5`, `PyYAML==6.0.3`, `pre-commit==3.8.0`); the 16 transitive dependencies, resolved from the installed package metadata rather than copied from `pip freeze`, pinned in the new `constraints-dev.txt`, applied by `-c`. The `pytest-precommit` hook uses the same direct pins. CI's `.venv` cache key hashes both files and has no `restore-keys`, so an older venv never carries over. Tests: four new checks in `tests/precommit/test_50_toolchain_version_parity.py` and the new `tests/doctor/test_40_venv_matches_pins.py` (strict xfail in `f2fe8ea`). Measured before the fix: the local `.venv` held `typeguard`, `typing-extensions` and two editable installs of the repo (`raspberry-pi-homelab`, `unknown`) that no pin covers — drift that `pip install -r` never removes; the operator ran `make venv-clean venv` on 2026-09-28, after which `typeguard`, `typing-extensions` and `unknown` were gone. `raspberry-pi-homelab` still showed up: not in `.venv`, but as a git-ignored `raspberry_pi_homelab.egg-info` in the repo root (2026-02-02, from an old `pip install -e .`), visible because `tests/conftest.py` puts the repo root on `sys.path`. The doctor test now counts only distributions located inside `.venv`; the stray directory is harmless and left to the operator. **Open (R1.6):** pip is still upgraded unpinned, seven times per `make ci`; the doctor test excludes pip until then. Known gap: the hook environment cannot apply `constraints-dev.txt`, so its transitive dependencies float.
- **Resolution (2026-09-28, R1.6 on `chore/r1-toolchain`):** `make venv` delegates to the new `scripts/dev/ensure-venv.sh`: it installs `pip==26.2.1` (pinned in `constraints-dev.txt`, the version measured in `.venv`) under the constraints file, then `-r requirements-dev.txt`, and writes `.venv/.toolchain-stamp` — a hash of both pin files and the venv's Python version — only after both succeeded; with a matching stamp it installs nothing. Tests: `tests/guards/test_42_ensure_venv.py` (stub python: install order, no pip on a second run, reinstall on a changed pin file or Python version, no stamp after a failed install), `test_pip_is_pinned_in_constraints`, and the doctor test now includes pip (strict xfail in `5bb3bf9`). **Measured 2026-09-28**, two consecutive `make ci` runs: run 1 `[venv] installing pinned pip` ×1, `installing requirements-dev.txt` ×1, `up to date` ×6; run 2 `up to date` ×7, no install; the doctor test passed in both with pip pinned, so `.venv` held `pip==26.2.1` twice. **Accepted 2026-09-28** after merge `2ea6475` (PR #29), CI green; deploy done, postdeploy `tests: passed` (no runtime effect on the Pi).

### F22 – Three diverging sources of dev dependencies

- **Evidence:** `pyproject.toml` `[project.optional-dependencies].dev` (`ruff>=0.14.11`, `pytest>=8`, `typeguard>=4`, `yamllint>=1.33`); `requirements-dev.txt` (exact pins); `.pre-commit-config.yaml` `pytest-precommit` `additional_dependencies`. [V 2026-09-23]
- **Impact:** `pip install .[dev]` yields a different toolchain than `make venv`; `typeguard` exists only in one list.
- **Proposed fix:** Make `requirements-dev.txt` the only source; drop the `dev` extra or generate it.
- **Test:** `tests/precommit/test_50_toolchain_version_parity.py` — the extra is absent or identical.
- **Acceptance:** One source of dev dependencies, enforced by the test.
- **Progress (2026-09-28, R1.4 on `chore/r1-toolchain`):** `pyproject.toml` declares no dependencies (the `dev` extra and the unused `typeguard` are gone); the `Makefile` `venv` recipe installs only `-r requirements-dev.txt` and fails if the file is missing (the `.[dev]` and bare-package fallbacks are gone). Tests: `test_pyproject_declares_no_dev_dependencies`, `test_venv_installs_only_requirements_dev` in `tests/precommit/test_50_toolchain_version_parity.py` (strict xfail in `397d950`). **Open:** the third source, the `pytest-precommit` hook's `additional_dependencies`, still carries ranges; R1.5 pins it to `requirements-dev.txt` with a parity test, which closes F22.
- **Resolution (2026-09-28, R1.5 on `chore/r1-toolchain`):** the hook's `additional_dependencies` are the exact `requirements-dev.txt` pins (`pytest==8.4.2`, `requests==2.32.5`, `PyYAML==6.0.3`), enforced by `test_hook_dependencies_match_requirements_dev`; transitive pins live only in `constraints-dev.txt`, and `test_constraints_pin_exactly_and_do_not_repeat_direct_pins` rejects a package pinned in both files. All three sources now agree or are gone. **Accepted 2026-09-28** after merge `2ea6475` (PR #29), CI green; deploy done, postdeploy `tests: passed` (no runtime effect on the Pi).

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
- **Progress (2026-09-29):** the compose error disappeared as a side effect of R1.10 (F30): vector's `group_add` now holds only `${SYSTEMD_JOURNAL_GID}`, so there are no longer two equal empty items. Measured in `make ci` on `feat/r1-socket-proxy` [V 2026-09-29]: the skip moved to `tests/doctor/test_35_cadvisor_flags.py:147: cadvisor image not present locally: ghcr.io/google/cadvisor:v0.60.5`. The test still does not run, and its any-failure skip is unchanged, so the defect stands; status stays `open`.
- **Progress (2026-09-29, R1.11):** after the operator pulled `ghcr.io/google/cadvisor:v0.60.5` in WSL, `make ci` showed `test_cadvisor_flags_are_supported_by_pinned_image` PASSED for the first time [V 2026-09-29] — it proved `--docker` before the R1.11 deploy, and still passes after the revert. It runs only because of that manual pull: `tests/doctor/test_35_cadvisor_flags.py:146-147` skips when the image is missing instead of pulling it, so after a Renovate bump of the cadvisor tag it silently skips again until someone pulls the new tag, and in GitHub CI it never runs. `tests/guards/test_32_alertmanager_renderer_container.py:91` already pulls its pinned image itself. Proposed addition to the fix: pull the image named in compose (as test_32 does) and fail, not skip, when the pull fails; skip only when Docker itself is missing outside CI. Status stays `open`.

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

### F49 – Postdeploy as root writes `__pycache__` into the Pi checkout

- **Evidence:** `deploy.sh:293` runs `POSTDEPLOY_ON_TARGET=1 make postdeploy` as root; the `postdeploy` target in `Makefile` sets no `PYTHONDONTWRITEBYTECODE`. Deploy logs on 2026-09-25: `repo-ownership: mismatch detected` at 13:33 and 13:46, `OK` at 12:44 and 13:50; an operator `find . -xdev ! -user admin` at 13:50 found nothing. Confirmed after the deploy of merge `acdd38b` at 14:25 (its pull added a `tests/_lib` module and changed `test_56`): the same `find` listed exactly two root-owned files, `/home/admin/iac/raspberry-pi-homelab/tests/_lib/__pycache__/docker_volumes.cpython-313.pyc` and `/home/admin/iac/raspberry-pi-homelab/tests/postdeploy/__pycache__/test_56_monitoring_no_volume_mounts.cpython-313-pytest-8.3.5.pyc`, both 14:25; the next deploy at 14:27 logged `repo-ownership: mismatch detected; fixing to admin:admin`, after which the list was empty. [V 2026-09-25]
- **Impact:** Every deploy that changes a postdeploy test leaves root-owned files in the checkout; the next deploy's `fix_repo_ownership_if_needed` silently resets them. That routine reset would also hide a real ownership drift.
- **Proposed fix:** Set `PYTHONDONTWRITEBYTECODE=1` for the postdeploy run (in `deploy.sh` or the `Makefile` target — decide when fixing).
- **Test:** `tests/guards` — static check that the postdeploy invocation sets `PYTHONDONTWRITEBYTECODE=1`.
- **Acceptance:** Two consecutive deploys whose pulls change `tests/postdeploy` both log `repo-ownership: OK`.
- **Resolution (2026-09-25) — partly:** fixed in `scripts/tests/run-tests.sh`, not the `Makefile`: every test target goes through it, and it escalates to root on the Pi by itself (`run_pytest_as_root`), so a manual `make postdeploy` wrote root-owned bytecode too. It exports `PYTHONDONTWRITEBYTECODE=1` and sets it explicitly in the `sudo … env` call, independent of sudoers' handling of `-E`. Tests: `tests/guards/test_41_run_tests_no_bytecode.py` (behaviour of the plain path with a fake python; text contract for the root path). **Open:** the Pi acceptance needs a later deploy whose pull changes `tests/postdeploy`; the deploy of this fix changes none, so its `repo-ownership: OK` proves nothing. Deployed with merge `19c76ab` (PR #22) on 2026-09-25: two deploys green, both `repo-ownership: OK`, `find ! -user admin` empty — consistent, but not yet the proof. **Accepted 2026-09-25** (operator decision) on a before/after comparison under the same condition — a pull that changes `tests/postdeploy`: before the fix (merge `acdd38b`, 14:25) `find ! -user admin` listed two root-owned `.pyc` and the next deploy logged `repo-ownership: mismatch`; with the fix (merge `f2a3172`, which changed `tests/postdeploy/test_25_cadvisor_metrics.py`, 15:09) `find` right after the deploy was empty and the next deploy (15:10) logged `repo-ownership: OK`. The `find` directly after the deploy is a more direct measurement than the two-deploy log criterion above, which was met once rather than twice.

### F50 – The WSL layer (Python, Docker Desktop, apt) is neither documented nor checked

- **Evidence:** `docs/operations/DevWorkflow.md` covers `make venv` but not the WSL host (Python version, Docker Desktop and its WSL integration, apt/Ubuntu release); `docs/operations/runtime-updates.md` covers the Pi only; `Makefile` target `doctor` reports `FAIL: docker missing` without diagnosis or pointer. Measured 2026-09-26: `make ci` stopped in `doctor` because Docker Desktop's WSL integration was off. `.github/workflows/ci.yml` pins Python `3.12` without a patch level; WSL uses the system `python3` (3.12.3). [V 2026-09-26]
- **Impact:** A change in the WSL environment blocks or silently alters the gate that every increment relies on, and nothing tells the operator how to recover or what is expected.
- **Proposed fix:** R2d — `docs/operations/dev-environment-updates.md` (checklist and recovery), `make doctor` version checks (Python minor as in CI, Docker and Compose plugin present) with a pointer to the doc.
- **Test:** `tests/doctor` — the version checks, with a clear message per missing or mismatched tool.
- **Acceptance:** With Docker's WSL integration off, `make doctor` fails with a message naming the fix; the doc describes the update and recovery flow.

### F56 – Deploy log records postdeploy as `passed` without counts; the evidence is not kept

- **Evidence:** `deploy.sh:290-294` (`run_postdeploy_tests`) runs `make postdeploy` and then logs only `tests: passed`; `log()` at `deploy.sh:66` writes to stdout, and `deploy.sh` redirects nothing to a file (no `tee`/`exec >`). The `Makefile` can tee output to `logs/<target>-<ts>.log` only with opt-in `LOG=1` (`Makefile:101`), which `deploy.sh:293` does not set. Measured by the operator on 2026-09-28 (deploy of merge `ed8e008`): the deploy summary shows `tests: passed` and `deploy: done` with no pass/skip counts; the "62 passed, 4 skipped" in the log rows of `.claude/roadmap.md` §7 comes from the operator reading it off the pytest output, not from any kept record. [V 2026-09-28]; whether pytest's own summary line reliably reaches the operator's terminal view [I — the operator confirms on the next deploy].
- **Impact:** IN7 makes "postdeploy green" part of *done*, but the only kept evidence is a word. A test that starts skipping (the false-green class of F47 and F23) or a test that vanishes leaves `tests: passed` unchanged, so a regression in coverage cannot be seen from the deploy log, and every increment log row has the same gap.
- **Proposed fix:** `run_postdeploy_tests` records the pytest result: write a JUnit XML (`--junitxml`) or capture the summary line to a host log path outside the checkout, and log `tests: passed (<n> passed, <m> skipped, …)` — or `tests: FAILED (…)` before `die`. Decide the host path together with the log location of the backup scripts (`docs/operations/BackupVerifyRestore.md` names `logs/`). IN9 check at fix time: a new host file.
- **Test:** `tests/guards` — run `run_postdeploy_tests` (or an extracted helper) with a stub `make` that prints a pytest summary; assert the logged line carries the counts, and that a failing stub is logged as failed with its counts.
- **Acceptance:** The next deploy log shows `tests: passed (<n> passed, <m> skipped …)`; the §7 log rows cite that line instead of an operator reading.
- **Progress (2026-09-29):** the [I] part is answered. On the deploy of merge `68a3118` (R1.7) pytest's own summary line `63 passed, 4 skipped in 15.86s` reached the operator's terminal [V 2026-09-29, operator]. It was read from the terminal, not from a kept file, so the defect stands: `deploy.sh` still keeps no record of the counts. Status stays `open`.

### F59 – `make ci` never runs the pre-commit hooks on new, untracked files

- **Evidence:** `Makefile:263` (target `hooks`, called by `precommit` and so by `ci`) runs `pre-commit run --all-files`, which selects files from `git ls-files` — tracked files only. `.pre-commit-config.yaml:6-7` (`trailing-whitespace`, `end-of-file-fixer`) and `:49-51` (`ruff`, `ruff-format`) therefore skip a file that is not yet added, while pytest still collects and runs it. Measured twice [V 2026-09-29]: `tests/guards/test_43_postdeploy_markers.py` (commit `73cbb07`) and `tests/guards/test_54_vector_config_hash.py` (commit `f2e01b2`) passed `make ci` untracked, and the hooks rewrote them only when the operator committed (a line wrap in the first; trailing whitespace and a quote style change in the second).
- **Impact:** "Validate first, commit afterwards" (IN4) holds only half for new files — exactly the files an increment adds most often. The operator's commit then fails once, or silently commits fixer output that nobody reviewed as a diff. Non-Python files (Markdown, YAML, shell) are not covered by any other check before the commit.
- **Proposed fix:** Let `make hooks` also run the hooks on untracked, not-ignored files, e.g. a second run `pre-commit run --files $(git ls-files --others --exclude-standard)` when that list is not empty. Interim practice until then (recorded in `.claude/roadmap.md` §8): run `.venv/bin/ruff format --check --no-cache .` and `.venv/bin/ruff check --no-fix --no-cache .`, which read the file system, before handing over a commit with new Python files.
- **Test:** `tests/guards` — the `hooks` recipe in `Makefile` covers untracked files (static check of the recipe); plus one manual negative control at fix time: an untracked file with trailing whitespace makes `make ci` fail.
- **Acceptance:** `make ci` fails on a new, untracked file with trailing whitespace, and passes once it is fixed.

## Host runtime updates

Reviewed 2026-09-26 (`scripts/host-runtime/`). The structure is sound — plan/apply split, no
automatic reboot, EEPROM separate, clean Git tree required, no `rpi-update`; the findings are about
what the scripts do not enforce. Scheduled in R3b, after backup (`.claude/roadmap.md` §9.6).

### F51 – Host upgrade apply does not execute the reviewed plan

- **Evidence:** `scripts/host-runtime/upgrade-apply.sh:26-28` runs `apt-get update`, `apt-get -y full-upgrade` and `apt-get -y autoremove --purge` afresh; `scripts/host-runtime/upgrade-plan.sh:27` only simulates and stores nothing. `DEBIAN_FRONTEND=noninteractive` (`scripts/host-runtime/upgrade-apply.sh:25`) without a `Dpkg::Options` conffile policy. [V 2026-09-26]; conffile behaviour under noninteractive [I — confirm with a stubbed `dpkg` in the R3b.1 harness or the Debian docs].
- **Impact:** What gets installed is whatever is current at apply time, not what the operator reviewed in the plan; `autoremove --purge` removes packages and their configuration that the plan never listed; a changed conffile can stall or silently replace configuration.
- **Proposed fix:** The plan writes `package=version` plus a timestamp to a host file; apply refuses if it is missing, stale, or differs from a fresh simulation; explicit `--force-confdef --force-confold`; the plan lists the `autoremove` set.
- **Test:** `tests/guards` with `PATH` stubs (F53) — apply refuses a missing/stale/different plan and passes the conffile options.
- **Acceptance:** A stubbed apply with a plan that differs from the simulation exits non-zero without calling `full-upgrade`.

### F52 – Mutating host-runtime scripts have no backup gate

- **Evidence:** `docs/operations/runtime-updates.md:34-39` and its acceptance list require backup and backup verification first; `scripts/host-runtime/upgrade-apply.sh` and `scripts/host-runtime/eeprom-apply.sh` check only `require_pi` and `require_clean_git_tree` (`scripts/host-runtime/common.sh:29,96`). [V 2026-09-26]
- **Impact:** The one safeguard that makes a host update reversible exists only on paper; an operator in a hurry can upgrade packages or the bootloader without a restorable backup.
- **Proposed fix:** After R3 provides a verified-backup record: both scripts refuse unless the last verified backup is younger than a set age; an explicit override flag with a logged reason.
- **Test:** `tests/guards` with stubs — apply refuses without, or with a stale, verification record; the override is logged.
- **Acceptance:** Without a fresh verified backup both scripts exit non-zero before any `apt-get` or `rpi-eeprom-update -a` call.

### F53 – host-runtime scripts are untestable off the Pi and untested

- **Evidence:** `scripts/host-runtime/common.sh:29` `require_pi` has no test override (the backup scripts use `HOMELAB_ALLOW_NON_PI`, `.claude/rules/backup-restore.md`); no file under `tests/` or `.github/` references the scripts (search 2026-09-26). Only ShellCheck covers them via `.pre-commit-config.yaml`. [V 2026-09-26]
- **Impact:** Every change to the scripts that mutate the host is first exercised on the Pi — the pattern that cost two fix-forward rounds in R1.
- **Proposed fix:** A `HOMELAB_ALLOW_NON_PI` test mode and `PATH` stubs for `apt-get`, `dpkg-query`, `rpi-eeprom-update`, `docker`, `sudo`.
- **Test:** `tests/guards/test_7x_host_runtime_*.py` — plan mutates nothing, apply refuses a dirty tree, EEPROM never runs in the routine path.
- **Acceptance:** The guard tests run in CI and fail when, for example, `upgrade-apply.sh` calls `rpi-eeprom-update -a`.

### F54 – Docker packages upgrade uncontrolled inside the routine APT upgrade

- **Evidence:** `scripts/host-runtime/upgrade-apply.sh:27` `full-upgrade` includes `docker-ce`, `containerd.io` and the Compose plugin, which `scripts/host-runtime/common.sh:153-176` only reports on; no `apt-mark hold`, no separate step, no postdeploy right after. [V 2026-09-26]; that a `docker-ce`/`containerd.io` upgrade restarts the daemon and all containers [I — standard package behaviour; observe in R3b.6].
- **Impact:** A routine security update can restart every service and change the container runtime without the deploy-time checks; related to F18.
- **Proposed fix:** ADR in R3b: hold the Docker packages and upgrade them in a separate controlled step (stop, upgrade, start, postdeploy), or accept the restart explicitly. Postdeploy minimum versions for Docker Engine and the Compose plugin.
- **Test:** `tests/guards` (stubs) for the chosen flow; `tests/postdeploy` minimum-version check.
- **Acceptance:** The ADR exists; the routine path cannot change the Docker packages unnoticed; the version check is green on the Pi.

### F55 – Plan output, audit and runtime-updates doc disagree; audit gaps pass silently

- **Evidence:** `docs/operations/runtime-updates.md:47-54` says the plan shows disk space and failed systemd units — `scripts/host-runtime/upgrade-plan.sh` prints neither (only `scripts/host-runtime/audit-runtime.sh:49,53` does); the doc uses `~/raspberry-pi-homelab` while the Pi checkout is `~/iac/raspberry-pi-homelab` (operator deploy output, 2026-09-25); "Last verified: 2026-05-21". `scripts/host-runtime/common.sh:61` skips a section with only a warning when sudo is not available non-interactively, and many calls end in `|| true`, so an incomplete audit exits 0; no machine-readable output or version history; the EEPROM release channel is never shown (`scripts/host-runtime/eeprom-apply.sh:22`). [V 2026-09-26]
- **Impact:** The operator reviews less than the doc promises, may follow a wrong path, and cannot tell a complete audit from a partial one or see version drift over time.
- **Proposed fix:** R2b corrects the doc; R3b adds the missing plan output, a machine-readable audit summary (versions, EEPROM channel, reboot state) and a distinct exit code for an incomplete audit.
- **Test:** `tests/guards` (stubs) — audit without sudo reports "incomplete" with its exit code; the plan prints disk and failed units.
- **Acceptance:** Doc and scripts agree; an incomplete audit is distinguishable by exit code.

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

## R1 increments

The grouping into increments, their order and what is open or done per group moved to
`.claude/roadmap.md` §6 on 2026-09-26. `tools/check_findings.py` keeps it consistent with the
index above.
