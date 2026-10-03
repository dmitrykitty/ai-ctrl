# AI Control Layer

Read `NOTES.md` and `plan.md` before work. The approved plan is the architecture source of truth. T01–T04 are complete. T03 native subscription forwarding and T04 repeatable integration proof are verified. T05 Codex integration is authorized within a 45–60 minute timebox. Paused by user after approximately 11 active minutes; resume from the T05 checkpoint in NOTES.md after the user returns. Stop after T05; do not start T06.

## Goal and architecture

Run actual coding agents in isolated Docker containers, with application-aware LLM/MCP/API gateways and an enforcing egress proxy. Use a Python 3.12 modular monolith, SQLite, validated YAML policy, and a small server-rendered dashboard. Claude is the first real agent; Codex is a later integration/fallback. Reuse `mattolson/agent-sandbox` at `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04` and retain MIT attribution.

## Workflow and boundaries

One implementing agent owns the work. Do not delegate or start later milestones automatically. Adapters describe agent configuration; runtime owns isolation, identity, lifecycle, and resource limits. Gateway owns native protocol forwarding; policy and guards own decisions; governance owns budgets and approvals; reporting owns safe events; dashboard consumes durable reporting data. The CLI is a host supervisor. No agent or gateway gets the Docker socket.

Use typed Python, explicit errors, small modules, and pinned dependencies. Keep configuration separate from enforcement. Shared Pydantic contracts live in `src/aictrl/contracts.py`: changes require coordinated consumer updates, serialization checks, and an explicit schema-version decision. Do not put enforcement behavior in data models.

## Commands and checks

Verified commands and environmental failures are recorded in `NOTES.md`. Use `make bootstrap`, `./scripts/uv.sh sync --frozen`, `.venv/bin/aictrl --help`, `make doctor`, `make test`, `make claude-image`, `make claude-auth-status`, `make claude-login`, `make verify-claude-state`, and `make verify-auth-boundary`. Native status reports authenticated. T02 actual runtime isolation, workspace writes, limits, signal/deadline cleanup, interactive Claude and a live subscription response have passed. Use `make runtime-image`, `make gateway-image`, `make test-fast` and `make verify-gateway-boundary` for T03. Native Claude returned AICTRL_GATEWAY_OK; the final offline suite passed 127 tests and focused Docker qualification passed 47 checks. `aictrl events --session <uuid>` reads safe audit data. `aictrl verify claude demo/project` proves a real reply, forbidden application request, direct bypass denial, audit attribution and cleanup in one managed session. T04 passed once live, with 24 targeted tests and 151 final offline tests. Verification reuses unchanged production images/topology; gateway decisions are durable events, while kernel bypass denial is a probe result. `make verify-runtime-boundary` explicitly selects EGRESS_ONLY; authentication-only probes do not qualify the application gateway.

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
