# T07 — Governance, Atomic Budgets, Approvals and Hot Reload

**T07 STATUS: PASS / COMPLETE.** Qualified 2026-10-04, Europe/Berlin. One implementing agent; no delegation. T08 remains TODO. Real Codex was **not attempted**; its unresolved T06 `guard.output.invalid` regression and failure history remain deferred without changes to native authentication/profile or output inspection.

The user authorized T07 separately after closing T06. The initially permitted Claude attempt was blocked before upstream by the suggested 100000-token quota. After a configuration correction and offline regression, the user explicitly permitted exactly one additional attempt. That attempt returned `AICTRL_T07_CLAUDE_OK` with actual budget settlement and cleanup. Both results are preserved below. No automatic live retries occurred.

## Budgets and durable admission

| Property | Implemented behavior / evidence |
|---|---|
| Store | Standard-library SQLite in the existing protected `.aictrl/audit/events.sqlite3`; WAL, synchronous FULL, bounded five-second lock wait. Parent 0700/database 0600; outside agent mounts and ordinary cleanup. |
| Transaction | Every authorization mutation uses `BEGIN IMMEDIATE`. All applicable claims and exact approval validation/consumption are one transaction. Every counter is checked before any claim is written. |
| Scopes | `session`, `agent`, `user`, `profile`, derived exclusively from trusted identity. Every applicable rule applies. |
| Dimensions | `requests`, `tokens`, `tool_calls`, `agent_steps`; validated positive integer limits, at most 128 configured budget rules. |
| Windows | UTC epoch-aligned fixed windows: `floor(now / seconds) * seconds`. A later window creates a distinct bucket; lifetime runaway buckets never reset. Rules are bounded to 1–86400 seconds. |
| LLM | One request and one observable step, plus token reservation, before the sole send. |
| MCP | Tool: one tool call and step. Resource read: one step. Discovery: neither tool nor step. |
| Default policy | 60 requests/60 seconds; 40 tools/600 seconds; 60 steps/600 seconds; 256000 tokens/user/3600 seconds. Lifetime session caps are 60 steps/40 tools. |
| Concurrency | 50 simultaneous real SQLite reservations against limit 10: exactly 10 admitted, 40 blocked, reserved total exactly 10. |
| Rollback | A failing three-dimension claim leaves every counter unchanged. An approved record remains APPROVED on quota failure; tests compare complete before/after projections. Duplicate claims are rejected. |
| Store failure | Actual missing SQLite table and admission-audit failures prevent provider/backend side effects. Errors expose fixed reasons, not SQL/raw exception contents. |

Additive tables preserve the original reporting `events` table and schema-1 SecurityEvent serialization:

| Table | Safe persisted data |
|---|---|
| `budget_counters` | Budget ID, scope/identity ID, dimension, window bounds, limit, used/reserved numbers; composite bucket key. |
| `approvals` | Approval/session/original-request IDs, SHA256 request digest, policy version, snapshot hash, operation ID, state, request/expiry/consumption times. |
| `reservations` | Reservation/session/request IDs, policy version, state, optional approval ID, time, optional numeric schema-1 UsageMetric JSON. |
| `reservation_claims` | Reservation ID, exact counter bucket and positive reserved amount. |
| `governance_audit` | Record/approval/session IDs, policy version, fixed action and timestamp for host decisions/consume/cancel. |

The shared admission path is: captured policy and guards → optional durable REDACT → atomic reservation/approval consumption → durable ALLOW → durable dispatch intent → one protected action. If admission/audit fails or is cancelled before dispatch, cancellation refunds every reserved claim and restores the unexpired consumed approval to APPROVED. Once dispatch intent commits, request/tool/step counters are spent; errors, output blocks and cancellation cannot refund them. The external call is not a SQLite transaction: a crash after dispatch intent can conservatively charge an action that was never sent. A crash before dispatch leaves a conservative outstanding reservation. No automatic crash refund is implemented.

## Token reservation and settlement

Native handlers own numeric extraction. A trusted positive `max_tokens` or `max_output_tokens` reserves the requested output limit plus the configured 4096-token input allowance. Missing/untrusted limits use an 8192-token fallback plus allowance. No reservation cap discards a declared larger valid limit merely to fit the quota.

