# Implementation notes

## T05 checkpoint — paused by user on 2026-10-03

T05 is IN_PROGRESS, not qualified or complete. User requested a break and continuation in about half an hour. Stop after T05; T06 is not authorized. Active implementation elapsed approximately 11 minutes (17:52:39–18:03:44 UTC); exclude the user-requested break from the 45–60 minute implementation timebox.

Implemented but still awaiting Docker/live qualification: CodexAdapter; narrow shared-supervisor selection of RESPONSES identity, isolated provider state and independent lease; dedicated native authentication/status commands; fixed-origin POST /codex/responses gateway sharing durable admission/raw SSE transport; minimal default-BLOCK Responses policy; targeted tests. Public provider profile is /home/dev/.codex/aictrl.config.toml, selected with --profile aictrl. Internal identity is env_http_headers X-AICtrl-Session / AICTRL_SESSION_TOKEN; no session secret in profile. ChatGPT-only saved authentication is required; no platform API key or host state is copied.

Official Codex 0.159.3 and its bwrap helper were downloaded from the pinned OpenAI release with GitHub-published SHA-256 digests verified. Image aictrl-codex:0.159.3-t05 was built on the unchanged qualified base. Root-owned binary and Apache-2.0 license retained; actual image --version/--help/login --help/exec --help verified. Existing Claude and proxy images were not rebuilt. Gateway code changed but aictrl-gateway:t05 has NOT been built yet; current project config selects that pending image.

Fresh aictrl-codex-state reported not authenticated using native offline login status, read-only provider volume and network none. Restricted native codex --no-daemon login --device-auth successfully produced its browser flow through an auth.openai.com-only CONNECT proxy. It was cancelled at the user-requested break; do not retain or reuse the expired one-time device code. No credentials were inspected, printed, copied or logged. Provider state volume is preserved. Authentication has NOT completed; next run should generate a fresh flow with make codex-login.

Targeted shared-runtime/config/CLI/policy/auth boundary tests: 67 passed. Targeted Codex/Responses/Claude-gateway/policy group: 65 passed and one test assertion failed (incorrect suffix length in new command assertion); fixed and that one test rerun passed. Thus all 66 selected cases have passed, without repeating the whole group. No final full suite or live provider request has run for T05.

Resume at this checkpoint:
1. Start make codex-login and let the user finish the fresh device flow; continue independent qualification while waiting. Verify offline status, recreated-container persistence and idempotent make codex-login, without reading any credential file.
2. Build only the changed gateway image with make gateway-image. Add/run focused real Docker probes for Codex state/mounts/UID/GID/capabilities, default-deny/direct/proxy denial, lease concurrency, cleanup and synthetic native Responses streaming/tool follow-up. Synthetic transport remains test-only and does not become an upstream override in production.
3. Run the exact live .venv/bin/aictrl run codex demo/project --prompt 'Reply with exactly: AICTRL_CODEX_OK' once. The requested trusted upstream is https://api.openai.com/v1; the architecture originally names ChatGPT's Codex backend. Native subscription token compatibility with this fixed API origin still needs actual verification. Never work around failure using a platform API key, copied host state or generic inference bypass. Document a reproducible technical blocker if reached and respect the remaining timebox.
4. If inexpensive and basic inference passes, qualify a native local-tool/follow-up turn. Shared Claude admission/policy tests passed; run one bounded live Claude regression only if needed for the shared changed handler.
5. Run one final offline suite; update all required milestone/reuse/architecture documentation; make logical commits/push, report the required T05 result format and stop before T06.

Known unqualified areas: actual pinned-client custom profile parsing/network path, native Responses body encoding, API-origin compatibility with native ChatGPT login, live response, native local-tool loop, and actual Codex Docker lifecycle. New client print mode suppresses native stderr because Codex otherwise prints the full input there; safe failure/exit and session events remain available. No shared contract/schema/dependency change.

