# AI Control Layer

Read `NOTES.md` and `plan.md` before work. The approved plan is the architecture source of truth. The current authorization covers T01 only; stop at that milestone.

## Goal and architecture

Run actual coding agents in isolated Docker containers, with application-aware LLM/MCP/API gateways and an enforcing egress proxy. Use a Python 3.12 modular monolith, SQLite, validated YAML policy, and a small server-rendered dashboard. Claude is the first real agent; Codex is a later integration/fallback. Reuse `mattolson/agent-sandbox` at `c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04` and retain MIT attribution.

## Workflow and boundaries

One implementing agent owns the work. Do not delegate or start later milestones automatically. Adapters describe agent configuration; runtime owns isolation, identity, lifecycle, and resource limits. Gateway owns native protocol forwarding; policy and guards own decisions; governance owns budgets and approvals; reporting owns safe events; dashboard consumes durable reporting data. The CLI is a host supervisor. No agent or gateway gets the Docker socket.

Use typed Python, explicit errors, small modules, and pinned dependencies. Keep configuration separate from enforcement. Shared Pydantic contracts live in `src/aictrl/contracts.py`: changes require coordinated consumer updates, serialization checks, and an explicit schema-version decision. Do not put enforcement behavior in data models.

## Commands and checks

Verified commands and environmental failures are recorded in `NOTES.md`. Use `make bootstrap`, `./scripts/uv.sh sync --frozen`, `.venv/bin/aictrl --help`, `make doctor`, `make test`, `make claude-image`, `make claude-login`, `make verify-claude-state`, and `make verify-auth-boundary`. T01 `run` must fail clearly until T02 is implemented. Test meaningful contract validation, adapter configuration, and prerequisite failure handling. The real image's `claude --version` has passed; user browser authorization remains pending under the T01 exception. Later networking checks must exercise actual boundaries and cannot treat authentication-only probes as runtime qualification.

## Security invariants

Do not weaken a security boundary merely to make a demo work.

Do not silently replace real enforcement with mocked behavior.

Mount only the selected workspace, public proxy CA, and dedicated provider state. Never mount host agent configuration, SSH, AWS, Kubernetes, enterprise credentials, policy storage, audit storage, or the CA private key into agents. Agent networking must fail closed, block direct internet/host/sibling/DNS/IPv6/UDP bypasses, and drop setup privileges before running the agent. Only the proxy and gateway may access upstream networks. Provider authentication may persist in its dedicated named volume; enterprise credentials may not. Preserve that volume at ordinary shutdown and allow only one active container per provider state volume.

Never log credentials, provider tokens, or full prompts. Record inspection coverage explicitly; never silently downgrade TLS inspection. Update `NOTES.md`, `TASKS.md`, reuse records, and working commands after each milestone. Record unresolved blockers honestly and wait for the next instruction after T01.
