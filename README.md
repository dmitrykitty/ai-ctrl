# AI Control Layer

A control layer for actual coding agents in isolated Docker runtimes. Claude Code is the first integration, with a deterministic demo agent for repeatable checks and Codex as a later adapter/fallback. See `plan.md` for the approved design and `NOTES.md` for current status.

Current scope: T01 foundation. Python packaging, versioned Pydantic contracts, adapter configuration, a CLI doctor, pinned runtime assets, and the native login path are implemented. The launcher begins in T02; the application gateway begins in T03. `aictrl run claude .` exits with status 2 and `runtime not implemented yet — milestone T02`.

## Prepare

Prerequisites: a reachable Docker daemon, Docker Compose, `make`, and an existing Python with pip to bootstrap uv. The bootstrap installs uv 0.12.22 and Python 3.12.15 locally, then synchronizes the committed `uv.lock`. It leaves the system Python unchanged. Runtime dependencies are FastAPI, uvicorn, Pydantic, PyYAML, HTTPX, and Typer; pytest is the test dependency.

```bash
make prepare
source .venv/bin/activate
aictrl --help
aictrl doctor
```

`make prepare` covers T01 dependencies and runtime images. Local semantic models, the full offline judge suite, and live agent qualification are later milestones. Run uv through `./scripts/uv.sh`; it selects the project's local installation and cache. `make bootstrap` prepares Python dependencies alone.

The Claude image installs actual Claude Code 2.1.285 through the upstream official native installer. Base image digest, signed Debian snapshot, installer checksum, binary checksums, and observed local image IDs are recorded in `docker/images.lock.json`. Builds refuse changed installer content or binary checksums. After an intentional upgrade, re-inspect the installer and update pins together. Local builds have immutable image IDs; a published registry digest is recorded only when available.

## Check the foundation

```bash
make test
make compose-config
make claude-version
make verify-claude-state
make verify-auth-boundary
```

`make test` runs the T01 offline contract, adapter, doctor, and authentication-transport checks. One transport check binds a local loopback port. The two live Docker checks verify named-state persistence and the authentication bootstrap's actual firewall, provider allowlist, IPv4/DNS/IPv6 bypass blocking, and privilege drop. They make no model request and do not qualify the future T02 runtime. `doctor` returns nonzero for missing required prerequisites; an image not yet built is a warning.

## Authenticate Claude

```bash
make claude-login
```

Run this in an interactive terminal. Open the CLI's authorization URL in the host browser and complete the native subscription login. Enter any returned code only in that terminal. See [authentication instructions](docs/claude-authentication.md) for restrictions, state verification, and blockers.

Claude state is `aictrl-claude-state` mounted at `/home/dev/.claude`. Provider authentication state can exist inside this dedicated agent state volume because the selected agent requires it. Enterprise resource credentials must never be placed there. Do not mount host Claude/Codex, SSH, AWS, or Kubernetes directories into containers. Login mounts no workspace and preserves the named volume when it exits. Only one active container may use this state volume.

## Scope and reuse

The runtime Compose profile is a skeleton whose services refuse startup until implemented. The small CONNECT transport is restricted to T01 native login; future runtime egress uses the planned enforcing proxy. Native login deliberately uses end-to-end TLS with destination-only coverage. No protected agent operation is launched through this bootstrap transport.

The reused upstream uses UID/GID 501. T02 must handle chosen-workspace write permissions while retaining a non-root agent and dropped capabilities. CPU/memory/PID limits are prepared; the login helper also enforces a ten-minute timeout. The host supervisor's runtime wall-time enforcement belongs to T02.

See [reuse decisions](REUSE_DECISIONS.md), [attribution](OPEN_SOURCE.md), [architecture](ARCHITECTURE.md), [task status](TASKS.md), and [verified results](NOTES.md). `plan.md` remains unchanged.
