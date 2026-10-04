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

## T05 Codex image and shared runtime

`docker/codex/Dockerfile` is new project packaging on the existing digest-qualified agent-sandbox-derived base. It uses the same official release-binary installation approach inspected in upstream `images/agents/codex/Dockerfile`; no host executable is copied. The inherited agent-sandbox MIT notice remains in the image. Bootstrap and Compose changes below adapt the already attributed files, preserving their original license.

| Source | Local asset | Modification and attribution |
|---|---|---|
| [OpenAI Codex rust-v0.159.3 release](https://github.com/openai/codex/releases/tag/rust-v0.159.3) | `/usr/local/bin/codex`, `/usr/local/bin/codex-code-mode-host` in Codex image | Official Linux/amd64 musl binaries; verify release-published SHA-256, install root-owned 0755, pin same version |
| [Codex LICENSE at rust-v0.159.3](https://github.com/openai/codex/blob/rust-v0.159.3/LICENSE) | `docker/codex/LICENSE.openai-codex` | Verbatim Apache-2.0 notice embedded at `/usr/local/share/licenses/openai-codex/LICENSE`; applies to the Codex CLI and code-mode host |
| Official Codex release bubblewrap helper; [vendored source](https://github.com/openai/codex/tree/rust-v0.159.3/codex-rs/vendor/bubblewrap) | `/usr/local/bin/bwrap`, `docker/codex/COPYING.bubblewrap`, `docker/codex/LICENSE.bubblewrap` | Verify pinned release digest; retain upstream COPYING (GNU Library GPL version 2) and LICENSE symlink target text in `/usr/local/share/licenses/bubblewrap/` |
| Previously attributed agent-sandbox bootstrap/topology | `docker/base/entrypoint.sh`, `docker/compose.codex-auth.yaml`, host-rendered Codex runtime | Select only the exact dedicated Codex state path and restricted native device-auth command; retain MIT attribution, default deny and complete agent capability drop |

The public profile preparer, CodexAdapter, native status wrapper, shared-runtime selection, Responses handler, bounded terminal-frame observer and deterministic/live diagnostics are new project code. Existing FastAPI/HTTPX/Pydantic/PyYAML/SQLite dependencies and serialized contracts are reused unchanged. The auth proxy extends the existing exact-host design to auth.openai.com; no third-party OAuth implementation or native credential parser is added.

The subsequent T05 cleanup changes only the project-owned public profile to use AICTRL's outer container boundary instead of Codex's nested sandbox, with approval never and web search disabled. Official binaries, source pins and license notices are unchanged; no new upstream code or dependency is introduced.

Version, source URLs, SHA-256 pins, license checksums and final locally built image identities are recorded in `docker/images.lock.json`. The proxy, base and Claude images were reused without rebuilding. Official configuration references were checked at implementation time; saved subscription forwarding to the fixed native ChatGPT backend was explicitly approved and actually qualified, as recorded in NOTES.md.

## T05H architecture checkpoint

The trusted runtime/protocol registries, independent native handlers, common ControlPipeline, policy schema 2 rules, EventSink contract, synthetic extension tests and local HTTP benchmark are new project code. They reuse the existing locked Python dependencies and standard-library SQLite; no plugin framework, ORM, distributed backend, judge or additional dependency was imported. Agent/native auth/bootstrap binaries and license notices are unchanged.

`docker/compose.yaml` remains an adaptation of the attributed MIT agent-sandbox topology. T05H changes only the logical provider-state key to a generic external volume rendered from trusted adapter metadata; actual provider paths, private topology, privileges, limits and mount isolation are preserved. The changed gateway source was repackaged in the existing digest-pinned gateway image with hash-locked dependencies. Base, Claude, Codex and proxy images were reused; their upstream notices remain intact.

## T06 SDK, recognizers and stateless packaging

| Distribution / source | Exact version | License | Use |
|---|---|---|---|
| [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | `mcp==2.3.0`, `mcp-types==2.3.0` | MIT | Native low-level server and official Streamable HTTP client; transport/protocol implementation is reused, not hand-rolled |
| [Presidio analyzer](https://github.com/data-privacy-stack/presidio) | `presidio-analyzer==2.2.364` | MIT | Selected email pattern, phone and Luhn card recognizers; no NLP engine or downloaded model |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | `jsonschema==4.26.0` | MIT | Trusted tool argument-schema validation before dispatch |
| [HTTPX2](https://github.com/pydantic/httpx2) | `httpx2==2.13.1` | BSD-3-Clause | Official MCP v2 transport dependency; existing HTTPX remains the native LLM/Jev client |
| [python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) | `phonenumbers==9.0.40` | Apache-2.0 | Presidio phone recognizer dependency |
| [spaCy](https://github.com/explosion/spaCy) | `spacy==3.8.16` | MIT | Analyzer package's transitive library dependency only; no language model downloaded/instantiated |

Direct dependency pins and all hashed transitive versions are in `pyproject.toml`/`uv.lock`. Installed distribution license notices remain in the gateway image. The demo installs only the frozen `demo` dependency group's MCP client closure, preserving its installed notices and the inherited agent-sandbox MIT license. No Presidio/NLP package is installed in the demo image. License/version statements were checked against installed distribution metadata.

The new guard engine, Jev HTTP client, provenance extraction, bounded native output buffering, MCP control/backend/memory, stateless adapter/client and qualification/benchmark scripts are project code. The [TypeSafe OpenAPI schema](https://api.typesafe.ai/openapi.json) and [API documentation](https://docs.typesafe.ai/introduction) are protocol references; no vendor implementation or local model was copied. External TypeSafe service access is subject to its service terms, separate from dependency licenses.

The already attributed `docker/base/entrypoint.sh` gains only an explicit runtime-only stateless demo path; `docker/demo/Dockerfile` copies the existing qualified firewall/readiness script onto the digest-pinned base. Native images are reused. `docker/proxy/destinations.py` is project code and now accepts an empty allowlist as deny-all without DNS. Its changed image retains the proxy/base MIT notices; no egress exception was added. Gateway, demo and this narrowly changed proxy were rebuilt; base/Claude/Codex binaries and license pins were preserved.

## T08 local dashboard

Jinja2 3.1.6 (BSD-3-Clause) is pinned directly for the local server-rendered dashboard; it was already in the locked dependency closure. MarkupSafe remains its existing BSD-3-Clause dependency. Installed distribution notices are retained in the frozen environment/image. CSS, vanilla JavaScript, SVG icons, reporting/risk/response logic and host-only demo orchestration are new project code; no external font/chart/React/Node assets were copied. Existing MIT agent-sandbox attribution/pin, native binaries and provider terms are unchanged.

## T09 verification and preparation

The offline judge, preflight, scoped reset and safe privacy/cleanup scripts are project code using the standard library and existing locked packages. The deterministic rehearsal reuses the official pinned MCP SDK clients, the attributed Docker boundary and production SQLite/policy/governance; its semantic fixture is explicitly labelled and remains outside the production factory. No new dependency, downloaded UI asset, native agent binary or copied third-party code is introduced.
