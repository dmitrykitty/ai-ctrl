# AI Control Layer

Read `NOTES.md` and `plan.md` before work. The approved plan, including its user-authorized T06 amendments, is the architecture source of truth. T01–T05/T05H and T06 are COMPLETE under the user's explicit decision to defer Codex's unresolved real-provider regression and proceed with working Claude/Jev/MCP. Do not claim real Codex T06 success. Current results/status are in `docs/T06_REPORT.md`. The user instructed “Domknij T06; T07 podam osobno”; do not start T07 or resume Codex automatically. Codex's packaged Docker profile alone uses danger-full-access, approval never, web search disabled; AICTRL's Docker filesystem/network/UID/capability boundary remains the enforcement layer. Never apply this profile to host Codex configuration.

## Goal and architecture

Run actual coding agents in isolated Docker containers, with application-aware LLM/MCP/API gateways and an enforcing egress proxy. Use a Python 3.12 modular monolith, SQLite, validated YAML policy, and a future small server-rendered dashboard. Claude/Codex use shared runtime with separate native protocols/state; stateless demo-agent uses official MCP without provider state. Guards/MCP are implemented in T06; governance/dashboard remain future work. Reuse `mattolson/agent-sandbox` at `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04` and retain MIT attribution.

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


## T05H checkpoint

Trusted runtime/handler registries replace brand selection; RuntimeSupervisor creates one identity/token and renders once. Native commands belong to adapters; Compose uses validated code-owned provider-state metadata and stable volume leases. Independent native handlers compose with gateway/control.py ControlPipeline. Policy configuration is schema 2, version t05h, with exact enabled-agent rules and BLOCK precedence; shared contracts remain unchanged schema 1. EventSink.append must commit durably before returning; SQLite WAL/FULL and safe audit remain the actual backend. No guards/MCP/governance/distributed services were added.

T05H passed 227 final offline tests, 47 Claude gateway Docker checks, 42 Codex checks, six provider lease checks, Compose validation and one real smoke per provider with durable completion/cleanup. make benchmark-gateway measures historical pre-guard local HTTP overhead at concurrency 1/10/50; full numbers/limitations are in NOTES.md and ARCHITECTURE.md. Do not repeat successful checks for docs-only changes. T06 was explicitly authorized and implemented below; this historical checkpoint did not include it.

## T06 checkpoint and next boundary

One shared GuardEngine handles native Anthropic/Responses input/output and MCP. Deterministic secrets BLOCK before external calls; selected Presidio email/phone/card input is REDACT, output BLOCK. Provenance-marked untrusted tool/resource text alone reaches fixed TypeSafe Jev System One, jev-latest, three noul questions/one request, thresholds 0.85, 2500 ms, 32768 characters; missing key/provider failure blocks. No NLP model, Ollama, LiteLLM, alternate provider, retry or production fake.

Host AICTRL_JEV_API_KEY becomes a private ephemeral 0400 file mounted read-only ONLY in gateway at /run/secrets/aictrl/jev_api_key. Never put the value in container env, workspace, policy, audit or logs. Native safe input/output bytes are preserved; actual PII rewrites selected input strings. SSE units/ordered interleaved groups are capped at 1 MiB/30 seconds; unsafe or incomplete units are withheld, BLOCK plus output_blocked AUDIT, no successful completion.

Official MCP SDK 2.3.0 supplies /mcp Streamable HTTP, required session identity, filtered discovery and independent per-operation authorization. Protected memory is synthetic gateway-local project/private data. Demo-agent is trusted stateless metadata, with no provider mount/auth/lease. Native state validation/reservations remain mandatory. Empty proxy allowlist is valid deny-all; no destination is added. Shared contracts remain byte-identical schema 1; MCP uses Channel.MCP/protocol null. Policy config is schema 3/version t06.

T06 final offline suite passed 380 tests; focused gateway/Codex/demo Docker checks passed 47/42/27 and provider leases six, with Compose validation. Responses tests include item-ID/done-only/delta-first/nullable reasoning frames, complete arguments, ambiguous/interleaved units, JSON-type dispatch with generic SSE labels, known DONE sentinels and null initial placeholders. Three real native qualification attempts and one separately approved no-Jev diagnostic blocked with guard.output.invalid; the diagnostic captured no rejected structure, so the exact failing branch/frame/root cause remains unconfirmed. Final diagnostics cover every output-block/non-SSE path and safe transport context, with fixed names/types/counts only; no raw values or arbitrary field names. Final diagnostic image is offline-qualified only. The user explicitly deferred Codex, all one-run permissions are exhausted, and no automatic retry is active. Temporary host key input was removed, so future live semantic commands require securely supplied host AICTRL_JEV_API_KEY again. make benchmark-guards measures deterministic/fake timing separately. Real verify-jev passed two examples on jev-1.13.0, and production demo returned T06 DEMO PASS. Claude exact reply/completion passed with a disclosed unexpected email redaction; the user accepted proceeding with it. Current evidence/limitations are in NOTES.md and docs/T06_REPORT.md. Do not rerun successful checks for docs-only edits.

Stop before T07. Budget reservation enters ControlPipeline after guards/REDACT and before durable ALLOW/upstream; request-bound approvals/budgets enter MCP after argument guards and before ALLOW/backend. Policy/threat-feed reload replaces the static validated snapshot. Governance, dashboard/risk response and distributed deployment remain unimplemented.
