# AI Control Layer

Read `NOTES.md` and `plan.md` before work. The approved plan, including user-authorized milestone amendments, is the architecture source of truth. T01–T10/T05H are COMPLETE. The separate OVERNIGHT FINALIZATION instruction authorized sequential T08→T09→T10, now complete; STOP before T11. T08/T09/T10 are COMPLETE; FEATURE FREEZE was respected. Do not begin more milestone work without a separate instruction. Preserve the local T07 source of truth and do not redesign it. Native Codex's real T06 regression remains deferred; do not run or investigate it. The user subsequently authorized as many necessary Jev/Claude Code tests as needed for a correct result, overriding the overnight instruction's single-live-trial limit. Preserve test discipline and secure key handling. Codex's packaged full-access profile applies only inside AICTRL Docker, never to host configuration.

## Goal and architecture

T07 is complete and focused qualification passed55 on entering the overnight run. T08 adds host-side loopback dashboard, safe durable reporting/latency/risk/alerts and owned host response. T09 provides one offline judge and deterministic rehearsal; T10 freezes features, qualifies clean startup and leaves a demo-ready product. No frontend service/build stack, CDN or infrastructure rewrite. One implementing agent, no delegation. Do not start T11 or presentation work. Necessary real Jev/Claude tests are explicitly authorized; native Codex remains deferred. Do not repeat tests/provider calls for documentation-only edits.

Run actual coding agents in isolated Docker containers, with application-aware LLM/MCP/API gateways and an enforcing egress proxy. Use a Python 3.12 modular monolith, SQLite, validated YAML policy, and a local server-rendered dashboard. Claude/Codex use shared runtime with separate native protocols/state; stateless demo-agent uses official MCP without provider state. Guards/MCP are implemented in T06; T07 implements governance/reload. T08 implements reporting, risk, alerts and owned host response; T09 supplies the offline judge and repeatable demo. Reuse `mattolson/agent-sandbox` at `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04` and retain MIT attribution.

## Workflow and boundaries

One implementing agent owns the work. Do not delegate or start later milestones automatically. Adapters describe agent configuration; runtime owns isolation, identity, lifecycle, and resource limits. Gateway owns native protocol forwarding; policy and guards own decisions; governance owns budgets and approvals; reporting owns safe events; dashboard consumes durable reporting data. The CLI is a host supervisor. No agent or gateway gets the Docker socket.

Use typed Python, explicit errors, small modules, and pinned dependencies. Keep configuration separate from enforcement. Shared Pydantic contracts live in `src/aictrl/contracts.py`: changes require coordinated consumer updates, serialization checks, and an explicit schema-version decision. Do not put enforcement behavior in data models.

## Commands and checks

Verified commands and environmental failures are recorded in `NOTES.md`. Use `make bootstrap`, `./scripts/uv.sh sync --frozen`, `.venv/bin/aictrl --help`, `make doctor`, `make test`, `make claude-image`, `make claude-auth-status`, `make claude-login`, `make verify-claude-state`, and `make verify-auth-boundary`. Native status reports authenticated. T02 actual runtime isolation, workspace writes, limits, signal/deadline cleanup, interactive Claude and a live subscription response have passed. Use `make runtime-image`, `make gateway-image`, `make test-fast` and `make verify-gateway-boundary` for T03. Native Claude returned AICTRL_GATEWAY_OK; the final offline suite passed 127 tests and focused Docker qualification passed 47 checks. `aictrl events --session <uuid>` reads safe audit data. `aictrl verify claude demo/project` proves a real reply, forbidden application request, direct bypass denial, audit attribution and cleanup in one managed session. T04 passed once live, with 24 targeted tests and 151 final offline tests. Verification reuses unchanged production images/topology; gateway decisions are durable events, while kernel bypass denial is a probe result. `make verify-runtime-boundary` explicitly selects EGRESS_ONLY; authentication-only probes do not qualify the application gateway.