Anthropic usage includes input, cache creation, cache read and final cumulative output; streaming settlement requires final usage and `message_stop`. Responses accepts complete input/output counts and validates total when supplied. Non-streaming JSON and Anthropic count_tokens are covered. Bools, floats, negative/string counts, inconsistent totals and incomplete usage cannot create a guessed refund. Complete metadata settles exactly once to actual counts. Missing/invalid/incomplete usage marks UNKNOWN and retains the entire token reservation; dispatched actions remain spent. Unknown counts remain in their original historical window rather than being fabricated as zero.

Raw upstream usage is collected separately from guarded output release. Numeric UsageMetric uses `billing_mode=SUBSCRIPTION`, `cost_microunits=null`; no monetary estimate is made. Exact input tokens cannot be known before send. Actual usage may exceed an allowance/reservation/limit; settlement charges all observed tokens, including an excess, and later claims block. This is conservative accounting with configured input allowance, not a hard bound on pre-generation total tokens.

The initial quota was too small for the native client's reservation. The final configuration is 256000/user/hour; a synthetic regression reproduces the former 100000 rejection with zero counters and verifies a full 132096 reservation for declared output 128000 under the corrected policy. [Official model limits](https://platform.claude.com/docs/en/models/overview) and [Claude Code output settings](https://code.claude.com/docs/en/env-vars) support accommodating large native output limits; they are not evidence of the unrecorded first request's exact field value. No model, provider routing or security guard was changed.

## Exact-request approvals

Policy schema 4 adds `REQUIRE_APPROVAL`, with precedence BLOCK > REQUIRE_APPROVAL > ALLOW. REDACT remains a guard action. Policy rules are generic; no operation-name exception grants permission. The approval-required demo tool remains visible in discovery with a safe description; private resource access remains BLOCK.

`request_digest` is SHA256 over RAM-only canonical JSON containing trusted session/agent/user/profile, channel/direction/protocol, target/operation and original arguments. Key order is normalized; request UUID is excluded so exact retries can match. Original pre-redaction arguments remain bound. Raw arguments/prompts, matched text, identity tokens and credentials never enter the approval database or CLI. Policy version and full validated policy/feed snapshot hash additionally bind permission, including edits that reuse a version label.

| Lifecycle | Behavior |
|---|---|
| PENDING | Exact first call creates an approval, returns its safe UUID and does not dispatch. Waiting/retrying does not grant permission. |
| APPROVED | Explicit host CLI only; approval does not refresh the original TTL. |
| DENIED | Explicit host denial; no execution. |
| EXPIRED | Lazy expiry at original request time + default 60 seconds, including already-approved unused records. |
| CONSUMED | Exact approved retry consumes permission atomically with every applicable budget. Further retries fail. |

Host commands:

```bash
.venv/bin/aictrl approvals --session <session-uuid>
.venv/bin/aictrl approve <approval-uuid>
.venv/bin/aictrl deny <approval-uuid>
.venv/bin/aictrl budgets
```

Every retry rechecks policy, original binding and guards under its captured snapshot; new BLOCK rules win. Changed arguments/session/target/operation/version/snapshot require another approval. Denied/expired/consumed records are not reused. Two simultaneous approved retries produce exactly one successful reservation; the MCP integration proves exactly one backend counter increment. Admission-audit failure restores an undispatched approval; quota rejection never consumes it.

Only the verifier coordinates a host CLI approval for the explicitly task-authorized harmless counter fixture. It verifies expected session/operation/digest and calls actual `aictrl approvals`/`approve`; product admission never auto-approves. The fixture performs no deletion.

## Reload and threat feed

The policy config explicitly migrates schema 3→**4**, version `t07`; schemas 1/2/3 receive migration errors. Configuration models are frozen/strict and shared contracts remain unchanged. `ConfigSnapshotManager` captures policy, compiled engine, guard settings, validated feed and a canonical snapshot hash. A lifecycle-owned 500 ms poll uses inode/mtime/size to detect edits/atomic replacements, validates whole candidates and publishes one complete immutable reference. No policy/feed file parsing occurs in request admission.

Each LLM request, stream and MCP operation retains one snapshot through output inspection, accounting and final audit. Tests change policy while a stream is active and prove its version does not mix with the next request. Valid policy/feed changes take effect without gateway restart. Invalid files independently retain last good snapshots, including malformed regex, JSON/YAML/schema and missing candidates; a valid independent file can still reload. The first poll also closes the initial-read/rename race. Private health exposes active policy/feed versions and fixed reload categories only. Startup requires valid configuration.

The protected config directory is mounted read-only **only into gateway** at `/etc/aictrl/config`. Directory binding preserves visibility after host atomic file replacement. Agent/proxy mounts, network, native state leases, resource limits and host wall-time enforcement are unchanged.

