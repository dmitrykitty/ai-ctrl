# Implementation notes

Current milestone: T01

Status: COMPLETE for the T01 foundation and cleanup. Native authentication now reports an authenticated stored state. T02 remains TODO until this cleanup is recorded; the user has authorized proceeding to the supplied T1/T02 instruction afterward.

Working commands (from project root):
- `make bootstrap` — local uv/Python bootstrap and frozen dependency synchronization.
- `./scripts/uv.sh --version` — uv 0.12.22.
- `.venv/bin/python --version` — Python 3.12.15.
- `./scripts/uv.sh sync --frozen --offline` — 29 installed packages checked; lock remains valid offline.
- `./scripts/uv.sh lock --check --offline` — lock agrees with `pyproject.toml`.
- `.venv/bin/aictrl --help` — `doctor` and `run` commands available.
- `make doctor` — all six checks OK: Python, Docker daemon 29.8.1, Compose 5.5.1, validated configuration, directories, Claude image.
- `make test` — 40 passed on Python 3.12.15; includes a loopback socket test and safe authentication-status/error handling, with no external model/provider request.
- `make compose-config` — runtime skeleton and authentication Compose files validate.
- `make claude-image` — base and real Claude image built; actual `claude --version` returns `2.1.285 (Claude Code)`; state volume created and image identities recorded.
- `make claude-version` — offline/non-root real CLI version check.
- `make verify-claude-state` — named state survives two separate containers; directory owner 501:501; synthetic marker removed afterward.
- `make verify-auth-boundary` — all ten actual Docker checks pass: non-root user, all capability sets dropped, no-new-privileges, provider CONNECT allowed, unrelated/private CONNECT denied, direct IPv4 denied, embedded DNS TCP/UDP denied, direct IPv6 denied. This tests authentication bootstrap, not the future runtime.
- `make claude-auth-status` — native Claude status reports authenticated; offline, non-root, all capabilities dropped, read-only dedicated state, boolean-only output.
- `make claude-login` — two consecutive noninteractive calls returned 0 with `Claude is already authenticated.` and opened no new browser flow. Unauthenticated state uses the existing restricted native login flow; operational errors abort.

Failing or incomplete commands:
- `.venv/bin/aictrl run claude demo/project` — expected status 2: `runtime not implemented yet — milestone T02`; no container launched.
- The original native status was unauthenticated and the first login attempt was cancelled at its browser/code prompt. That earlier browser-authentication exception is resolved: the new helper now reports authenticated. No live model response is claimed by this cleanup.
- Assistant sandbox initially blocked Docker socket access and the unit test's localhost bind. Authorized execution outside that sandbox verified Docker and all 33 tests. These are resolved execution-environment restrictions, not broken project commands.

Decisions:
- Starting state on 2026-10-03: only `plan.md`; no existing implementation or repository instructions. Preserve that file.
- Use approved upstream commit `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04`.
- Use one implementing agent, Python 3.12, minimal dependencies, and a configuration-oriented adapter boundary.
- User explicitly authorized installing Python, uv, and required prerequisites.
- Git was initialized on branch `main`; T01 is organized into six logical commits at the user's request. The configured origin is `https://github.com/dmitrykitty/ai-ctrl.git`; it was empty before this initial publication. The starting host Python 3.14.4 was retained; project Python is 3.12.15.
- Six direct runtime dependencies plus pytest are locked with hashes in `uv.lock`. The build backend is hatchling 1.27.0.
- Official base: Python 3.12.15 slim-bookworm, digest `sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3`; signed apt snapshot `20261002T000000Z`.
- Actual CLI: Claude Code 2.1.285, installed through the checksum-pinned official installer with its mutable bootstrap lookup pinned to the requested target. The executable is promoted to a root-owned path; bootstrap PATH contains no agent-writable directories.
- Observed local base identity: `sha256:6aa766403c933b40f83857e64ffac4ecd551a573bac5acc625623f5787247a20`.
- Observed local Claude identity: `sha256:3753162762467711f5f4cde51d56942cce1bf26cc62f5e638f9e3c86fac8103f`. Local Docker RepoDigests are recorded in `docker/images.lock.json`; these images have not been published to a remote registry.
- Provider state is only `aictrl-claude-state` → `/home/dev/.claude`; accepted provider-authentication exception is documented. No host agent, SSH, AWS, or Kubernetes directory was mounted.
- Auth-only CONNECT transport uses end-to-end TLS and explicit destination-only coverage; native login command restriction and actual network enforcement prevent an unenforced agent launch. Runtime services and `aictrl run` remain explicit nonfunctional stubs until their milestones.
- Every copied/adapted upstream file and its MIT notice is recorded in `OPEN_SOURCE.md` and `REUSE_DECISIONS.md`.

Known blockers:
- There are no remaining T01 cleanup, authentication-state, Python, dependency, image-build, Compose, or Docker-daemon blockers. A live subscription response remains separate runtime qualification.

Follow-up verification (2026-10-03):
- Standardized all project environment variables on the `AICTRL_` prefix, including the demo gateway URL and state probe. Updated bootstrap/firewall consumers, Compose producers, verification helpers, and README together.
- Rebuilt both Docker images and reverified actual Claude Code 2.1.285. Updated the image identities above and in `docker/images.lock.json`.
- All 33 offline tests, shell syntax checks, both Compose configurations, the `AICTRL_WORKSPACE` mount override, and the entrypoint's restricted auth/runtime responses passed.
- A native login container was active, so the standard boundary helper correctly refused its shared configuration. Ran the existing ten boundary probes on a separate internal test network and the updated state helper with a temporary named volume; all passed. Only proxy addresses and test resource names were substituted for isolation. Test containers, networks, and volume were removed; the active login and provider state were preserved.

Cleanup verification (2026-10-03):
- Scanned the complete project source, scripts, Docker/Compose, tests, docs, Makefile, and examples; all project-owned environment variables use `AICTRL_`. Unrelated upstream identifiers are preserved.
- Added `make claude-auth-status` and made login idempotent using the real dedicated volume. Native JSON and stderr are never echoed; only the authentication boolean or a safe error is displayed. No credential files were inspected or copied.
- All 40 tests, shell syntax checks, both Compose configurations, original state-persistence helper, and all ten original Docker authentication-boundary probes pass. Authentication helpers left no running containers; the provider volume was preserved. T01 remains COMPLETE.

Next-milestone requirements:
- T02 must implement the host supervisor/lifecycle, actual enforcing runtime proxy, selected workspace permissions for UID 501, public CA export, and wall-clock enforcement. The prepared runtime entrypoint deliberately refuses to start an agent today.
- T03 must route native Anthropic streaming through the application gateway and establish policy/SQLite events. No model request or live agent qualification was attempted in T01.

Next milestone: T02 — launcher and isolation; begin only after explicit instruction.
