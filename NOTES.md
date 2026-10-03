# Implementation notes

Current milestone: T01

Status: COMPLETE for the T01 foundation; native browser authentication is pending the user. The explicitly allowed interactive-login exception is recorded below. T02 remains TODO and requires the next instruction.

Working commands (from project root):
- `make bootstrap` — local uv/Python bootstrap and frozen dependency synchronization.
- `./scripts/uv.sh --version` — uv 0.12.22.
- `.venv/bin/python --version` — Python 3.12.15.
- `./scripts/uv.sh sync --frozen --offline` — 29 installed packages checked; lock remains valid offline.
- `./scripts/uv.sh lock --check --offline` — lock agrees with `pyproject.toml`.
- `.venv/bin/aictrl --help` — `doctor` and `run` commands available.
- `make doctor` — all six checks OK: Python, Docker daemon 29.8.1, Compose 5.5.1, validated configuration, directories, Claude image.
- `make test` — 33 passed on Python 3.12.15; includes a loopback socket test, with no external model/provider request.
- `make compose-config` — runtime skeleton and authentication Compose files validate.
- `make claude-image` — base and real Claude image built; actual `claude --version` returns `2.1.285 (Claude Code)`; state volume created and image identities recorded.
- `make claude-version` — offline/non-root real CLI version check.
- `make verify-claude-state` — named state survives two separate containers; directory owner 501:501; synthetic marker removed afterward.
- `make verify-auth-boundary` — all ten actual Docker checks pass: non-root user, all capability sets dropped, no-new-privileges, provider CONNECT allowed, unrelated/private CONNECT denied, direct IPv4 denied, embedded DNS TCP/UDP denied, direct IPv6 denied. This tests authentication bootstrap, not the future runtime.
- `make claude-login` — in an interactive terminal, native `claude auth login --claudeai` reaches the authorization URL and code prompt through the restricted proxy. User completion is still required.

Failing or incomplete commands:
- `.venv/bin/aictrl run claude demo/project` — expected status 2: `runtime not implemented yet — milestone T02`; no container launched.
- Native `claude auth status` — status 1 and `loggedIn: false`; no account authorization has been completed.
- The login attempt was cancelled at its native browser/code prompt (native status 130, make status 2); temporary authentication containers/networks were removed and the state volume was preserved.
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
- Observed local base identity: `sha256:4c80ba98ca3601fd4735576d107e363bb74264f73c93517b4d30c9eff3644537`.
- Observed local Claude identity: `sha256:8502c46d31b77f9df008eec6ac2f701d90cc72df1327311a87d745ba1829de01`. Local Docker RepoDigests are recorded in `docker/images.lock.json`; these images have not been published to a remote registry.
- Provider state is only `aictrl-claude-state` → `/home/dev/.claude`; accepted provider-authentication exception is documented. No host agent, SSH, AWS, or Kubernetes directory was mounted.
- Auth-only CONNECT transport uses end-to-end TLS and explicit destination-only coverage; native login command restriction and actual network enforcement prevent an unenforced agent launch. Runtime services and `aictrl run` remain explicit nonfunctional stubs until their milestones.
- Every copied/adapted upstream file and its MIT notice is recorded in `OPEN_SOURCE.md` and `REUSE_DECISIONS.md`.

Known blockers:
- The headless container cannot complete the user's browser sign-in/consent and code-entry step. Native login was started in the verified state volume and reached the supported authorization flow. Complete `make claude-login` in an interactive host terminal using the user's account. The image and state mount are verified; authentication is not faked. This is the permitted T01 login exception and blocks a real subscription response in T03 until resolved.
- There are no remaining Python, dependency, image-build, Compose, or Docker-daemon blockers.

Next-milestone requirements:
- T02 must implement the host supervisor/lifecycle, actual enforcing runtime proxy, selected workspace permissions for UID 501, public CA export, and wall-clock enforcement. The prepared runtime entrypoint deliberately refuses to start an agent today.
- T03 must route native Anthropic streaming through the application gateway and establish policy/SQLite events. No model request or live agent qualification was attempted in T01.

Next milestone: T02 — launcher and isolation; begin only after explicit instruction.