`config/threat-feed.json` has schema 1 and a safe version identifier. Each signature has ID, enabled flag, channel set, pattern, `literal` or `regex`, and BLOCK action. Limits: 128 signatures, 256 characters/pattern, 128 KiB/file. Literal matching is case-sensitive. Regex permits classes, dots, anchors and safe escapes; groups, repetition, alternation, lookarounds, backreferences and inline flags are rejected, including in disabled signatures. Semantic feed signatures are unsupported/rejected. No new regex dependency is added.

Order is secrets → selected PII → feed → relevant Jev. Feed scanning examines inspected segments and their bounded concatenation; split-field regression tests pass. A feed match prevents semantic/backend calls and records only `threat.<signature-id>`, never matched text/pattern. Production demonstration atomically installs a literal signature, observes its BLOCK without backend dispatch/restart, supplies invalid policy/regex candidates and proves the valid active signature still blocks. Coverage remains bounded extracted text/decoded JSON, not arbitrary encoding, binary/images or independently completed output units.

## Runaway and preserved regression boundaries

Session lifetime hard limits block future observable operations after 60 agent steps or 40 tools, independent of fixed windows. Demo temporarily uses four lifetime tool calls and proves the fifth blocks after the windowed quota is raised. The host's monotonic deadline remains authoritative: default 600 seconds including preparation, shorter `--timeout` only. No automatic restriction/termination, scoring, alert, dashboard or UI approval is introduced.

Final offline coverage includes T06 secret/PII/Jev failure behavior, poisoned MCP result withholding, private memory denial, native Messages/Responses framing, audit secrecy, runtime mounts/isolation and admission failure. Native local filesystem/shell tools stay under Docker enforcement; T07 counters cover observable gateway/MCP operations rather than claiming universal pre-execution native tool interception.

## Qualification results

| Command / proof | Actual result and scope |
|---|---|
| Targeted iterations | Small SQLite/policy/reload/usage/MCP/native/cancellation groups passed; final four governance files contain 55 cases: store 14, integration 10, reload/feed 22, usage 9. Counts from earlier overlapping groups are not added together. |
| Concurrency | Real SQLite 50 contenders/limit 10: 10 admitted; approved concurrent retries: exactly one consumes/dispatches. |
| `make verify-governance` | PASS, 51 cases at that checkpoint and 14 reported proof groups, no external calls. Four subsequently added safety/quota regressions passed in the final suite. |
| `make verify-governance-demo` | 33/33 checks, real Docker/SDK/host CLI with explicitly injected offline Jev fixture; session `8762bccf-bb7f-4818-a0ea-71f8016733b9`, 35 safe events. Not presented as live Jev. |
| `make verify-gateway-boundary` | 47/47 actual Docker checks: native messages/count_tokens, mount/UID/caps/NNP/resource boundary, network/proxy denial, durable audit and cleanup; final gateway image. |
| `make verify-demo-boundary` | 27/27 actual Docker checks, synthetic key/offline Jev only: stateless boundary, protected config/key denial, MCP/guards/cleanup. |
| `make verify-codex-boundary` | 42/42 **fully synthetic** checks, pinned CLI against synthetic Responses backend/state; zero actual Codex provider calls. |
| `make compose-config` | Runtime and both native authentication Compose definitions validate. Lease code/auth/profile unchanged; historical lease matrix was not repeated. |
| Production governance/Jev | 33/33 checks, actual fixed production Jev, session `8f0b625c-4a61-487b-b7c3-de3982c0a26d`, 38 safe events, exit 0, recorded `2026-10-04T00:27:02.120288Z`. No LLM. |
| Real Claude, corrected quota | PASS, exact response, native exit 0, durable admission/completion, complete numeric settlement and all resource cleanup checks. Details below. |
| Final `make test` | **435 passed in 6.73 seconds**, Python 3.12.15. Previous meaningful checkpoint: 434 before the live quota finding; one added regression justified the final run. Documentation afterward does not rerun tests. |

As recorded in prior notes, threaded/async tests stall in the restricted runner. Affected targeted/full tests and Docker qualifications ran with reviewed escalation; no production enforcement workaround was added. Final offline suite includes serialization/architecture checks; no dependency or shared-contract change was made.

### Production MCP/Jev evidence