Official sources checked: [authentication and custom-provider OpenAI auth](https://learn.chatgpt.com/docs/auth), [configuration fields and HTTP/SSE transport](https://learn.chatgpt.com/docs/config-file/config-reference), [SIWC app-server API configuration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server). SIWC is a distinct token-sharing integration and does not prove native Codex login tokens work at the requested API origin.

Historical T04 STATUS: PASS. T01–T04 were COMPLETE at this checkpoint. T04 adds proof orchestration only. The production supervisor, Compose topology, adapter, gateway, policy, store, firewall, proxy, dependency lock and image identities are unchanged; shared contracts remain schema 1.

## T04 verified on 2026-10-03

Command: `.venv/bin/aictrl verify claude demo/project`. One actual live invocation returned `T04 INTEGRATION PASS`, exit 0. Real Claude output was exactly `AICTRL_T04_OK`, native exit 0, using saved subscription authentication through APPLICATION_GATEWAY.

One managed session `81a0a546-45f5-40a6-9840-5e3f8d71d9ee` owned the single identity/token, workspace, agent container, gateway and proxy for the entire proof. The same non-root sandbox then sent valid-identity GET `/anthropic/v1/messages`; existing policy rejected it with HTTP 403. The forbidden request had durable BLOCK with no ALLOW or upstream completion/failure event. Direct TCP to `1.1.1.1:443` failed while ignoring gateway/proxy variables. Optional inference CONNECT through the generic proxy also returned 403. No instruction asked Claude to perform an attack and global policy was not changed.

After production cleanup, EventStore and `aictrl events --session 81a0a546-45f5-40a6-9840-5e3f8d71d9ee` confirmed:

| Action | Event ID | Request ID | Reason |
|---|---|---|---|
| ALLOW | c17eb111-7220-469a-a5e7-beb7c4167f8b | 7064738f-6390-4f85-a5f4-744d48d33909 | llm.policy.allowed |
| AUDIT | 3e4a08d0-7cbd-43ff-9d24-2bed6c321f7c | 7064738f-6390-4f85-a5f4-744d48d33909 | llm.upstream_completed |
| BLOCK | 0167525b-1bcd-44aa-947d-d6ecb49393cf | be028472-eb17-44b0-b5bc-5d97de699d45 | llm.policy.blocked |

All three identify that same real session, agent/adapter claude, LLM OUTBOUND, ANTHROPIC_MESSAGES, STRUCTURED, policy t03 and schema 1. ALLOW/AUDIT identify operation.messages; BLOCK identifies operation.unsupported. The live events occurred at 17:36:11–13 UTC.

No session-labelled container, network or session-private volume remained, and the ephemeral host identity directory was removed. The workspace, `aictrl-claude-state` and `.aictrl/audit/events.sqlite3` survived. No authentication file was inspected, synthetic authentication substituted, provider state deleted, or credential/token/full prompt recorded in proof output or audit.

Gateway decisions produce durable SecurityEvents. Kernel-level bypass rejection is a verified probe result, with no invented gateway event. The proxy denial is likewise a probe result; richer network telemetry remains later reporting scope.

## T04 implementation and verification discipline

`src/aictrl/runtime/integration.py` creates one production RuntimeSupervisor and uses its existing controlled command interface. The host sends trusted `integration_probe.py` source as Python command text; the smoke input stays on stdin. The workload invokes existing non-root UI preparation, then real native Claude and deterministic probes. There is no new runtime interface, image, mount, workspace fixture or alternate enforcement path. Native output is checked privately; only restricted safe results leave the sandbox. CLI emits concise PASS/FAIL lines and a session UUID.

Host result aggregation requires successful native output/exit, denied application/proxy/direct probes, correlated ALLOW/completion, BLOCK for the exact forbidden request, correct attribution and cleanup/persistence. Wrong/missing/duplicate result envelopes and mismatched evidence fail the proof. Unexpected native output or operational exception details are not printed. CLI exit codes: 0 PASS, 1 failed checks, 2 unsupported agent/invalid input/unavailable prerequisites.

24 focused tests passed in 0.21 seconds, covering unsupported agents, result aggregation, failed Claude/incorrect response, missing ALLOW/AUDIT/BLOCK, mismatched session/adapter/request, unexpectedly successful direct/proxy bypass, admission of the forbidden request, unsafe output, cleanup/persistence and one-supervisor orchestration with audit read after cleanup. One final `make test` passed 151 tests in 0.84 seconds. The actual proof ran once. No image was rebuilt, no full T03/T02 Docker verifier or redundant test-fast checkpoint was run, and documentation edits do not trigger more tests.

No T04 blocker remains. Live provider availability and saved subscription are required for the integration command; ordinary tests remain offline. T04 adds integration evidence without guards, budgets, MCP, another agent or dashboard. New proof code is project-owned and reuses the existing dependency/runtime assets; attribution and architectural records need no redesign.

T05 starting point: timeboxed second adapter/Codex integration if this healthy Claude path remains available, following the next milestone instruction. Do not begin T05 automatically.

## Archived T03 record

Historical T03 STATUS: PASS. T01–T03 were complete at that checkpoint; T04 was not yet started. The active configuration is APPLICATION_GATEWAY with native Anthropic forwarding, minimal strict admission and durable safe events. `plan.md` and shared serialized contracts remain unchanged (schema 1).

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
