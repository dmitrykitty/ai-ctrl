# Implementation notes

T03 STATUS: PASS. T01, T02 and T03 are COMPLETE. Stop here; T04 has not started. The active configuration is APPLICATION_GATEWAY with native Anthropic forwarding, minimal strict admission and durable safe events. `plan.md` and shared serialized contracts remain unchanged (schema 1).

## T03 verified on 2026-10-03

- One live qualification: `.venv/bin/aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_GATEWAY_OK' --timeout 90` returned exactly `AICTRL_GATEWAY_OK`, exit 0, with existing saved subscription authentication. No new login flow, gateway API credential or custom OAuth implementation was introduced.
- Real session `562bd3ba-6017-4072-bf6c-fb5100286961`, request `3747fdce-e39d-440e-9412-aed99ec25eb9`: SQLite contains ALLOW / `llm.policy.allowed` then AUDIT / `llm.upstream_completed`, both LLM, OUTBOUND, ANTHROPIC_MESSAGES, STRUCTURED, claude, policy t03. Admission was at 17:21:08.882295 UTC; completion at 17:21:10.746017 UTC. The interval includes the provider and streaming; gateway overhead was not separately measured.
- `aictrl events --session 562bd3ba-6017-4072-bf6c-fb5100286961` displayed the two safe attributable events after cleanup. No session-labelled container, network or CA volume remained after live/Docker qualification.
- Targeted gateway/policy/store/runtime tests passed. One `make test-fast` checkpoint: 127 passed in 0.87 seconds. One final `make test`: 127 passed in 0.81 seconds. No test rerun followed documentation edits.
- `make verify-gateway-boundary` passed 47 actual Docker checks: native messages and count_tokens with exact queries, raw SSE/ping order, invalid session/unsupported route blocking, generic inference CONNECT and HTTP denial, no direct/DNS/UDP/IPv6/host/sibling bypass, host UID/GID, empty capability sets, NNP, resource limits, public-only CA, absent host credentials/socket, workspace writes and provider state preservation.
- The same focused qualification confirmed gateway non-root/readonly/capability drop, absent workspace/provider-state/CA mounts, two durable ALLOW/completion pairs plus two BLOCK events after cleanup, no prompt/provider credential in SQLite, exactly four allowed synthetic upstream hits and zero denied/host hits. A stopped gateway prevented the workload marker from being created; host deadline returned 124 and cleanup preserved prior audit/state.
- Unit tests prove admission is visible from a fresh SQLite connection before upstream is called; missing/wrong/expired/duplicate identity fails closed; disabled/denied/default/invalid policy blocks; actual SQLite write errors prevent upstream. Raw request body/queries and future Anthropic/version/beta/auth headers are preserved, internal/hop headers are removed, statuses/errors/rate-limit headers survive, POST is not retried, and the first SSE chunk arrives before upstream EOF. Stream and final-audit failures have safe handling.
- count_tokens is qualified in native routing/header/body/query unit tests and real Docker with a synthetic native backend. The live provider qualification exercised messages; no separate paid count_tokens request was made.

## T03 implementation and security decisions