The production governance demo used `.venv/bin/python scripts/verify-governance-demo.py --live --key-file <private-host-file>`. The actual host CLI approved `58a95311-b8ad-4ce2-936b-f5d36c754698`, original request `2a32201f-ebd1-45bc-82bf-2043bfa71e3a`, requested `00:26:56.812756Z`, expiring one minute later. It became CONSUMED once. Changed arguments created another PENDING record; replay never executed.

Backend counter was 0 before approval and exactly 1 afterward. Four backend calls completed in total: three harmless lookups and one approved counter call; their safe returned text received production Jev checks. The verifier also proved small tool-quota denial, no partial step increments, discovery's zero tool quota, policy BLOCK reload, literal feed BLOCK, invalid-candidate retention, no gateway restart, lifetime runaway BLOCK, host coordination before cleanup and stateless operation without provider lease. Database checks found no raw argument, feed marker, key or internal identity token. All session containers/networks/ephemeral volumes and staged identity/key files were removed.

The user explicitly requested keeping the private host input file for use again today. Its 0600 mode and 0700 parent were verified; it remains outside the repository. Ephemeral gateway copies are still removed normally. No key value was printed or saved in tracked files, Docker environment, workspace, policy, audit or report. No persistent environment setup was created.

### Real Claude evidence and the first blocked attempt

The one initially authorized attempt, session `ba49123e-eb31-4b01-a909-eb5fe682e988`, exited 1 under the 100000-token quota. Request `9196a618-cd21-4ad7-8bc8-48fb1e314adb` had the known context EMAIL_ADDRESS redaction and BLOCK `d71f4cbe-3db8-4d66-9d31-d00ea922bf0a`, reason `governance.budget.tokens_exceeded`. It had no ALLOW, reservation, provider send, usage or completion; cleanup passed. Exact request payload/declared output field was not persisted. The safe failure report remains `.aictrl/qualifications/t07-claude-budget-block.json`.

After quota correction, synthetic regression and 435 offline passes, the user explicitly allowed one additional attempt. The wrapper made exactly one native invocation with no Jev key/calls and no retry:

```bash
.venv/bin/aictrl run claude demo/project \
  --prompt 'Reply with exactly: AICTRL_T07_CLAUDE_OK' --timeout 90
```

Session **`afdad8fa-6bd8-4c42-babe-d6040bfc9af9`**, request **`8a5647d8-881f-46cb-b729-907ebac09e78`**, native exit **0**, exact **`AICTRL_T07_CLAUDE_OK`**. Safe report recorded `2026-10-04T00:42:38.356951Z` at `.aictrl/qualifications/t07-claude.json`:

- EMAIL_ADDRESS REDACT `12852946-eea2-4ec6-b612-5131e028da13`, ALLOW `2a164af7-0572-4571-9254-2c61ef9e69a6`, completion AUDIT `f4134c2c-6333-440e-827e-5c276b29ab9f`; all schema 1/policy t07. No BLOCK/failure. The extra email-shaped context redaction remains disclosed as in T06; zero-redaction behavior is not claimed and no whitelist was added.
- Reservation **`745f1db6-709b-4e8a-bd4a-7e70960435c3`**: request 1, configured step 1, lifetime step 1, tokens **132096**. Final state **SETTLED**.
- Native usage: **21519 input**, including cached input counters, **20 output**, **21539 total**; unused **110557** reservation released. Billing SUBSCRIPTION, money unknown/null.
- Correlated durable events/accounting survived session cleanup. No labelled container/network/ephemeral volume remains; accepted dedicated native state/workspace/audit are preserved.

Real Codex was **not run** and its recorded deferred T06 status is unchanged. All per-attempt live permissions are exhausted; no further automatic trial is authorized.

## Files and version decisions

Files added (17):

| Area | Files |
|---|---|
| Configuration/demo | `config/threat-feed.json`; `demo/agent/governance.py` |
| Qualification | `scripts/verify-governance.py`; `scripts/verify-governance-demo.py`; `scripts/qualify-claude-t07.py` |
| Governance | `src/aictrl/governance/store.py`; `budgets.py`; `approvals.py`; `admission.py`; `reload.py` in the same directory |
| Native usage/guards | `src/aictrl/gateway/usage.py`; `src/aictrl/guards/threat_feed.py` |
| Tests | `tests/unit/test_governance.py`; `test_governance_integration.py`; `test_reload.py`; `test_usage.py` in the same directory |
| Documentation | `docs/T07_REPORT.md` |

Files changed (47):