T05 commands: `make codex-image`, `make codex-version`, `make codex-auth-status`, `make codex-login`, `aictrl run codex demo/project --prompt 'Reply with exactly: AICTRL_CODEX_OK'`, `make verify-codex-boundary`, and `.venv/bin/python scripts/verify-codex-boundary.py --leases-only`. Codex 0.159.3 is pinned; native device authentication uses only aictrl-codex-state and exact auth.openai.com. The public profile is selected by --profile aictrl; no project-level provider routing or API key. The fixed Responses upstream is https://chatgpt.com/backend-api/codex, approved after the original API origin returned 401. T05 final offline suite: 194 passed; focused Docker: 42 passed; provider leases: 6 passed; live Codex exact response and one credible shared-path Claude regression passed. Do not repeat these checks for documentation-only work.

T05 cleanup passed 13 targeted adapter/profile tests and one actual read/create-file task with 20 focused checks. Codex returned AICTRL_CODEX_TOOL_OK and created codex-test.txt at host UID/GID; two Responses ALLOW/completion pairs survived cleanup. Direct internet and both inference proxy routes remain denied, credentials/socket absent, all capability sets empty and NNP active. Only the changed Codex image was rebuilt; no full suite or unchanged Claude/proxy/gateway verifier was repeated. Never apply this image's full-access profile to a host Codex configuration.

## Security invariants

Do not weaken a security boundary merely to make a demo work.

Do not silently replace real enforcement with mocked behavior.

Mount only the selected workspace, public proxy CA, and dedicated provider state. Never mount host agent configuration, SSH, AWS, Kubernetes, enterprise credentials, policy storage, audit storage, or the CA private key into agents. Agent networking must fail closed, block direct internet/host/sibling/DNS/IPv6/UDP bypasses, and drop setup privileges before running the agent. Only the proxy and gateway may access upstream networks. Provider authentication may persist in its dedicated named volume; enterprise credentials may not. Preserve that volume at ordinary shutdown and allow only one active container per provider state volume.

Never log credentials, provider tokens, or full prompts. Record inspection coverage explicitly; never silently downgrade TLS inspection. Update `NOTES.md`, `TASKS.md`, reuse records, and working commands after each milestone. Record unresolved blockers honestly; do not claim application inspection for the T02 opaque CONNECT path. T03 records STRUCTURED native Anthropic admission; generic CONNECT remains DESTINATION_ONLY. Keep inference hosts excluded from the generic proxy in APPLICATION_GATEWAY, commit admission before upstream, preserve raw SSE, and never persist payloads/auth headers/internal identity tokens. Audit lives at .aictrl/audit/events.sqlite3 outside agent mounts and ordinary cleanup.

## FAST ITERATION / TEST DISCIPLINE

Do not run the full test suite after every code change.

During implementation:
- run the smallest relevant unit/integration tests for the files being changed;
- rerun only previously failing tests while debugging;
- run Docker/runtime verification only when runtime/network/container code changed;
- do not rebuild unchanged images;
- do not repeat expensive live-provider tests unless the relevant gateway/runtime path changed.

Run the full offline suite only:
1. at a meaningful milestone checkpoint,
2. after broad/shared-contract changes when necessary,
3. once before declaring the milestone complete.

Documentation-only changes do not require rerunning tests.

Prefer targeted feedback loops measured in seconds over full-suite feedback loops measured in minutes.


## Historical T05H checkpoint

Historical milestone snapshots below retain their checkpoint-specific schema versions, scope and verification instructions. Current project status is in TASKS.md; T01–T10 are complete, current policy is schema 5/version t08, and T08 reporting/risk/alerts/host response are implemented.

