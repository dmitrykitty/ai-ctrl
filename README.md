# AI Control Layer

T01–T05/T05H are complete. T06 adds shared secret/PII guards, bounded native output inspection, external TypeSafe Jev and authorized MCP tools/protected memory. Real Claude Code 2.1.285 and Codex CLI 0.159.3 retain native subscription forwarding and isolated provider state. The stateless demo uses the same Docker boundary with no provider credentials or LLM. Current qualification and limitations are in the [T06 report](docs/T06_REPORT.md), [verification notes](NOTES.md) and approved [plan](plan.md).

T06 is closed under the user's explicit acceptance of working Claude/Jev/MCP while deferring Codex. Claude's real exact-response test and the live Jev/MCP demo passed; 380 offline tests passed. Real Codex currently fails at output inspection with guard.output.invalid and does not complete the task. This regression remains deferred, with no automatic retry. T07 awaits the user's separate specification.

## Prepare and authenticate

Prerequisites: Docker with Compose, `make`, and an existing Python with pip. Bootstrap installs project-local uv 0.12.22 and Python 3.12.15. Dependencies are frozen in `uv.lock`.

```bash
make prepare
source .venv/bin/activate
aictrl doctor
make claude-auth-status
make claude-login
```

Preparation builds the native runtime, proxy and gateway images. `make runtime-image` reuses the installed T02 Claude binary and changes only bootstrap files; `make gateway-image` installs hash-locked dependencies in a digest-pinned Python image. Its temporary build context contains only source and public requirements. Actual local image identities and installer checksums are in `docker/images.lock.json`; qualification is Linux/amd64.

Authentication uses only `aictrl-claude-state` at `/home/dev/.claude`. The status helper mounts it read-only, drops capabilities and reports only authenticated/unauthenticated or a safe error. Login checks status first and exits successfully without a browser when already authenticated. Host Claude, SSH, AWS and Kubernetes state is never mounted. See [authentication instructions](docs/claude-authentication.md).

## Run Claude and view events

```bash
aictrl run claude demo/project
aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_GATEWAY_OK' --timeout 90
aictrl events --session <session-uuid>
```

The live print command returned exactly `AICTRL_GATEWAY_OK`, exit 0, through `APPLICATION_GATEWAY`. Admission and completion events identify the same real session and request. Pass another safe repository directory as the workspace; this control checkout's root and credential/control directories are rejected. Authentication is checked before infrastructure starts. Concurrent use of provider state is refused.

The native workspace-trust dialog remains enabled. After authentication preflight, bootstrap prepares only the native onboarding preference, without opening credential files or automatically trusting the workspace. Claude runs with the positive host UID/GID, empty capability sets and no-new-privileges. Workspace ownership and modes are preserved.

The agent mounts exactly the selected workspace, dedicated provider state and read-only public proxy CA. Policy, audit, host credentials, the Docker socket and CA private material remain outside the agent.

## Run Codex

These commands document the retained native setup. Its T05/T05H live proofs are historical; the current T06 output-inspection regression is unresolved and work on it is explicitly deferred. Use the qualified Claude path for current real-agent tasks.

```bash
make codex-image
make codex-version
make codex-auth-status
make codex-login
aictrl run codex demo/project
aictrl run codex demo/project --prompt 'Reply with exactly: AICTRL_CODEX_OK' --timeout 90
aictrl events --session <session-uuid>
```

The T05 live prompt command returned exactly `AICTRL_CODEX_OK`, exit 0, with a durable Responses ALLOW/completion pair after cleanup. The image downloads checksum-pinned official release binaries, including the required code-mode host and bubblewrap helper, on the existing trusted base. Qualification is Linux/amd64.

Native `codex login --device-auth` uses only `aictrl-codex-state` at `/home/dev/.codex` through a separate auth.openai.com-only login proxy. Complete the native device flow in your browser. Status runs in a fresh container with network disabled and the same volume read-only; it emits only a safe authentication result. Repeated login exits 0 when authenticated. Authentication survives runtime cleanup and container recreation. Host `~/.codex` and browser/SSH credentials are never mounted; no OpenAI Platform API key is used. Concurrent Codex/authentication use is refused; Claude has a separate volume and lease.

