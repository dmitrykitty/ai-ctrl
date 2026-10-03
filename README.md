# AI Control Layer

T01 foundation and T02 launcher/isolation are complete. The host supervisor launches real Claude Code 2.1.285 in Docker with enforced egress, host-compatible non-root identity, selected workspace, dedicated provider state, resource limits, and cleanup. See `NOTES.md` for verified results and `plan.md` for the approved architecture.

## Prepare and authenticate

Prerequisites: Docker with Compose, `make`, and an existing Python with pip. Bootstrap installs project-local uv 0.12.22 and Python 3.12.15, leaving system Python unchanged. Dependencies are frozen in `uv.lock`.

```bash
make prepare
source .venv/bin/activate
aictrl doctor
make claude-auth-status
make claude-login
```

`make prepare` builds the pinned base, actual Claude, and mitmproxy runtime images. Installer and binary checksums, upstream revisions, resolved base digests, and observed image IDs are recorded in `docker/images.lock.json`. Actual build qualification is Linux/amd64.

Authentication uses only `aictrl-claude-state` at `/home/dev/.claude`. The offline status helper mounts it read-only, determines its numeric owner from directory metadata, drops all capabilities before native status, and displays only authenticated/unauthenticated or a safe error. It exits 0/1/2 respectively; `make` reports nonzero as failure. Login checks status first: authenticated state returns 0 without a terminal or browser; unauthenticated state uses the restricted native login flow. Operational errors abort. Host Claude, SSH, AWS, and Kubernetes state is never mounted. See [authentication instructions](docs/claude-authentication.md).

## Run Claude

```bash
aictrl run claude demo/project
aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_OK' --timeout 90
```

For another repository, pass its directory to this installed CLI. `aictrl run claude .` works from a safe workspace. This control repository's root is deliberately rejected because it contains control assets and local Git authentication configuration; use `demo/project` here. Missing paths, files, protected host/control directories, unsupported agents, and concurrent Claude-state use are rejected. The launcher checks authentication before creating runtime infrastructure and never starts a browser login flow.

The native interactive workspace-trust dialog remains enabled. After authentication preflight, bootstrap sets the native `hasCompletedOnboarding` UI preference inside the provider volume so an existing login does not encounter the first-run login picker. Credential files are never opened by that helper, and it does not accept workspace trust automatically.

Trusted setup configures the firewall, installs the public proxy CA, and prepares only container-owned home/provider state. Claude then runs using the host's positive numeric UID/GID (verified 1000:1000), with supplementary groups and every capability set removed and no-new-privileges enabled. Workspace ownership and modes are preserved; no repository-wide chown or chmod is performed.

The agent mounts exactly the selected workspace at `/workspace`, dedicated Claude state, and read-only public proxy CA. The CA private key stays in a separate proxy-only volume. No Docker socket, host home, enterprise credentials, policy storage, or audit storage is mounted.

## Current network coverage

T02 uses transitional `EGRESS_ONLY`: native provider endpoints through mitmproxy 12.2.3, without forcing `ANTHROPIC_BASE_URL`. `APPLICATION_GATEWAY` is represented by the adapter but requires T03 infrastructure.

The agent joins an internal network and may reach only its designated proxy TCP socket, required TCP loopback, and established replies. Direct internet, external IP/DNS, Docker DNS, UDP/QUIC, IPv6, host services, and siblings are blocked. Unsetting proxy variables or removing the proxy does not restore connectivity. Default-deny proxy rules admit exact adapter provider hosts/ports and explicitly configured test destinations. Unapproved requests do not reach upstream. Public provider DNS results are checked and connected by numeric address; private resolution is rejected. Synthetic private targets require an explicit trusted test pin; the shipped configuration has none.

Provider HTTPS remains opaque CONNECT with destination/port enforcement and end-to-end TLS. Public CA lifecycle is ready, but T02 makes no claim of LLM body inspection. The application gateway, central policy, guards, budgets, MCP authorization, audit pipeline, and dashboard belong to later milestones. The demo-agent adapter remains a fixture.

## Limits, shutdown, and verification

Default limits are 2 CPUs, 2048 MiB RAM, 256 PIDs, and a 600-second host wall-clock deadline including infrastructure preparation. `--timeout` can only shorten that limit. Normal exit is propagated; host SIGINT/SIGTERM return 130/143, deadline expiry returns 124, and launch/input errors return 2. Native terminal Ctrl+C also exits cleanly. Cleanup removes only session resources and preserves workspace/provider state. Restrict/terminate hooks are available for later response logic.

```bash
make test
make test-fast
make verify-runtime-boundary
make verify-auth-boundary
make verify-claude-state
make compose-config
```

87 offline tests passed. The real runtime qualification passed 29 boundary checks twice plus cleanup, no-upstream-hit, deadline, signal, exit-code, concurrency, proxy-loss, and partial-start failure checks. These use the production bootstrap, firewall, proxy, and supervisor with separate synthetic state and a pinned synthetic backend. Provider availability is unnecessary for ordinary tests. Real interactive startup and a live subscription reply `AICTRL_OK` were verified separately.

Project-owned environment variables use `AICTRL_`. Runtime bootstrap uses `AICTRL_BOOTSTRAP_MODE`, `AICTRL_PROXY_IP`, `AICTRL_UID`, and `AICTRL_GID`; future gateway rules use `AICTRL_GATEWAY_IP`. Raw Compose inputs include `AICTRL_WORKSPACE` and `AICTRL_RUNTIME_DIR`; the normal launcher renders validated absolute paths and per-session infrastructure configuration. Rebuild images after changing bootstrap/proxy assets.

See [architecture](ARCHITECTURE.md), [reuse decisions](REUSE_DECISIONS.md), [attribution](OPEN_SOURCE.md), [tasks](TASKS.md), and [verification](NOTES.md).
