# Open-source attribution

Runtime asset source: [mattolson/agent-sandbox](https://github.com/mattolson/agent-sandbox/tree/c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04).

Pinned revision: `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04`. License: MIT. Preserve the original license and copyright notice with copied/adapted assets.

The upstream MIT notice is retained verbatim in `docker/LICENSE.agent-sandbox`, in the base build context at `docker/base/LICENSE.agent-sandbox`, and in the built image at `/usr/local/share/licenses/agent-sandbox/LICENSE`. Adapted files carry source/license comments. The repository and revision above apply to every row below; every upstream asset in this table is MIT, Copyright (c) 2026 Matt Olson.

| Original path | Local path | Modification | Reason |
|---|---|---|---|
| `LICENSE` | `docker/LICENSE.agent-sandbox`, `docker/base/LICENSE.agent-sandbox` | Verbatim copies; embedded in image | Preserve original MIT copyright and terms in source and distribution |
| `images/base/Dockerfile` | `docker/base/Dockerfile` | Digest-pinned Python 3.12/Debian base and dated apt snapshot; retain dev/workspace and firewall/CA tools; omit unrelated IDE, stacks, shell customizations, credential shims, sudo, and custom Git/yq/gh builds | Minimal reproducible T01 agent base; trusted setup then irrevocable privilege drop |
| `images/agents/claude/Dockerfile` | `docker/claude/Dockerfile` | Pin official native installer and CLI; verify checksums; promote binary to root-owned path; disable updates/nonessential traffic/connectors; reset to trusted root bootstrap | Prepare actual Claude Code with stable binary and controlled startup, without agent-writable bootstrap PATH |
| `images/base/init-firewall.sh` | `docker/base/init-firewall.sh` | Default deny before flushing; exact proxy/gateway TCP destinations; remove subnet allowance/DNS restoration; IPv6 deny; real proxy reachability prerequisite | Preserve and tighten isolation, avoid host/sibling/DNS/UDP bypasses |
| `images/base/entrypoint.sh` | `docker/base/entrypoint.sh` | Restrict native login command, require real firewall/public CA, prepare only container home/state with no-follow ownership changes, select host-compatible runtime IDs, and drop all native capabilities; omit sudo/dotfile/skill hooks | No unenforced launch and no privileged agent process |
| `images/base/install-proxy-ca.sh` | `docker/base/install-proxy-ca.sh` | Hardcoded public-only AICtrl CA path; reject private keys; validate certificate | Prepare public CA trust without leaking proxy private key |
| `internal/embeddata/templates/compose/base.yml` | `docker/compose.yaml`, `docker/compose.auth.yaml` | Internal-only agent network, explicit service IPs, controlled host entries, resource limits, no host secrets/runtime-shim mounts; split authentication profile | Managed isolated runtime topology plus separate restricted native login |
| `internal/embeddata/templates/claude/cli/agent.yml` | `docker/compose.yaml`, `docker/compose.auth.yaml` | Rename state volume to `aictrl-claude-state`; retain `/home/dev/.claude`; omit separate shell history | Persist only dedicated provider state; no host agent-directory mount |

Anthropic's [official native installer](https://claude.ai/install.sh) and [Claude release manifest](https://downloads.claude.ai/claude-code-releases/2.1.285/manifest.json) are fetched during the build. The installer content is checksum-pinned; the single `latest` bootstrap lookup is replaced with its exact target version after verification. This is recorded in `docker/images.lock.json`. Claude Code and Anthropic's installer are vendor-distributed software and are not relicensed under the upstream MIT license. Anthropic account/product terms continue to apply.

`docker/auth-proxy.py` and the Python control-layer modules are new project code, rather than copied upstream proxy/gateway implementations. The authentication host choices were checked against the official network documentation; see `docs/claude-authentication.md`.

Direct Python dependencies are locked in `uv.lock`: FastAPI 0.142.2 (MIT), uvicorn 0.54.0 (BSD-3-Clause), Pydantic 2.13.5 (MIT), PyYAML 6.0.3 (MIT), HTTPX 0.28.1 (BSD-3-Clause), Typer 0.27.2 (MIT), and pytest 9.1.1 (MIT). uv 0.12.22 is MIT/Apache-2.0; hatchling 1.27.0 is MIT. Their original installed distribution notices remain intact. Python and Debian package notices remain in the base image.

## T02 proxy adaptations

The same approved revision and MIT copyright apply below. The verbatim license is also retained in `docker/proxy/LICENSE.agent-sandbox` and embedded in the proxy image at `/usr/local/share/licenses/agent-sandbox/LICENSE`.

| Original path | Local path | Modification | Reason |
|---|---|---|---|
| `images/proxy/Dockerfile` | `docker/proxy/Dockerfile` | Digest-pinned mitmproxy base, minimal addon files, non-root user, private/public CA directories, retained license | Reuse runtime proxy packaging with separate CA exposure |
| `images/proxy/entrypoint.sh` | `docker/proxy/entrypoint.sh` | Generate CA with mitmproxy API; export public certificate only; static destination file; quiet regular proxy and opaque CONNECT | Prepare trust safely and state actual HTTPS coverage |
| `images/proxy/addons/enforcer.py` | `docker/proxy/enforcer.py` | Retain HTTP/CONNECT/server-connect admission pattern and streaming responses; omit credential injection, reload, full policy and content logging | Minimal enforcing runtime egress without later-milestone scope |

`docker/proxy/destinations.py`, `docker/base/prepare-claude-ui.py`, host supervisor/rendering/validation and runtime probes are new project code. mitmproxy 12.2.3 is distributed under its original MIT license and installed dependency notices in the official image; its base digest and actual image identity are in `docker/images.lock.json`. Claude vendor software retains its own terms.

## T03 native gateway and readiness

The gateway, policy and reporting modules, session identity handling, image scripts and synthetic qualification are new project code. They reuse the already-locked FastAPI, uvicorn, Pydantic, HTTPX and PyYAML distributions and Python's standard-library SQLite; no additional dependency or protocol framework is introduced. Original installed notices remain in the digest-pinned Python gateway image.

The MIT attribution above continues to cover adapted `docker/base/entrypoint.sh`, `docker/base/init-firewall.sh` and the Compose topology. T03 adds exact gateway readiness and host-rendered service configuration while retaining default deny, complete agent capability drop and provider-state isolation. `docker/base/Dockerfile.runtime` adds only those changed bootstrap files to the existing native Claude image, retaining inherited upstream MIT notices and vendor terms. The proxy image and authentication implementation are unchanged.

Protocol behavior was checked against Anthropic's current [gateway configuration](https://code.claude.com/docs/en/llm-gateway) and [native gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol). These are documentation references; their gateway implementation was not copied. Live subscription qualification and actual resulting image identities are recorded in NOTES.md and docker/images.lock.json.