Codex selects the public `$CODEX_HOME/aictrl.config.toml` using `--profile aictrl`. Its provider uses `http://gateway:8000/codex`, native Responses HTTP/SSE, saved OpenAI authentication and `env_http_headers` for the ephemeral `X-AICtrl-Session` header. WebSockets and automatic transport retries are disabled. Project-level `.codex/config.toml` is not used for routing. These fields follow the checked [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

The gateway admits only POST `/codex/responses` and forwards to fixed `https://chatgpt.com/backend-api/codex/responses`. The user explicitly approved this native subscription backend after the T05-requested `https://api.openai.com/v1` returned 401. There is no fallback or caller-controlled upstream. Provider Authorization/account headers, original JSON/query and raw SSE pass through; internal identity is stripped. Both `api.openai.com` and `chatgpt.com` are excluded from generic proxy inference. Unsupported catalog/auxiliary routes stay denied; the pinned client can complete the smoke using its bundled model catalog.

Codex's image profile sets `sandbox_mode="danger-full-access"`, `approval_policy="never"` and `web_search="disabled"`. This avoids creating a second sandbox inside the already isolated AICTRL container; Docker filesystem isolation, non-root IDs, capability drop, NNP, firewall, limits and gateway remain the enforcement boundary. The settings are packaged only in the container profile. This follows the [official container guidance](https://learn.chatgpt.com/docs/agent-approvals-security).

The T05 real task read `demo/project/demo_codex.txt`, created `codex-test.txt` with the same content and returned `AICTRL_CODEX_TOOL_OK`. T06 now guards returned native tool content before the next model request, including Jev inspection of untrusted results. Native local tools still execute inside Docker; independent pre-execution authorization is provided for MCP operations. Codex prompt mode suppresses native stderr because it includes full input; final answers, exit status and safe events remain visible.

## Jev and the deterministic MCP demo

```bash
make demo-image
make verify-demo-boundary
make benchmark-guards
```

The Docker verifier explicitly injects an offline semantic fixture and a synthetic key to test protected mounts; it makes zero real Jev calls. Production uses only fixed `https://api.typesafe.ai/v1/systemone`, model `jev-latest`. To configure real semantic protection, set `AICTRL_JEV_API_KEY` in the host shell using silent input (Bash example):

```bash
read -rsp 'Jev API key: ' AICTRL_JEV_API_KEY
printf '\n'
export AICTRL_JEV_API_KEY
make verify-jev
.venv/bin/aictrl run demo-agent demo/project --timeout 90
```

Never put the key in the workspace, policy, tracked files, container environment or chat. The supervisor stages a 0400 key file in its private ephemeral directory and mounts it read-only into the gateway alone. Cleanup removes the staged file. `verify-jev` sends only two fixed synthetic examples and prints safe classifications/latency. No key means semantic-required operations fail closed; deterministic-only native requests still work, while the production demo reports PARTIAL with withheld results.

The official MCP SDK v2 client performs filtered discovery, safe lookup, a guessed forbidden tool/counter check, contact redaction, secret blocking, allowed project memory, guessed private-memory denial and poisoned-result withholding. Protected memory is synthetic and gateway-local. The forbidden backend only has a counter; it never deletes anything. No real LLM is needed for the attack sequence. `T06 DEMO PASS` requires the safe results to pass semantic checks and the poisoned result to be blocked. The report distinguishes offline fixture PASS from live Jev qualification.

Guards block stable secret signatures, redact EMAIL_ADDRESS/PHONE_NUMBER/CREDIT_CARD on input and block those entities on output. Jev receives only relevant untrusted text after deterministic privacy checks, with three probability questions in one request, default thresholds 0.85 and a 2.5-second deadline. This external service can receive residual unrecognized sensitive text; no local model or alternate semantic provider is used. Provider failures block.

## Repeatable Claude integration proof

```bash
aictrl verify claude demo/project
```

The command runs real Claude once and deterministic probes inside one managed agent container, using the production supervisor, adapter, gateway, policy, SQLite, firewall and proxy. It requires existing subscription authentication and APPLICATION_GATEWAY. It writes no probe file into the workspace and adds no mount or Docker image.

A successful result includes:

```text
AICTRL integration proof

Session: <managed-session-uuid>

[PASS] Real Claude response: AICTRL_T04_OK
[PASS] Application policy blocked forbidden GET request
[PASS] Direct internet bypass blocked by sandbox
[PASS] Inference CONNECT bypass denied by proxy
[PASS] ALLOW event persisted
[PASS] AUDIT completion correlated with ALLOW
[PASS] BLOCK persisted without an ALLOW/upstream event
[PASS] Events attributed to session <managed-session-uuid>
[PASS] Runtime cleanup complete
[PASS] Provider state, workspace and SQLite preserved
[PASS] Qualification workload exited successfully

T04 INTEGRATION PASS
```

The forbidden step sends GET `/anthropic/v1/messages` with valid internal identity and expects policy denial 403. The direct step uses a low-level TCP connection to `1.1.1.1:443`, ignoring proxy/gateway settings; an additional CONNECT to the inference host through the generic proxy must return 403. After cleanup, EventStore verifies correlated ALLOW/completion and the exact forbidden request's BLOCK in the same session, with no admission/upstream event for that blocked request.

Gateway decisions create durable SecurityEvents. Kernel-level rejected bypass is verified by the probe and does not receive an invented application event. Output contains safe results and the session UUID; native output, provider credentials, internal token, prompt and configuration are not dumped. Exit 0 means complete proof, 1 means a failed check, and 2 means invalid input or unavailable prerequisites. The live T04 proof passed once; its session/events are recorded in NOTES.md.

## Routing and admission

`config/project.yaml` selects `APPLICATION_GATEWAY`. Claude receives `ANTHROPIC_BASE_URL=http://gateway:8000/anthropic`, a supervisor-generated `X-AICtrl-Session` header, proxy settings and `NO_PROXY` for the gateway. No gateway API key, auth-token variable or apiKeyHelper is added, so saved subscription authentication remains native. This behavior was checked against [Claude gateway documentation](https://code.claude.com/docs/en/llm-gateway).

The private gateway accepts POST `/anthropic/v1/messages` and `/anthropic/v1/messages/count_tokens`, forwarding to fixed `https://api.anthropic.com`. Queries, safe original body bytes, provider authorization, version/beta and relevant native headers are preserved; an actual PII redaction rewrites selected JSON strings. Internal identity, caller Host and hop headers are stripped. Safe SSE units retain their original bytes/pings/order after inspection. See the [native gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol).

`config/policy.yaml` uses configuration schema 3/version `t06` and defaults to BLOCK. Enabled agents have exact channel/direction/protocol/target/operation rules; matching BLOCK wins regardless of order. Unknown fields/enums, empty operations, wildcard identifiers and duplicate IDs are rejected. Schemas 1/2 require explicit migration; shared contracts remain unchanged schema 1. Missing/wrong/duplicate/expired identity, unsupported routes, denied policy and invalid JSON cause no upstream action. Policy, guards and admission-store failures fail closed. Provider and Jev clients have explicit timeouts, no environment proxy inheritance, retries or redirects. Internal `/mcp` uses the same identity, policy, GuardEngine and durable EventSink.

The generic proxy excludes each adapter's inference hosts in gateway mode, including duplicate authentication declarations or test pins. These are `api.anthropic.com` for Claude and `api.openai.com`/`chatgpt.com` for Codex. Declared authentication hosts remain available. `EGRESS_ONLY` remains an explicit trusted Claude alternative with destination-only opaque CONNECT and no application admission/audit; the Codex launcher requires `APPLICATION_GATEWAY`.

Both modes retain default-deny agent networking. Only designated proxy/gateway TCP sockets and required TCP loopback/replies are allowed. Direct internet, host/sibling access, DNS, UDP/QUIC and IPv6 remain blocked. Gateway health is required before the workload starts; failure never selects another route.

## Durable events and trust boundary

Events live at `.aictrl/audit/events.sqlite3`, outside the workspace, provider state and ephemeral session directory. The directory is mode 0700, database mode 0600, and ignored by Git. SQLite uses WAL and synchronous FULL commits. The gateway commits ALLOW admission before sending a provider request, records durable BLOCK decisions, and adds an AUDIT completion/failure event with the same request ID. Shared event contracts remain schema 1.

Only safe attribution, operation/rule identifiers, decision, reason, policy version and timestamps are stored. Prompts, system/messages content, tool arguments, authorization headers, provider credentials and the internal token are never stored or logged by the control layer. Native provider state/history remains in its accepted dedicated volume. `aictrl events` displays these safe events.

The gateway runs non-root with all capabilities dropped, no-new-privileges and a read-only root filesystem. It joins internal and upstream networks with no published host port. It mounts read-only session/policy and writable audit, plus the optional gateway-only read-only Jev key file. It has no workspace, provider state, socket or CA private key. The mode-0400 identity file is compared in constant time with duplicate/expiry checks. Cleanup removes ephemeral identity/key and resources while preserving audit, workspace and native provider state. The stateless demo mounts no provider volume and obtains no provider lease.

## Verification and limits

```bash
aictrl verify claude demo/project
make test-fast
make test
make verify-gateway-boundary
make verify-codex-boundary
make verify-demo-boundary
make verify-jev
make benchmark-guards
.venv/bin/python scripts/verify-codex-boundary.py --leases-only
make compose-config
```

The T03 checkpoint and final offline suite each passed 127 tests. Focused actual Docker qualification passed 47 checks, including native messages/count_tokens, inference proxy denial, zero denied upstream/host hits, non-root/capability/resource boundaries, durable events after cleanup and gateway-unavailable startup refusal. It uses separate synthetic state and a test-only transport; the production upstream is fixed. One live subscription response was qualified separately. T04 adds 24 targeted orchestration tests; its final full offline suite passed 151 tests. Its one live proof reused unchanged images and security enforcement, so the T03 Docker matrix was not repeated. T02's prior signal/deadline/concurrency qualification remains recorded in `NOTES.md`; authentication helpers were unchanged.

T05's one final offline suite passed 194 tests. Focused Codex Docker qualification passed 42 checks, including the actual pinned client/custom profile against a synthetic Responses backend, unchanged isolation, raw SSE/function-call/follow-up forwarding, both inference proxy denials, durable events and cleanup. Six actual independent-provider lease checks passed. One live Claude regression passed because the shared runtime/gateway changed. The unchanged Claude/proxy images and historical full boundary matrices were reused. Codex native authentication persistence and idempotent login were verified without reading credentials.

The subsequent T05 profile cleanup passed 13 targeted adapter/profile tests and 20 checks in one real local-tool session. It rebuilt only the Codex image; full offline and historical Docker matrices were not repeated for this small configuration change. The read/create-file/follow-up task now passes under the unchanged external boundary.

T05H passed 227 offline tests, 47 Claude gateway Docker checks, 42 Codex checks and six provider leases, plus one real smoke per provider. T06 results are recorded separately in the [milestone report](docs/T06_REPORT.md), including the external-provider prerequisites and any pending proof.

Defaults remain 2 CPUs, 2048 MiB RAM, 256 PIDs and 600 seconds including preparation. `--timeout` only shortens the deadline. Host SIGINT/SIGTERM return 130/143, deadline 124, and ordinary exit is propagated. Cleanup preserves workspace and provider state.

Gateway admission buffers at most 16 MiB in RAM. Output waits for an Anthropic content block or Responses item, including complete tool arguments; interleaved items form an ordered group. Each unit/group is limited to 1 MiB and 30 seconds. Deterministic checks catch split secrets/PII before releasing that unit. Unsafe, malformed, compressed, oversized or incomplete output is withheld and audited as blocked; native terminal evidence is required for SSE completion. Earlier safe units cannot be recalled. Coverage is text and decoded JSON, not arbitrary encoded/binary/image content or values split across independently completed units. Usage accounting, approvals, budgets, reload, risk response and dashboard remain later work. Stop before T07.

## Historical T05H gateway benchmark

```bash
make benchmark-gateway
```

This uses a deterministic local HTTP/SSE upstream with no provider or model traffic. It measures direct HTTP, complete gateway admission/stream/completion, policy decisions and durable SQLite appends at concurrency 1/10/50. Results include failures, p50/p95/p99 and successful requests/s and are saved to `.aictrl/benchmarks/latest.json`. Tests check correctness without timing thresholds.

On the qualified Python 3.12.15/i7-10750H Linux host, 500 requests per sample produced gateway p50/p95/p99 of 10.492/11.707/13.553 ms at concurrency 1; direct HTTP was 2.029/3.005/3.354 ms. Gateway throughput was 94.263, 175.534 and 93.524 requests/s at 1/10/50, with zero failures in the final run. Durable append p50 was 2.461 ms versus policy 5.496 µs. Higher concurrency has substantial local scheduling/storage tails; these are synthetic application-layer measurements, not provider or enterprise capacity claims. Full results and limitations are in [architecture](ARCHITECTURE.md) and [notes](NOTES.md).

These gateway numbers predate T06 guards. `make benchmark-guards` separately measured combined deterministic p50 of 0.379/3.228/10.285 ms for 1/10/32 KiB, with 200 samples per cohort. Fake-semantic timing is labelled separately and excludes external latency. See the T06 report for all percentiles and limitations.

The current deployment keeps one agent/gateway/proxy/private network per session, a local Docker supervisor, SQLite and one lease per provider-state identity. Shared gateways, distributed identity and external event backends are future deployment work; current code boundaries prepare that work without implementing it.

Project-owned environment variables use `AICTRL_`. Bootstrap uses `AICTRL_BOOTSTRAP_MODE`, `AICTRL_PROXY_IP`, `AICTRL_GATEWAY_IP`, `AICTRL_ROUTING_MODE`, `AICTRL_UID` and `AICTRL_GID`; raw Compose also accepts `AICTRL_WORKSPACE` and `AICTRL_RUNTIME_DIR`. Use the normal launcher for validated per-session configuration. Run targeted tests during implementation; documentation edits do not require another test run.

See [architecture](ARCHITECTURE.md), [reuse decisions](REUSE_DECISIONS.md), [attribution](OPEN_SOURCE.md), [tasks](TASKS.md), and [verification](NOTES.md).