| Area | Files |
|---|---|
| Documentation | `AGENTS.md`; `ARCHITECTURE.md`; `NOTES.md`; `README.md`; `REUSE_DECISIONS.md`; `TASKS.md`; `plan.md` |
| Configuration | `config/policy.yaml`; `config/project.yaml` |
| Build/images | `Makefile`; `docker/demo/Dockerfile`; `docker/images.lock.json`; `scripts/demo-image.sh`; `scripts/gateway-image.sh` |
| Existing qualification | `scripts/benchmark-gateway.py`; `scripts/verify-codex-boundary.py`; `scripts/verify-demo-boundary.py`; `scripts/verify-gateway-boundary.py` |
| Demo/CLI | `demo/agent/main.py`; `src/aictrl/cli/main.py` |
| Gateway | `src/aictrl/gateway/anthropic.py`; `app.py`; `audit.py`; `control.py`; `protocols.py`; `responses.py` in the same directory |
| Guards/MCP | `src/aictrl/guards/engine.py`; `src/aictrl/mcp/control.py`; `demo_backend.py`; `server.py` in the MCP directory |
| Policy | `src/aictrl/policy/engine.py`; `loader.py`; `models.py` in the same directory |
| Runtime | `src/aictrl/runtime/compose.py`; `config.py`; `supervisor.py` in the same directory |
| Fixtures | `tests/fixtures/demo_probe.py`; `gateway_factory.py`; `gateway_probe.py` in the same directory |
| Existing unit tests | `tests/unit/test_architecture.py`; `test_codex.py`; `test_gateway.py`; `test_gateway_runtime.py`; `test_mcp.py`; `test_policy.py`; `test_responses.py`; `test_t06_runtime.py` in the same directory |

Shared `src/aictrl/contracts.py` is byte-for-byte unchanged, **schema 1**. Existing Approval/BudgetState/UsageMetric contracts are reused; no enforcement enters models. Policy config is **schema 4/version t07**; threat feed **schema 1**; image manifest **schema 1**; reporting events retain their existing table/contract. SQLite governance is additive. `pyproject.toml`/`uv.lock` are unchanged; no ORM/distributed service/NLP model/dependency was added. MIT attribution and upstream `mattolson/agent-sandbox` pin remain intact.

Only source-changed gateway/demo images were rebuilt. Recorded `docker/images.lock.json` image IDs:

- `aictrl-gateway:t07`: `sha256:8fbc7dde580c2b5d6fa92f99521878112d27fe5b28b6d1a2fe97f2107510b9d4`.
- `aictrl-demo:t07`: `sha256:78adcc3ca97a772dd9c120c30a788866af6f1a6f23d581d086c38159ea7fbbb7`.

Native Claude/Codex, base and proxy images were reused. The final quota fix is protected host configuration and requires no image rebuild. Historical benchmark numbers predate T07; no new latency claim is made.

Final review: `git diff --check` passed; inventory is exactly 47 changed/17 added files. Contracts, dependency declarations/lock and `docs/T06_REPORT.md` have no diff. An in-memory comparison found no actual Jev key value in the changed/added files, T07 qualification reports or audit database/WAL; it printed only a boolean. The private input file and 0600/0700 modes were verified without showing its contents.

## Known limitations and T08 starting point

Governance is local/single-host SQLite, with serialized writers and fixed windows only. There are no distributed quotas, shared gateway fleet or distributed configuration consensus. Hot reload is process-local; runtime/image/network/provider-state settings do not reload. Changing a budget identity/window selects a new counter bucket; policy administration is a trusted host operation.

Approvals are one-use, exact-request/snapshot-bound, host CLI only, with no argument display or browser UI. No automatic renewal or universal native shell tool approval is implemented. Unknown token usage is retained conservatively; input allowance and trustworthy provider metadata limit enforcement precision. Monetary subscription accounting remains unknown. Threat feed has only the restricted literal/regex text coverage; semantic signatures and arbitrary encoded/binary scanning are absent. There is no automatic session termination/risk response. Real Codex's earlier compatibility issue remains unresolved/deferred.

T08 can query existing safe SecurityEvents via EventStore, numeric BudgetState projections, ApprovalManager states, reservations/UsageMetric and governance_audit, plus active snapshot health. Reporting/risk/alerts should consume these durable safe records while preserving awaited admission commits. Later host response logic can call existing runtime restrict/terminate hooks with trusted session identity; it must not put Docker access into agents/gateway. T07 adds none of that dashboard/scoring/alert/export/automatic lifecycle work.

**STOP: T07 COMPLETE. T08 TODO; await a separate specification.**
