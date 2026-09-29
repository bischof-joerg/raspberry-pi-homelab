# ADR-0012: Docker API access through a filtering socket proxy

- **Status:** Proposed
- **Date:** 2026-09-29
- **Scope:** every container in this repository that reads the Docker Engine API; today vector
  (since R1.10) and, from R1.11, cadvisor. Findings F30 and F57.

## Context

vector's `docker_logs` source and cadvisor's Docker integration both need Docker container
metadata. Until R1.10 each mounted `/var/run/docker.sock`, and vector also joined the Docker group
(`group_add: ${DOCKER_GID}`). A `:ro` mount protects the socket inode, not the API behind it, so
either container could create a privileged container and take the host (F28, F30, F57).
`.claude/rules/compose-stacks.md` already names a socket proxy as the default and a direct mount as
an exception.

Both consumers parse data an attacker can influence: vector reads arbitrary container log lines,
cadvisor reads host-controlled files and answers every container on `monitoring`. Removing their
Docker API access is not an option: container logs (vector) and the `name=` label on container
metrics (cadvisor, `tests/postdeploy/test_25_cadvisor_metrics.py`) depend on it.

## Decision

1. A service that needs the Docker API MUST NOT mount a runtime socket or join the Docker group. It
   reads the API through the service `socket-proxy` at `http://socket-proxy:2375`.
2. `socket-proxy` runs `wollomatic/socket-proxy`, pinned to an exact tag (1.13.1 at the time of
   writing). It is the only service that mounts `/var/run/docker.sock` (`:ro`) and the only one
   with the Docker group. It runs as uid 65534 with `read_only`, `cap_drop: [ALL]`,
   `no-new-privileges`, a healthcheck and a 64M memory limit, and publishes no port.
3. The proxy allows **GET only**. The allowlist names exactly the paths its consumers use; for
   vector 0.53.0 (read in `src/sources/docker_logs/mod.rs` on 2026-09-29) these are `events`,
   `containers/json`, `containers/<id>/json` and `containers/<id>/logs`, with or without the
   `/v1.<n>` prefix. Any other method, and `archive`, `export`, `attach`, `images`, `exec`, are
   refused. Adding a path or a method is an amendment of this ADR.
4. The proxy and its consumers meet only on the network `docker-api`. It is declared `external`
   in compose (created and owned by `scripts/network/bootstrap-networks.sh`, R1.9) and created
   with Docker's `--internal` flag (no default route); the script refuses an existing
   `docker-api` that is not internal. It has no other members; the proxy joins no other network.
   Per the Compose specification, attributes other than `name` do not apply to an external
   network, so `internal: true` does not belong in the compose file.
5. `-allowfrom` names the consumers by service name (resolved per request, no cache), plus
   `127.0.0.1/32` so the postdeploy probe can test the allowlist from the proxy's own network
   namespace; that namespace is reachable only for someone who already controls Docker.
6. A request the proxy refuses is logged at WARN as `blocked request`. A refused request from a
   consumer is a defect: its data goes missing silently. Postdeploy fails on it.

cadvisor moves to the proxy in R1.11 and adds the endpoints it needs, each measured; this ADR is
amended then. Until R1.11 cadvisor keeps its direct socket mounts (F57), as allowlisted in
`tests/guards/test_50_docker_socket_mounts.py`.

## Alternatives considered

- **`tecnativa/docker-socket-proxy`.** Widely used, but its switches are per API section:
  `CONTAINERS=1` also opens `GET /containers/<id>/archive`, i.e. reading any file from any
  container, and the image runs as root by default. Rejected for the coarser filter.
- **Proxy on the `monitoring` network.** Simpler, but every monitoring container (Grafana, vmagent,
  …) could then read the Docker API, including every container's environment. Rejected.
- **Network defined in the compose file instead of an external one.** Less host state, but the repository
  manages networks explicitly through the bootstrap script (`docs/architecture/networking-and-firewall-model.md`);
  the operator chose the external, bootstrapped variant on 2026-09-29.
- **journald-only log collection for vector.** Would remove vector's Docker API need, but requires
  switching the Docker logging driver on the host (a `daemon.json` change that restarts every
  container, F18) and loses the Compose labels vector uses for `stack` and `service`. Rejected for
  now; it remains an option if the proxy proves fragile.
- **Keep the direct mounts and accept the risk.** Rejected: host-root equivalence for two services
  that parse untrusted input (F30, F57, severity High).

## Consequences

### Positive

- A compromised vector can no longer create, start, exec into or copy from containers: those calls
  need POST or the refused paths.
- One small service, which parses no foreign data and is reachable only from named consumers on an
  internal network, holds the socket instead of two large ones.
- Every refused request is visible in the proxy log and fails postdeploy.

### Negative / Tradeoffs

- **Secrets stay readable.** `GET /containers/<id>/json` returns `Config.Env`, which includes
  values injected from `/etc/raspberry-pi-homelab/monitoring.env` (for example the Grafana admin
  password and the SMTP credentials in the renderer's environment). A compromised consumer can read
  them. The proxy cannot filter response bodies; the remedy is to move secrets out of container
  environments (not planned yet).
- **The proxy itself is host-root equivalent.** It holds the socket and the Docker group. The
  mitigation is its size, its hardening and its reach, not a lack of privilege.
- One more image to keep current (Renovate covers it through the monitoring compose rule) and one
  more container on the Pi (64M limit).
- The allowlist is coupled to the consumers' code: an upgrade of vector or cadvisor that calls a
  new endpoint loses data until the allowlist is amended. Postdeploy catches it (Decision 6), but
  only after the deploy.
- vector now depends on the proxy being healthy (`depends_on: condition: service_healthy`).

## Enforcement

- `tests/guards/test_53_socket_proxy_contract.py` — image pinned, hardening, only the socket mount,
  GET only, allowlist accepts vector's paths and refuses `archive`, `export`, `attach`, `images`
  and `..` traversal, `-listenip`/`-allowfrom`, network membership, vector's `docker_host` and no
  Docker group.
- `tests/guards/test_50_docker_socket_mounts.py` — only allowlisted services mount a runtime socket.
- `tests/guards/test_10_monitoring_compose_contract.py` — `EXPECTED_NETWORKS`.
- `tests/postdeploy/test_26_docker_socket_proxy.py` — proxy healthy; GET 200, POST 405, `archive`
  403; no `blocked request` from a consumer; vector without socket mount and Docker group.
- `tests/postdeploy/test_40_vector_pipeline.py` — container logs still reach VictoriaLogs.
- `tests/postdeploy/test_35_network_and_ufw.py` — `docker-api` is internal.