Trusted runtime/handler registries replace brand selection; RuntimeSupervisor creates one identity/token and renders once. Native commands belong to adapters; Compose uses validated code-owned provider-state metadata and stable volume leases. Independent native handlers compose with gateway/control.py ControlPipeline. Policy configuration is schema 2, version t05h, with exact enabled-agent rules and BLOCK precedence; shared contracts remain unchanged schema 1. EventSink.append must commit durably before returning; SQLite WAL/FULL and safe audit remain the actual backend. No guards/MCP/governance/distributed services were added.

T05H passed 227 final offline tests, 47 Claude gateway Docker checks, 42 Codex checks, six provider lease checks, Compose validation and one real smoke per provider with durable completion/cleanup. make benchmark-gateway measures historical pre-guard local HTTP overhead at concurrency 1/10/50; full numbers/limitations are in NOTES.md and ARCHITECTURE.md. Do not repeat successful checks for docs-only changes. T06 was explicitly authorized and implemented below; this historical checkpoint did not include it.

## Historical T06 checkpoint

One shared GuardEngine handles native Anthropic/Responses input/output and MCP. Deterministic secrets BLOCK before external calls; selected Presidio email/phone/card input is REDACT, output BLOCK. Provenance-marked untrusted tool/resource text alone reaches fixed TypeSafe Jev System One, jev-latest, three noul questions/one request, thresholds 0.85, 2500 ms, 32768 characters; missing key/provider failure blocks. No NLP model, Ollama, LiteLLM, alternate provider, retry or production fake.

Host AICTRL_JEV_API_KEY becomes a private ephemeral 0400 file mounted read-only ONLY in gateway at /run/secrets/aictrl/jev_api_key. Never put the value in container env, workspace, policy, audit or logs. Native safe input/output bytes are preserved; actual PII rewrites selected input strings. SSE units/ordered interleaved groups are capped at 1 MiB/30 seconds; unsafe or incomplete units are withheld, BLOCK plus output_blocked AUDIT, no successful completion.

Official MCP SDK 2.3.0 supplies /mcp Streamable HTTP, required session identity, filtered discovery and independent per-operation authorization. Protected memory is synthetic gateway-local project/private data. Demo-agent is trusted stateless metadata, with no provider mount/auth/lease. Native state validation/reservations remain mandatory. Empty proxy allowlist is valid deny-all; no destination is added. Shared contracts remain byte-identical schema 1; MCP uses Channel.MCP/protocol null. Policy config is schema 3/version t06.

T06 final offline suite passed 380 tests; focused gateway/Codex/demo Docker checks passed 47/42/27 and provider leases six, with Compose validation. Responses tests include item-ID/done-only/delta-first/nullable reasoning frames, complete arguments, ambiguous/interleaved units, JSON-type dispatch with generic SSE labels, known DONE sentinels and null initial placeholders. Three real native qualification attempts and one separately approved no-Jev diagnostic blocked with guard.output.invalid; the diagnostic captured no rejected structure, so the exact failing branch/frame/root cause remains unconfirmed. Final diagnostics cover every output-block/non-SSE path and safe transport context, with fixed names/types/counts only; no raw values or arbitrary field names. Final diagnostic image is offline-qualified only. The user explicitly deferred Codex, all one-run permissions are exhausted, and no automatic retry is active. Temporary host key input was removed, so future live semantic commands require securely supplied host AICTRL_JEV_API_KEY again. make benchmark-guards measures deterministic/fake timing separately. Real verify-jev passed two examples on jev-1.13.0, and production demo returned T06 DEMO PASS. Claude exact reply/completion passed with a disclosed unexpected email redaction; the user accepted proceeding with it. Current evidence/limitations are in NOTES.md and docs/T06_REPORT.md. Do not rerun successful checks for docs-only edits.

At this T06 checkpoint, T07 was not yet authorized or implemented. The subsequent separate specification and completed checkpoint below supersede that historical boundary. T06's failed real Codex evidence remains unchanged.

## Historical T07 checkpoint

