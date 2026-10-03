# Reuse decisions

Approved source: [mattolson/agent-sandbox](https://github.com/mattolson/agent-sandbox), commit `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04`, MIT.

Reuse only necessary agent image, official Claude installer, proxy CA/bootstrap, firewall, workspace, and named provider-state assets. Inspect source before adaptation; record each copied or adapted file in `OPEN_SOURCE.md`. Do not import unrelated upstream services or accept broad Docker-subnet firewall access.

Use FastAPI/Python, Pydantic, HTTPX, PyYAML, Typer, uvicorn, pytest, and standard-library SQLite for the foundation. Defer LiteLLM, Presidio, MCP, and mitmproxy integration to their actual milestones. Do not add Redis, React, Kafka, OPA, or a second service framework.

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
