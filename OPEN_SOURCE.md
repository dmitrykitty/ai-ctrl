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
| `images/base/entrypoint.sh` | `docker/base/entrypoint.sh` | Restrict native login command, reject T01 runtime, require real firewall, hardcoded state permissions, drop all IDs/capabilities; omit sudo/dotfile/skill hooks | No unenforced launch and no privileged agent process |
| `images/base/install-proxy-ca.sh` | `docker/base/install-proxy-ca.sh` | Hardcoded public-only AICtrl CA path; reject private keys; validate certificate | Prepare public CA trust without leaking proxy private key |
| `internal/embeddata/templates/compose/base.yml` | `docker/compose.yaml`, `docker/compose.auth.yaml` | Internal-only agent network, explicit service IPs, controlled host entries, resource limits, no host secrets/runtime-shim mounts; split authentication profile | Shared topology and fail-closed skeleton plus isolated native login |
| `internal/embeddata/templates/claude/cli/agent.yml` | `docker/compose.yaml`, `docker/compose.auth.yaml` | Rename state volume to `aictrl-claude-state`; retain `/home/dev/.claude`; omit separate shell history | Persist only dedicated provider state; no host agent-directory mount |

Anthropic's [official native installer](https://claude.ai/install.sh) and [Claude release manifest](https://downloads.claude.ai/claude-code-releases/2.1.285/manifest.json) are fetched during the build. The installer content is checksum-pinned; the single `latest` bootstrap lookup is replaced with its exact target version after verification. This is recorded in `docker/images.lock.json`. Claude Code and Anthropic's installer are vendor-distributed software and are not relicensed under the upstream MIT license. Anthropic account/product terms continue to apply.

`docker/auth-proxy.py` and the Python control-layer modules are new project code, rather than copied upstream proxy/gateway implementations. The authentication host choices were checked against the official network documentation; see `docs/claude-authentication.md`.

Direct Python dependencies are locked in `uv.lock`: FastAPI 0.142.2 (MIT), uvicorn 0.54.0 (BSD-3-Clause), Pydantic 2.13.5 (MIT), PyYAML 6.0.3 (MIT), HTTPX 0.28.1 (BSD-3-Clause), Typer 0.27.2 (MIT), and pytest 9.1.1 (MIT). uv 0.12.22 is MIT/Apache-2.0; hatchling 1.27.0 is MIT. Their original installed distribution notices remain intact. Python and Debian package notices remain in the base image.
