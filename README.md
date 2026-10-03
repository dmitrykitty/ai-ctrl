# AI Control Layer

T01 foundation, T02 isolation, T03 first native gateway path and T04 repeatable integration proof are complete. Real Claude Code 2.1.285 uses its existing subscription through a native Anthropic gateway, strict admission policy and durable SQLite events. The agent retains the verified Docker isolation. See [verification](NOTES.md) and the approved [plan](plan.md).

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

## Repeatable integration proof

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

The private gateway accepts POST `/anthropic/v1/messages` and `/anthropic/v1/messages/count_tokens`, forwarding to the corresponding paths on fixed `https://api.anthropic.com`. Queries, original body bytes, provider authorization, version/beta headers and relevant native client headers are preserved. Internal identity, caller Host and hop headers are stripped; outbound Host and length are generated correctly. SSE bytes, pings, event order, upstream statuses, errors and end-to-end response headers pass through incrementally. See the [native gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol).

`config/policy.yaml` is strict, versioned and defaults to BLOCK. Only an enabled declared agent with an explicitly allowed native operation is admitted. Missing/wrong/expired identity, unsupported routes, denied/disabled policy and invalid JSON cause no upstream action. Policy errors and admission-store failures fail closed. HTTPX uses one client per gateway, explicit limits/timeouts, no environment proxy inheritance, no POST retries and no redirect following.

The generic proxy excludes `api.anthropic.com` in gateway mode, including duplicate authentication declarations or test pins for that inference host. Declared authentication hosts remain available. It cannot provide an alternate inference tunnel. `EGRESS_ONLY` remains available by changing the trusted routing setting; that mode forwards native provider traffic through destination-only opaque CONNECT and has no application admission/audit.

Both modes retain default-deny agent networking. Only designated proxy/gateway TCP sockets and required TCP loopback/replies are allowed. Direct internet, host/sibling access, DNS, UDP/QUIC and IPv6 remain blocked. Gateway health is required before the workload starts; failure never selects another route.

## Durable events and trust boundary

Events live at `.aictrl/audit/events.sqlite3`, outside the workspace, provider state and ephemeral session directory. The directory is mode 0700, database mode 0600, and ignored by Git. SQLite uses WAL and synchronous FULL commits. The gateway commits ALLOW admission before sending a provider request, records durable BLOCK decisions, and adds an AUDIT completion/failure event with the same request ID. Shared event contracts remain schema 1.

Only safe attribution, operation/rule identifiers, decision, reason, policy version and timestamps are stored. Prompts, system/messages content, tool arguments, authorization headers, provider credentials and the internal token are never stored or logged by the control layer. Native provider state/history remains in its accepted dedicated volume. `aictrl events` displays these safe events.

The gateway runs non-root with all capabilities dropped, no-new-privileges and a read-only root filesystem. It joins internal and upstream networks with no published host port. Its three production mounts are read-only session identity, read-only policy and writable audit storage. It has no selected workspace, provider state, Docker socket or CA private key. The host writes a minimal mode-0400 session file; comparison is constant-time, rejects duplicate identity headers and checks expiry. Cleanup removes that file and session resources while preserving audit, workspace and provider state.

## Verification and limits

```bash
aictrl verify claude demo/project
make test-fast
make test
make verify-gateway-boundary
make compose-config
```

The T03 checkpoint and final offline suite each passed 127 tests. Focused actual Docker qualification passed 47 checks, including native messages/count_tokens, inference proxy denial, zero denied upstream/host hits, non-root/capability/resource boundaries, durable events after cleanup and gateway-unavailable startup refusal. It uses separate synthetic state and a test-only transport; the production upstream is fixed. One live subscription response was qualified separately. T04 adds 24 targeted orchestration tests; its final full offline suite passed 151 tests. Its one live proof reused unchanged images and security enforcement, so the T03 Docker matrix was not repeated. T02's prior signal/deadline/concurrency qualification remains recorded in `NOTES.md`; authentication helpers were unchanged.

Defaults remain 2 CPUs, 2048 MiB RAM, 256 PIDs and 600 seconds including preparation. `--timeout` only shortens the deadline. Host SIGINT/SIGTERM return 130/143, deadline 124, and ordinary exit is propagated. Cleanup preserves workspace and provider state.

Gateway admission buffers a bounded request body (16 MiB maximum); response streams are not buffered in full. Completion records transport completion, without interpreting SSE content or calculating model usage. Gateway overhead was not separately measured. Direct-provider auxiliary features may be denied by the inference-host restriction. Semantic/output guards, MCP authorization, budgets, dashboard and additional agents remain later milestones. T04 is complete; T05 is next and has not started.

Project-owned environment variables use `AICTRL_`. Bootstrap uses `AICTRL_BOOTSTRAP_MODE`, `AICTRL_PROXY_IP`, `AICTRL_GATEWAY_IP`, `AICTRL_ROUTING_MODE`, `AICTRL_UID` and `AICTRL_GID`; raw Compose also accepts `AICTRL_WORKSPACE` and `AICTRL_RUNTIME_DIR`. Use the normal launcher for validated per-session configuration. Run targeted tests during implementation; documentation edits do not require another test run.

See [architecture](ARCHITECTURE.md), [reuse decisions](REUSE_DECISIONS.md), [attribution](OPEN_SOURCE.md), [tasks](TASKS.md), and [verification](NOTES.md).