Current official [Claude gateway configuration](https://code.claude.com/docs/en/llm-gateway) and [native protocol](https://code.claude.com/docs/en/llm-gateway-protocol) were verified before forwarding code. Saved subscription auth remains native when a base URL is supplied without gateway credentials. Version/beta/auth and relevant client headers are forwarded; `X-AICtrl-Session` is control-plane identity only and never reaches the provider.

Runtime generates `secrets.token_urlsafe(48)` per session and stores it in existing excluded SecretStr identity. Minimal trusted session data is mounted read-only from a mode-0400 ephemeral file; equality is constant-time and expiry/duplicate headers are checked. Claude receives the internal header through its adapter. The gateway receives no workspace, provider state, Docker socket or private CA. Its production mounts are readonly session, readonly policy and persistent audit. It runs at host UID/GID with ALL capabilities dropped, NNP, readonly root, bounded tmpfs and internal/upstream networks, without host ports.

Strict `config/policy.yaml` defaults to BLOCK and permits only declared enabled native Anthropic operations. Gateway supports POST messages/count_tokens with fixed HTTPS Anthropic origin, unchanged body/query bytes and incremental raw response streaming. Request bodies are limited to 16 MiB and validated only in memory. HTTPX is lifecycle-owned, environment-independent, explicitly timed/limited, without POST retries or redirect following. Semantic/output filtering and model usage extraction are deferred.

`.aictrl/audit/events.sqlite3` is host-persistent, outside workspace/provider state/session cleanup and ignored by Git. Mode 0700 directory / 0600 database, WAL, synchronous FULL, 14-column events plus schema-1 SecurityEvent JSON and session index. Admission commits before upstream; audit/policy failure prevents an upstream action. BLOCK is durable; completion/failure is correlated AUDIT. Completion persistence failure logs safe IDs only because delivered bytes cannot be recalled. Prompts, system/messages content, tool arguments, provider credentials, auth headers and internal tokens are absent from audit/control logs. Native accepted provider state/history is preserved.

In APPLICATION_GATEWAY, inference-host entries are removed from the generic proxy across all purposes, including duplicate auth declarations; inference-host test pins are refused. Only declared authentication/auxiliary destinations remain. EGRESS_ONLY is still supported by explicit trusted config and retains destination-only opaque CONNECT. The existing authentication helper and boundary were unchanged, so authentication-only Docker probes were not repeated. Focused T03 qualification reuses the affected runtime checks once in gateway mode; the full T02 lifecycle matrix was not rerun.

Gateway service creation, Compose health wait and exact bootstrap health readiness are fail-closed. Existing native privilege drop, workspace validation, state reservation, signal/deadline behavior and cleanup remain intact. Test-only synthetic transport injection lives under tests/fixtures and is absent from production configuration; the production upstream cannot be overridden by callers.

## T03 iteration and commands

The permanent FAST ITERATION / TEST DISCIPLINE section in AGENTS.md requires the smallest relevant tests, only failed-test reruns while debugging, Docker qualification for boundary changes, no unchanged image rebuild, one meaningful fast checkpoint, one final offline suite and no retest for docs. During development an HTTPX automatic Connection header was corrected before forwarding; only failed tests were retried. A test sibling initially kept the fixture network alive; putting it under Compose ownership fixed fixture cleanup, and the failed focused probe was retried. No production security relaxation was needed.

`make runtime-image`, `make gateway-image`, `make prepare`, `make doctor`, `make test-fast`, `make test`, `make verify-gateway-boundary`, `.venv/bin/aictrl run claude demo/project`, and `.venv/bin/aictrl events --session <uuid>` are current commands. `make verify-runtime-boundary` explicitly selects EGRESS_ONLY for its separate historical lifecycle qualification. Authentication helpers continue to use the existing T02 image; normal runtime uses the T03 bootstrap overlay.

Gateway uses the existing lock; no dependency was added. A temporary Docker build context contains only code/public requirements. The unchanged proxy and installed native Claude binary were reused. Final local image identities are gateway `sha256:0dc4b19fb7f058786d8c98ba2ac07a31f99f37311a0f86cdfc8a9e6f38b5c58e`, Claude runtime `sha256:5ed6e58ce234b455d1599fa4f7fba03188255e441af8f43781722151913cdeaf`; full pins/notices remain in docker/images.lock.json and OPEN_SOURCE.md. Images were built locally, not published remotely.

## Remaining scope

No T03 blocker remains. Qualification is Linux/amd64 with a non-root host user. Response completion denotes transport completion; SSE semantic errors pass through unchanged. Gateway overhead and provider usage were not measured. Direct-provider auxiliary features can be denied by the inference-host restriction. Guards, MCP authorization, budgets/reload, dashboard and other agent adapters remain later work.

T04 starting point: build the required real-agent allowed/denied/direct-bypass integration proof on this existing native gateway/policy/store and supervisor; reuse the focused deterministic fixtures and safe per-session events. Do not start T04 without its next instruction.

## Archived T02 record

Historical T1 / repository T02 record: PASS, completed before T03. The future-scope statements below describe that checkpoint.

## Verified on 2026-10-03

- Actual Claude Code 2.1.285 starts interactively using `aictrl run claude demo/project`, displays `/workspace` and the existing subscription, and exits normally after native Ctrl+C. The workspace trust dialog remains a native decision.
- Live controlled-egress smoke returned exactly `AICTRL_OK`, exit 0. This used transitional destination enforcement, not the future application-aware gateway.
- Native status reports authenticated. Repeated `make claude-login` returns 0 without a browser flow. Named state survives container restart at UID/GID 1000:1000. Status uses read-only state, metadata-only owner selection and complete native privilege drop; native JSON/stderr are never echoed.
- 87 offline tests passed with `make test`. Earlier `make test-fast` passed all then-current 85 tests; its two additional lifecycle/UI regressions are included in the final full-suite result. No additional test run is needed for documentation changes.
- `make verify-runtime-boundary` passed 29 checks on each of two runs: host UID/GID, non-root, all capability sets zero, no-new-privileges, CPU/memory/PID limits, denied firewall mutation, workspace read/create/edit, writable dedicated state, absent host credentials/socket, public-only CA, actual native CLI, allowed HTTP/CONNECT, denied host/port/private destinations, direct IPv4, host/sibling, TCP/UDP DNS, UDP and IPv6 blocking.
- The same real-runtime qualification verified normal cleanup twice, zero denied upstream/host/UDP hits, timeout 124, host SIGINT 130, SIGTERM 143, native exit 7 propagation, concurrent state rejection, proxy-loss fail-closed behavior, and partial infrastructure startup failure exit 2. No session-labelled containers/networks/volumes remained; synthetic fixture state was preserved until explicit fixture cleanup. Production provider state was never replaced by a synthetic test volume.
- Both Compose configurations validate. Actual image/version and native authentication/state checks passed. The original ten Docker authentication-boundary checks passed during T01 cleanup; runtime qualification independently exercises the production T02 path.
- All project-owned environment names use `AICTRL_`. No credentials, native auth file contents, or full model prompts were inspected/exported/logged. `plan.md` is unchanged.

## Implementation decisions

- Supervisor uses per-session UUID names/labels, checked workspace paths, free internal subnet selection, safe Docker errors, engine-level state reservation, a single host deadline and owned-resource cleanup. Print input reaches the Docker workload over stdin rather than Docker arguments. Restrict/terminate hooks remain available for later milestones.
- Runtime identity is host UID/GID (observed 1000:1000). Bootstrap prepares only container-owned home/provider state with no-follow ownership changes and suppresses usermod's implicit home traversal. No chmod/chown of the selected repository occurs. Native capability bounding/effective/permitted/inheritable/ambient sets are all zero. Setup-only DAC_OVERRIDE handles prior state ownership; KILL lets trusted Docker init forward signals across UID changes.
- Native login does not itself complete the interactive onboarding preference. After host authentication preflight, bootstrap sets `hasCompletedOnboarding` in native configuration using a bounded, no-follow, non-root helper. This opens no credential file and preserves native workspace trust. Actual interactive startup then reached the conversation screen without a new browser login.
- Runtime proxy is mitmproxy 12.2.3, adapted from approved agent-sandbox MIT enforcement/bootstrap assets. Static exact destination admission is the only T02 policy. Provider TLS is opaque CONNECT and receives destination/port enforcement only. Public CA is exported separately; private CA never enters the agent.
- Defaults: 2 CPUs, 2048 MiB RAM, 256 PIDs, 600 seconds including preparation. Cleanup grace is bounded and preserves external provider state. Deadline/signal/normal-exit behavior was qualified on actual Docker, not mocked enforcement.
- Shared serialized contracts remain schema 1. Routing mode is internal adapter/runtime configuration. No T03 application protocol gateway or policy/reporting implementation is included.

## Working commands and reproducibility

`make prepare`, `make doctor`, `.venv/bin/aictrl --help`, `make test`, `make test-fast`, `make compose-config`, `make claude-version`, `make claude-auth-status`, `make claude-login`, `make verify-claude-state`, `make verify-auth-boundary`, `make verify-runtime-boundary`, and `.venv/bin/aictrl run claude demo/project`.

Python is 3.12.15, uv 0.12.22, Docker 29.8.1, Compose 5.5.1. Six runtime dependencies plus pytest remain frozen in `uv.lock`; offline synchronization/lock validation passed in T01. No host Python was replaced. Image installer/binary checksums, base digest, signed apt snapshot and actual local image IDs are in `docker/images.lock.json`.

Current image identities: base `sha256:7b229dcd23ba00496574245973a8ef32a23aec99211b0db249d0e84bfacb1147`; Claude `sha256:d9c2de14b6c7eb90356de84139d4af04b7d80d2380f5034393bd4da866d9d6dd`; proxy `sha256:7fb53e47a53507de67008de4b0d3bf08e2585bee0582b223266d7c1c86f56a9f`. Images were built locally; no remote image publication is claimed.

## History and limitations

T01 established packaging/contracts/adapters, pinned actual CLI assets and native isolated login. Cleanup standardized the environment prefix and added real idempotent authentication status; 40 offline tests and ten Docker authentication probes passed before T02. Authentication was completed by the user. T01 changes were split into logical commits and pushed to `main` at the user's request.

Initial Docker access restrictions, an image-pull retry, state-owner bootstrap permissions, and the native onboarding screen were resolved. No remaining T02 blocker is known. Qualification is Linux/amd64 with cgroup v2 and a non-root host user. Credential/control workspaces, this control checkout's root, and root-host runtime identity are deliberately rejected. Provider availability is outside deterministic tests. TLS body inspection, central policy, durable audit, MCP authorization, guards, budgets and dashboard remain future milestones. Next: T03 native Anthropic Messages gateway, policy admission and SQLite events, following the approved plan.
