# Reuse decisions

Approved source: [mattolson/agent-sandbox](https://github.com/mattolson/agent-sandbox), commit `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04`, MIT.

Reuse only necessary agent image, official Claude installer, proxy CA/bootstrap, firewall, workspace, and named provider-state assets. Inspect source before adaptation; record each copied or adapted file in `OPEN_SOURCE.md`. Do not import unrelated upstream services or accept broad Docker-subnet firewall access.

Use FastAPI/Python, Pydantic, HTTPX, PyYAML, Typer, uvicorn, pytest, and standard-library SQLite for the foundation. mitmproxy is integrated in T02; defer LiteLLM, Presidio and MCP to their designated milestones. Do not add Redis, React, Kafka, OPA, or a second service framework.

## T01 decisions

- Adapt the upstream base/Claude Dockerfiles, firewall, bootstrap, public CA installer, Compose topology, and named Claude state mount. The complete per-file record is in `OPEN_SOURCE.md`.
- Use the official Python 3.12.15 slim-bookworm image at a resolved immutable digest. Reproduce apt resolution using the signed Debian and Debian-security snapshot `20261002T000000Z`. Keep Git, curl, ripgrep, native CLI libraries, and trusted firewall/privilege-drop tools; omit upstream IDE/shell customization, GitHub credential shims, additional agents, language stacks, and custom Git/yq/gh builds that T01 does not require.
- Preserve upstream UID/GID 501 and `/home/dev`; the next launcher milestone must resolve workspace write permissions without keeping the agent privileged.
- Install Claude Code 2.1.285 using Anthropic's native installer, as upstream does. Checksum the downloaded installer, replace its one mutable `latest` bootstrap lookup with the exact requested target, and verify the installed binary against Anthropic's manifest. This version pin is the only installer adaptation; it is not a new installation or OAuth implementation. Promote the installed executable to root-owned `/usr/local/lib/aictrl/claude` with `/usr/local/bin/claude` as its launcher, keeping trusted bootstrap PATH free of agent-writable directories. Both amd64 and arm64 checksums are recorded; actual build qualification is on linux/amd64.
- Remove the upstream subnet-wide network permission and Docker DNS access. Prepared firewall assets permit only a designated proxy TCP socket (and, in the future runtime mode, a designated gateway TCP socket). The T01 runtime entrypoint rejects startup. Native authentication runs only after real firewall setup and drops UID, GID, supplementary groups, and all capability sets before executing the CLI.
- Prepare a dedicated provider-only CONNECT transport for native authentication using standard-library Python. This T01 helper does not replace the planned mitmproxy runtime. It admits exact authentication destinations on port 443, refuses private-address DNS results, connects to checked numeric addresses, and never logs TLS contents or authentication headers. Restrict bootstrap to `claude auth login --claudeai`, no workspace, and ten minutes. Document destination-only TLS coverage explicitly.
- Keep credentials and native provider history only in `aictrl-claude-state`; never copy host agent state or enterprise credentials. The public CA installer rejects private-key material; runtime CA generation/export belongs to T02.
- Use uv 0.12.22, Python 3.12.15, a committed hash-bearing `uv.lock`, and a pinned hatchling build backend. SQLite remains standard-library only. No custom OAuth bridge, model request, Codex integration, launcher, gateway, policy engine, or audit store is implemented in T01.

Version pins and observed image identities are in `docker/images.lock.json`. Authentication completion is recorded separately from image/version and volume verification.

## T02 decisions

- Adapt approved upstream proxy Dockerfile, CA export entrypoint and enforcement-hook pattern, retaining MIT notices. Pin the official mitmproxy image by digest; observed version is 12.2.3. Keep exact HTTP/CONNECT/server-connect destination admission and forwarding; omit upstream credential injection, dynamic reload, central policy and content inspection. References: [events](https://docs.mitmproxy.org/stable/api/events.html), [CA files](https://docs.mitmproxy.org/stable/concepts/certificates/), [options](https://docs.mitmproxy.org/stable/concepts/options/).
- Reuse the existing firewall and Compose approach with unique host-rendered sessions. Runtime proxy has a private CA volume and a separate public export. Agent networking permits only exact infrastructure TCP destinations and fails closed. Authentication keeps its distinct restricted transport.
- Adapt bootstrap to positive host UID/GID, no-follow provider-state preparation and complete native capability drop. Avoid usermod home traversal and preserve workspace ownership. Setup-only DAC_OVERRIDE handles state ownership, and KILL supports trusted init signal forwarding.
- Implement host supervisor, static destination validation, workspace validation and deterministic probes as new project code. No additional host service framework or runtime Python dependency was added; mitmproxy dependencies stay in its Docker image.
- Native UI preference preparation is new code, edits only provider-volume configuration, opens no credential file, and preserves workspace trust. The observed onboarding/login mismatch is also described in the [upstream issue](https://github.com/anthropics/claude-code/issues/67149).
- EGRESS_ONLY is transitional destination-level HTTPS enforcement. APPLICATION_GATEWAY remains a future adapter capability. Shared serialized contract schema stays 1; demo-agent remains a fixture.
