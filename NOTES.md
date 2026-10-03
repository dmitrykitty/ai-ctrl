# Implementation notes

## T05 cleanup verified on 2026-10-03 — PASS

The user explicitly authorized disabling only Codex's inner sandbox inside AICTRL's existing Docker boundary. The packaged docker/codex/aictrl.config.toml now contains sandbox_mode="danger-full-access", approval_policy="never" and web_search="disabled". No host Codex configuration, Docker capability/seccomp/AppArmor/namespace setting, firewall, mount, state lease, gateway, policy, contract or dependency changed. Official [container guidance](https://learn.chatgpt.com/docs/agent-approvals-security) and [configuration fields](https://learn.chatgpt.com/docs/config-file/config-reference) were checked, along with the pinned 0.159.3 native --help. AICTRL's external isolation remains the enforcement boundary for the untrusted agent and its tools.

Only the changed Codex image was rebuilt; prior binary/base layers were cached. Updated image aictrl-codex:0.159.3-t05 is sha256:e6db7d5c88478966701b36dea1e56cf00108bc2c290cd7f752bcaf8c323c39fd, recorded in docker/images.lock.json. Existing gateway, proxy, Claude and base images were reused. Native status/preflight used the preserved isolated subscription state; no authentication flow or credential file inspection was needed.

Thirteen targeted adapter/profile tests passed in 0.21 seconds. A single managed production RuntimeSupervisor then ran the real pinned Codex with --strict-config --profile aictrl exec, using prompt input on stdin and privately captured native diagnostics. Input: “Use a local tool to read demo_codex.txt. Create codex-test.txt with exactly the same content. Then reply with exactly the file content and nothing else.” The output file started absent. Codex read the existing public fixture, created demo/project/codex-test.txt with AICTRL_CODEX_TOOL_OK, returned exactly AICTRL_CODEX_TOOL_OK and exited 0. The created file has host UID/GID 1000:1000. Successful local tool execution and the native model follow-up are now qualified.

Session 67f80fec-ee2f-492e-9c9a-949c20873f64 has two actual Responses ALLOW/completion pairs plus durable BLOCKs after cleanup:

| Action | Event ID | Request ID | Reason |
|---|---|---|---|
| ALLOW | b006322b-6150-4ab1-8de0-ec4aae274435 | c91ad9b5-72c6-4099-91b7-3fc0133a4011 | llm.policy.allowed |
| AUDIT | 536f5738-903d-4d3d-ae9d-d6aa13c66942 | c91ad9b5-72c6-4099-91b7-3fc0133a4011 | llm.upstream_completed |
| ALLOW | 7699ba1b-e7f5-4c4a-9da0-036c2725ebc1 | e56362c9-fe86-411d-92e8-1b2bc7bab2b2 | llm.policy.allowed |
| AUDIT | 25d01820-25b0-4450-bd47-dece0387ab6e | e56362c9-fe86-411d-92e8-1b2bc7bab2b2 | llm.upstream_completed |
| BLOCK | 8dbbe143-e994-4c75-9fbb-42e21f73e00b | bb19537a-7880-4045-a595-0d793d7c22b8 | llm.policy.blocked |

All events identify the same trusted session and codex/codex, LLM OUTBOUND, RESPONSES, STRUCTURED, schema 1 and policy t03. The final BLOCK is the controlled valid-identity forbidden GET, HTTP 403. Unsupported auxiliary/catalog requests also remained blocked. Payloads/tool results/provider credentials/internal token were not persisted in the audit or printed by the probe.

All 20 focused checks passed in this one session: real read/final answer, real created file, non-root matching UID/GID, five capability sets empty, NNP, absent host SSH/AWS/Kubernetes/host mount and Docker socket, effective full-access/never container profile, web search disabled, direct 1.1.1.1:443 denial, generic CONNECT denial for both api.openai.com and chatgpt.com, forbidden GET denial, paired native gateway follow-up, durable attribution/BLOCK, complete cleanup, provider state preserved, unchanged workspace ownership/mode and created file ownership. No session-labelled container/network/volume or host identity directory remained. Workspace files, provider state and SQLite survived.

This was a small configuration cleanup: the previous 194-test final suite, 42-check Docker matrix, six lease checks and live Claude proof were not repeated. No T06 guards, semantic tool authorization, MCP or other later milestone work was started. T01–T05 remain COMPLETE. The historical nested-namespace limitation below is resolved by this explicitly authorized container profile change.

The initial test/build submissions were not executed because automatic approval review hit its usage limit. After the user requested continuation, the same approval path was retried successfully; the check was not bypassed.

## Initial T05 qualification record

The following record describes T05 before this cleanup. Its image identity and optional nested-sandbox limitation are historical; the current image and real tool proof are recorded above.

## Initial T05 verified on 2026-10-03 — PASS

T01–T05 are COMPLETE. T05 uses the explicitly user-approved fixed native ChatGPT backend after the originally requested API origin rejected native subscription authentication. T06 has not started. Approximately 40 active minutes were used, including qualification and documentation, excluding the user-requested break. The initial segment was 17:52:39–18:03:44 UTC (~11 minutes); work resumed at 18:56:10 UTC.

### Native image, authentication and routing

Codex CLI remains 0.159.3, installed from the [official pinned release](https://github.com/openai/codex/releases/tag/rust-v0.159.3) on the unchanged qualified base. Actual image --version/--help/login --help/exec --help confirmed current --no-daemon, --profile, device-auth, status and exec behavior. The CLI, official code-mode host and bubblewrap helper are root-owned 0755 and verified against the release's published SHA-256 digests. Original Codex Apache-2.0 and bubblewrap license files are retained in source and image. Final image IDs are Codex sha256:9c3ed5324c57e7b0cf96845a5fceda07e7217e4acf24ac49b62d34d4e91af2e3 and gateway sha256:fd0e33ea05894cf9a0ffce7b065880bf5b5aa170c49b69fd9f859cfc90e912d0. Base, Claude and proxy images were not rebuilt. Full checksums and references remain in docker/images.lock.json.

The initial fresh-state native status reported unauthenticated. After the break, the user completed native codex --no-daemon login --device-auth through the separate auth.openai.com-only CONNECT proxy. Authentication persists only in aictrl-codex-state at /home/dev/.codex. Fresh offline status containers mount this volume read-only, use network none and drop all native privilege sets before codex login status. Recreated-container status and make codex-login both report already authenticated; repeated login exits 0 without a browser flow. Both also passed using the final image after the live runtime changed provider-state ownership to the host UID/GID. No native credential file was inspected, printed, copied or logged; host ~/.codex and browser/SSH/enterprise state were never mounted. No Platform API key or custom OAuth implementation was introduced.

The public profile is /home/dev/.codex/aictrl.config.toml, selected by --profile aictrl. It uses model_provider=aictrl, http://gateway:8000/codex, wire_api=responses, requires_openai_auth=true, supports_websockets=false and zero request/stream transport retries. env_http_headers obtains X-AICtrl-Session from the runtime's AICTRL_SESSION_TOKEN; the profile contains no session secret. Routing is not stored in workspace .codex/config.toml. Saved native provider Authorization and ChatGPT-Account-ID remain separate from internal identity and pass upstream. Native prompt-mode stderr is suppressed because the CLI prints full input there; final answer/exit and safe events remain available. Prompt input stays on stdin, history persistence is disabled, log directory is ephemeral and exec uses --ephemeral.

With the T05-requested fixed https://api.openai.com/v1 origin, successful native login still produced HTTP 401. The controlled safe diagnostic session was c8c36b3a-0e63-411e-a015-4bc149fcaca5: native exit 1, upstream admission/failure pairs, unsupported-route BLOCKs, direct/proxy denial and cleanup. Only fixed classifications and numeric HTTP status codes were emitted; no raw provider diagnostics or credential files were opened. The user explicitly answered “Spróbuj natywnego backendu ChatGPT”. The gateway now pins https://chatgpt.com/backend-api/codex in code, matching the approved plan. There is no fallback or caller/environment origin selector. Only POST /codex/responses is supported and maps to /backend-api/codex/responses; catalog/auxiliary routes remain default BLOCK. Both api.openai.com and chatgpt.com remain excluded from generic proxy inference.

### Real Codex proof and durable evidence

Command: .venv/bin/aictrl run codex demo/project --prompt 'Reply with exactly: AICTRL_CODEX_OK' --timeout 90. The real pinned CLI returned exactly AICTRL_CODEX_OK, native/launcher exit 0, through APPLICATION_GATEWAY and native Responses HTTP/SSE using saved ChatGPT authentication.

Session 631061e2-494e-479e-a5ae-64fb58f6c179 was read from EventStore after production cleanup:

| Action | Event ID | Request ID | Reason |
|---|---|---|---|
| ALLOW | 2ade4b38-58db-42cb-bbd9-ef6757544ee5 | 1746dcd9-9ce4-42ea-a703-7538c8e925c2 | llm.policy.allowed |
| AUDIT | f8892080-c174-432d-88be-20f721e15951 | 1746dcd9-9ce4-42ea-a703-7538c8e925c2 | llm.upstream_completed |
| BLOCK | f39e1a05-f59b-488a-a978-c2f9f73ec581 | 21c9d47b-718d-4bba-8699-c5719231c39a | llm.policy.blocked |

All identify codex/codex, LLM OUTBOUND, RESPONSES, STRUCTURED, schema 1 and current policy identifier t03. Admission occurred at 19:12:34.937449 UTC; completion at 19:12:38.029961 UTC. Four unsupported native auxiliary/catalog requests were blocked; no additional endpoint was required for the exact response. SQLite contains safe attribution only, without input/instructions, tool arguments/results, authorization, provider/internal tokens or response bodies. Admission is committed before upstream; errors remain fail closed.

One RuntimeSupervisor continues to own either adapter's workspace, cryptographic per-session identity, Docker topology, state reservation, limits, deadline, signals and cleanup. Agent UID/GID is 1000:1000, all capability sets are zero and no-new-privileges remains set. Agent mounts stay exactly selected workspace, selected provider state and public CA. The gateway has only trusted identity/policy/audit, all capabilities dropped, read-only root and no workspace/provider state/socket/private CA. Bootstrap selects only the two exact supported provider paths and never recursively changes workspace ownership/modes. Shared serialized contracts and dependency lock are unchanged.

### Verification and iteration

- Targeted shared runtime/config/CLI/policy/auth checks: 67 passed. The first Codex/Responses/Claude-gateway/policy group had 65 pass and one incorrect test assertion; the assertion was corrected and only that test rerun, so all 66 cases passed.
- Targeted SSE terminal/Responses/Claude-gateway/adapter checks: 57 passed. Two safe native-diagnostic checks passed. During metadata refactoring a demo-adapter interface assertion failed; the unnecessary common-protocol extension was reverted and only the failing case plus the changed upstream-path assertion were rerun, both passing.
- make verify-codex-boundary passed 42 actual Docker checks. The production supervisor/bootstrap/firewall were used with separate synthetic state and a test-only Responses transport. Checks cover actual pinned CLI/profile/Responses composition, incremental native SSE, function call and matching follow-up bytes, valid-identity forbidden GET 403, missing identity 401, both inference-host proxy denials, direct public/fixture/host/sibling denial, DNS/TCP/UDP/IPv6 denial, zero denied host hits, UID/GID/capability/NNP/resource/mount boundaries, workspace read/create/edit without mode/owner changes, durable ALLOW/completion/BLOCK attribution and token-free audit, cleanup and state preservation.
- .venv/bin/python scripts/verify-codex-boundary.py --leases-only passed six actual checks: second Codex refused, failed contender preserves the first lease, concurrent authentication refused, independent Claude/Codex preparations, cleanup and both provider volumes preserved. No native client or provider contents were inspected during lease qualification.
- The focused Docker fixture initially reused the gateway address for a sibling; only the fixture's sibling address was fixed. The pinned client then exposed an early-close completion race: a bounded terminal-frame observer now recognizes a fully received response.completed before HTTP EOF, with failure/error taking precedence. Ten deterministic framing cases cover split/large/incomplete/error frames. Raw bytes remain unchanged. No firewall/topology relaxation was needed.
- One final make test passed 194 tests in 0.98 seconds. It was not repeated after image-only packaging or documentation edits. make compose-config verified runtime and both auth topologies; shell syntax and git diff checks passed. Project-owned environment naming remains AICTRL_; no misspelled project prefix remains.
- One actual Claude regression was justified by shared runtime/gateway changes: .venv/bin/aictrl verify claude demo/project returned exact AICTRL_T04_OK, exit 0, T04 INTEGRATION PASS. Session e14b23ef-5d29-41a7-bc0f-56e5a41f4e56 has ALLOW 6879f74d-2458-4afe-97d1-59e518924188 and completion ee589d82-ae30-40b3-9c41-f8a34f98ee2e for request 7ab59ea5-4c04-4652-a485-48d801ffb428, plus BLOCK fee5885b-6d25-4d0f-ad0a-428bd8996ee9 for forbidden request c004df91-53d3-4add-bb7e-0f102f4d2c0e. Historical full runtime/gateway matrices and unchanged Claude/proxy images were reused.

### Optional local-tool result and remaining limits

The public demo/project/demo_codex.txt fixture contains AICTRL_CODEX_TOOL_OK. One cheap read-file task initially found that the official codex-code-mode-host companion was missing from the image; it was added from the same release with a verified digest. Only that task was retried using the final image. The native tool then reported that the environment disallows creating its nested sandbox namespace. Session c91c7d61-c059-4bc4-a702-4c6eba9525f8 completed three real Responses admission/completion pairs, including the tool-error follow-up, but did not successfully read the file or return the requested literal. Native exit 0 is therefore not counted as successful local-tool proof. No capability, seccomp, namespace, firewall or credential isolation was weakened.

The basic real Responses criterion and all required T05 tests passed, so T05 is PASS with this optional tool limitation recorded. Native interactive entry is implemented and current help verified; an interactive Codex TUI session was not separately qualified. Provider availability/subscription is required for live commands. Usage, gateway-only latency, semantic/output guards and MCP authorization are not implemented. T06 starts from two shared native inference paths and the healthy Claude proof; any Codex tool/sandbox compatibility work must preserve the current outer boundary.

Final read-only checks confirmed zero session-labelled containers, networks or volumes for the successful Codex session, both file-task sessions and Claude regression. Both dedicated provider volumes, workspace fixture and audit survived. Fresh status and idempotent login on the final Codex image succeeded. Images are local builds, not remotely published.

Official sources checked: [native authentication](https://learn.chatgpt.com/docs/auth), [provider/profile configuration](https://learn.chatgpt.com/docs/config-file/config-reference), [native gateway requirements](https://learn.chatgpt.com/docs/enterprise/gateway-compatibility), and [SIWC app-server API configuration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server). The native subscription path was actually verified; SIWC was not implemented as an alternative authentication bridge.

## Archived T04 record

Historical T04 STATUS: PASS. T01–T04 were COMPLETE at that checkpoint. The records below describe the unchanged T04 implementation before T05.

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
