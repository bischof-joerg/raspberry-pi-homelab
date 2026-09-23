---
paths:
  - "stacks/**"
---

# Compose stacks

Applies when editing anything under `stacks/`. The monitoring stack is the reference
implementation; a new stack copies its shape, not its service list.

## MUST

- **Pin every image by tag, never `latest`.** Digests are the stated target (`ChatGPTHint.txt` §2)
  but are not used yet — finding F3. Do not introduce a new unpinned image under any circumstances.
- **Set the project name explicitly.** Pattern `<org>-<site>-<env>-<stack>`, e.g.
  `name: ${COMPOSE_PROJECT_NAME:-homelab-home-prod-mon}` in
  `stacks/monitoring/compose/docker-compose.yml`.
- **Declare networks explicitly.** `monitoring` and `apps` are *external*, bootstrapped by
  `scripts/network/bootstrap-networks.sh`. No implicit default network.
- **Bind mounts only, no named volumes** (ADR-0008). Data lives under
  `/srv/data/stacks/<stack>/<service>/` on the Pi.
- **Bind ports to `127.0.0.1` unless LAN exposure is a deliberate, documented decision.**
  Currently LAN-exposed: Grafana `3000` and VictoriaLogs `9428` (UFW-restricted). Both are
  intentional, but the decision is **not recorded in any ADR** — `ADR-0001-networking-and-firewall.md`
  mentions neither port (F42). Treat them as precedent, not as documentation, and do not cite them
  to justify a third exposed port.
- **A read-only mount does not contain a Docker socket.** `/var/run/docker.sock:ro` prevents writes
  to the socket *file*; it does not prevent Docker API calls, so any container with the socket and
  the `docker` group has host-root equivalence — `:ro` is not a mitigation (F28, F30). If a service
  needs container metadata, treat a socket proxy as the default and a direct mount as an exception
  that needs an ADR.
- **Harden every service**: `read_only: true`, `cap_drop: [ALL]`,
  `security_opt: [no-new-privileges:true]`, a non-root `user:`, and a `healthcheck`.
- **Use short service names** without prefixes: `grafana`, not `mon-grafana`.
- **No secrets in compose files or in a repo `.env`.** See `secrets.md` and ADR-0007.

## SHOULD

- Add a `healthcheck` even where the upstream image has none — `victorialogs`, `node-exporter`
  and `cadvisor` currently lack one (F7), and `victorialogs` also lacks a `restart` policy.
- Keep resource limits where memory growth is plausible (VictoriaMetrics 4G, VictoriaLogs 2G).
- Put host data under `/srv/data/stacks/<stack>/<service>/`, named after the service. A service
  that needs a second directory suffixes it, as `alertmanager-config` does.
  (`ChatGPTHint.txt` §4 proposes `<service>-data|config|db` instead; the implementation does not
  follow it, and renaming would be a data migration — the hint is wrong here, not the repo. F40.)

## Documented exceptions — do not "fix" these

- `cadvisor` runs `privileged: true` as root, plus `pid: host` and a **writable** Docker socket.
  An inline compose comment calls this a Pi 5 necessity, but **no document records the exception and
  `docs/monitoring.md` claims the opposite** (F46). Treat it as existing practice under review, not
  as a settled decision, and do not cite it to justify a second privileged container.
- `alertmanager-config-render` is a one-shot `alpine` renderer. It runs `apk add gettext` at
  runtime, which is a network dependency and non-deterministic (F8) — a known defect, not a
  pattern to copy.

## When adding or changing a service

The config hash in `deploy.sh` (`compute_monitoring_config_hash`) decides whether containers are
recreated. It currently covers only four files and misses `vmalert/rules/*`, `stacks/monitoring/vector/vector.yaml`,
`alertmanager.yml.tmpl` and the Grafana provisioning (F1/F2). **If you add a mounted config file,
check whether the hash covers it** — if not, a change to it will not trigger a recreate.

Every new image also needs Renovate coverage in the same increment (`ci-renovate.md`).

## Sources

`stacks/monitoring/compose/docker-compose.yml`, `docs/architecture/adr/ADR-0008-bind-mounts-only.md`,
`docs/architecture/adr/ADR-0007-secrets-and-env-files.md`, `deploy.sh`, `ChatGPTHint.txt` §4 and §7.

## Violations

```yaml
image: grafana/grafana                  # unpinned
volumes: [grafana-data:/var/lib/grafana] # named volume, violates ADR-0008
ports: ["9093:9093"]                     # LAN-exposed without a decision
```