Policy schema 4/version t07 and feed schema 1 use immutable per-request snapshots, 500 ms validated atomic reload and independent last-good retention. Shared contracts remain byte-identical schema 1. Protected config directory mounts read-only in gateway alone. Ordered guards are secret → PII → literal/restricted-regex feed → relevant Jev; no semantic feed signatures or production fallback.

Governance uses additive tables in the same protected events SQLite file, WAL/FULL and BEGIN IMMEDIATE. Exact approval consumption and all session/agent/user/profile requests/tokens/tool_calls/agent_steps claims commit together. Failure changes no counters and preserves approval. Durable ALLOW/dispatch intent precede one action; undispatched cancellation/audit failure refunds, dispatched failure keeps spent actions/unknown tokens. Original arguments are SHA256-bound in RAM with identity/operation, policy version and full snapshot hash. Host approvals/approve/deny CLI only; default TTL 60 seconds, one consumption. No raw arguments/secrets in records.

Defaults: requests 60/minute, tools 40/600 seconds, steps 60/600 seconds, user tokens 256000/hour; independent lifetime session caps 60 steps/40 tools and existing host wall-time. Native requested output plus 4096 input allowance is reserved, fallback 8192 plus allowance; complete numeric usage settles, unknown remains reserved, subscription money stays unknown. Native filesystem tools retain Docker enforcement; counts cover gateway-observable actions.

T07 final make test: 435 passed in 6.73 seconds. Actual Docker checks 47 gateway/27 demo/42 fully synthetic Codex; governance Docker and production Jev each 33/33. SQLite concurrency 50/limit10 admitted exactly10, concurrent approval retry executes once. Corrected real Claude returned AICTRL_T07_CLAUDE_OK, session afdad8fa-6bd8-4c42-babe-d6040bfc9af9, exit0, reservation132096 settled to21519 input+20 output tokens, durable events/cleanup. One context email redaction remains disclosed. First quota-blocked attempt and explicit extra permission are recorded in NOTES.md/docs/T07_REPORT.md. No real Codex run, no lease/auth/native/proxy rebuild or T08 implementation.

The user explicitly requested preserving today's private host Jev input file; it remains outside the repo at mode0600/parent0700. Runtime-staged gateway copies are still removed normally. T08 may consume safe EventStore, BudgetState/UsageMetric/Approval projections, governance_audit and snapshot health through host reporting and existing runtime hooks. Do not start dashboard/risk/alerts/automatic restriction or termination without the separate T08 instruction.

## Historical T09 / feature freeze

T09 offline judge470 +55/30 + real Docker47/27/42 synthetic/33/27 passed. One final real Claude and one production Jev/MCP regression passed with durable lifecycle/latency/settlement and cleanup. No real Codex. T10 permits only bug/reliability/UX/docs/test-determinism fixes, clean-start rehearsal and final qualification; no features/providers/pages/guards/refactors/dependencies. Use make demo-ready, local dashboard and make demo-rehearsal. Run the final make verify-final once after stabilization; do not rerun it for subsequent docs-only edits. Preserve native volumes/workspace/audit and private host key input. Stop before T11.


## T10 final checkpoint — STOP before T11

T10 COMPLETE: one clean start passed, warm preflight 0.934 s, dashboard health/start 1.634 s, deterministic rehearsal 77.080 s, dashboard stopped. The final make verify-final passed once in 152.665 s: 472 full offline, 55 governance, 32 reporting, Compose and actual Docker 47/27/42 synthetic Responses/33 governance/27 owned response; privacy and all session/identity/key staging cleanup passed. Real Claude AICTRL_FINAL_OK and production Jev passed in T09 and were not repeated for host-only fixes. No real Codex invocation/investigation, image rebuild, new dependency or T11 work occurred. See docs/T10_REPORT.md and the short docs/DEMO.md. Native state, workspace, audit and the user-requested private host key input are preserved. Do not rerun tests for documentation-only edits. T11 remains TODO.
