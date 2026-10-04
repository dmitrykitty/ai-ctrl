# Implementation notes

## T10 final checkpoint — 2026-10-04 — PASS / COMPLETE

OVERNIGHT FINALIZATION STATUS: PASS. T07 entry governance gate passed 55; preserved local T07/T08/T09 milestone commits. T10 FEATURE FREEZE respected: only own-session risk/status provenance, real Jev aggregation, refresh/error/date labels, two focused numeric regressions and documentation. No new feature/provider/page/guard/dependency/refactor, image rebuild or real Codex work. T11 is TODO; stop here.

One clean start passed: make demo-ready 0.934 s, dashboard health/start 1.634 s, complete deterministic rehearsal 77.080 s, whole run/dashboard stop 80.012 s. Actual Docker/MCP/SQLite/host CLI uses explicit offline semantic fixtures. Representative six-page visual review passed at laptop 1180×800, with overview at 1440×900/1920×1080; filters/details/focus/date labels/local assets are readable. Ephemeral 5000-event/100-session metadata query measurement had maximum 49.886 ms overview /28.080 ms sessions, five warm reads; no production history changed and no provider performance claim.

Final make verify-final PASS once after stabilization, exit 0, 152.665 s, recorded 02:45:09 UTC: full offline 472 in 9.408 s, focused governance 55, reporting 32, Compose, actual Docker 47 gateway/27 MCP/42 fully synthetic Responses/33 governance/27 owned response. All privacy/actual-key comparison and session container/network/volume/identity/key staging cleanup checks passed. Native volumes/workspace/audit preserved. Project-owned conservative scan passed 192 files with references or reviewed synthetic fixtures only. No native authentication contents opened, actual secret values printed, tracked environment/database/cache/debug artifacts or external publication.

Real Claude AICTRL_FINAL_OK and production Jev evidence passed in T09, retained separately; no repeated live trial for host-only T10 changes. The user authorized necessary Jev/Claude tests, while native Codex remains explicitly deferred. Private host key input remains mode 0600/parent 0700 outside the repo as requested; runtime staged copies are removed normally. See [final report](docs/T10_REPORT.md) for exact evidence/limits and the 28-added/37-changed overnight inventory, [short demo guide](docs/DEMO.md) for the four tomorrow commands. Safe T10 judge snapshot is .aictrl/qualifications/t10-final-judge.json, ignored by Git. Separate local milestone commits leave a clean tree; no push claimed. Documentation-only closure does not rerun tests.

## T09 checkpoint — 2026-10-04 — PASS / COMPLETE

Offline make verify-final passed154.15s: full470, governance55, reporting30, Compose and actual Docker47/27/42 synthetic Responses/33 governance/27 response. Safe privacy and all resource/ephemeral cleanup passed. No real Codex invocation. Actual production Claude returned AICTRL_FINAL_OK, session44a58b6d-c9f5-4e6c-b83c-e97ef3c3898a, exit0, settled21514 input/15 output tokens, durable lifecycle/latency and cleanup; one context email redaction disclosed. Actual production Jev/MCP33/33 passed in sessionbb963658-5f32-424a-80fb-1850c34e4791 with semantic n4 p50=246.327ms/p95=635.070ms, separate from deterministic guards. No retry needed after the green offline gate. Full evidence/limits/failure matrix in [T09 report](docs/T09_REPORT.md).

Warm make demo-ready passed14 checks0.722s without installs/rebuild/provider calls. Deterministic make demo-rehearsal passed76.255s using actual Docker/SDK/SQLite/CLI and explicitly offline semantic fixtures, populated durable labelled history and completed responses. make demo-reset removes only terminal offline-demo/session-only accounting; active/shared-scope refusal and native/workspace preservation passed3 tests. README now leads with the four demo commands. T09 COMPLETE; continue T10 feature freeze/clean start, stop before T11. Private host Jev input remains by user request; temporary gateway copies are removed.

## T08 checkpoint — 2026-10-04 — PASS / COMPLETE

Overnight T08→T09→T10 is explicitly authorized; stop before T11. One agent, no delegation. T07 entry gate passed55. T08 adds the loopback read-only six-view dashboard, durable lifecycle/status/latency, explainable windowed risk/alerts and owned host notify/restrict/terminate. Policy schema5/versiont08; shared contracts remain1. Final offline checkpoint465 passed8.54s; new verifier30 passed3.32s; subsequent view refinement27 targeted passed. Actual Docker response27/27 passed: restriction removed the gateway path, termination exited143 in4.311s, completion/lifecycle survived cleanup and no resources/ephemeral secrets remained. See [T08 report](docs/T08_REPORT.md) for exact evidence, initial observer/fixture fixes and limitations. Only gateway/demo images changed. No real Codex work. Continue T09; live Jev/Claude trials authorized as necessary, with private host key preserved.

Working commands: .venv/bin/aictrl dashboard --no-open, make verify-reporting, make verify-reporting-response. Dashboard startup is local and frontend assets require no Internet. T09/T10 will qualify production regression, deterministic rehearsal, warm timings and final clean start.

## T07 checkpoint — 2026-10-04 Europe/Berlin — PASS / COMPLETE

The user separately authorized T07 after accepting T06 with real Codex deferred. One implementing agent, no delegation. Atomic governance, request-bound approvals, immutable policy/threat-feed reload and lifetime runaway limits are complete. T08 remains TODO; stop here. Full data model, atomicity/lifecycle, exact file inventory, schemas, limits and T08 interfaces are in [docs/T07_REPORT.md](docs/T07_REPORT.md). Historical notes below retain their then-current state, including all T06 Codex failures. No real Codex invocation or investigation occurred in T07.

### Implementation and boundaries

- Standard-library SQLite adds budget_counters, approvals, reservations, reservation_claims and governance_audit beside unchanged events. WAL/FULL and BEGIN IMMEDIATE protect every authorization mutation. All applicable budget claims plus exact approved-record consumption commit together. Failed claims change no counters and do not burn approvals. Durable ALLOW/dispatch intent precede the sole provider/backend call; undispatched failure/cancellation refunds, dispatched actions remain spent and unknown tokens reserved. Actual missing-table/audit/cancellation regressions fail closed.
- Generic policy schema 4/version t07 adds REQUIRE_APPROVAL with BLOCK precedence. Existing schema-1 Approval/BudgetState/UsageMetric/SecurityEvent are reused; contracts.py, pyproject.toml and uv.lock are unchanged. RAM-only canonical SHA256 binds original arguments/identity/channel/operation; persisted policy version and full policy/feed snapshot hash prevent permission reuse after edits. PENDING/APPROVED/DENIED/EXPIRED/CONSUMED, default 60-second original TTL, actual host approvals/approve/deny CLI, single atomic consume. No raw arguments/key/prompt/internal token stored.
- Budget scopes session/agent/user/profile; requests/tokens/tool_calls/agent_steps; UTC epoch-aligned fixed windows. LLM request1/step1, MCP tool1/step1, resource step1, discovery0. Defaults requests60/60s, tools40/600s, steps60/600s, user tokens256000/hour. Lifetime steps60/tools40 never reset on window changes; host wall-time remains authoritative.
- Native requested output plus 4096 input allowance reserves fully, fallback8192+allowance; complete numeric Anthropic/cache/Responses usage settles exactly once. Invalid/missing/incomplete usage retains the entire reservation and subscription money remains null. Exact input is unavailable before send; observed excess is charged and blocks future claims rather than pretending a hard total-token pre-generation bound.
- Lifecycle-owned 500 ms poll validates complete candidates before atomically publishing frozen policy/guard/feed snapshots. One reference per operation/whole stream. Invalid policy/feed independently retain last good and expose only safe health categories. Protected config directory is read-only/gateway-only for visible atomic renames. Feed schema1 is literal/restricted-regex BLOCK, max128 signatures/256 characters/128 KiB; groups/repetition/alternation/lookarounds/backrefs/flags/semantic kinds rejected. Order secrets→PII→feed→relevant Jev. No new runtime/state/network allowance, dependency, NLP model, service, dashboard or automatic termination.

### Tests and actual Docker

Final **make test: 435 passed in 6.73 seconds**, Python3.12.15. Four final governance/usage/reload files contain 55 cases (14/10/22/9). Targeted loops covered serialization/native/guard/MCP/runtime/cancellation safety; counts overlap. make verify-governance passed 51 cases at its checkpoint and reported 14 proof groups; four later duplicate/excess/cancellation/quota cases passed in the final suite. SQLite50 concurrent/limit10 admitted exactly10, blocked40. Two concurrent approved retries consume once; MCP counter executes once. Failed multi-budget validation preserves every counter and approved state.

Reviewed escalation was used for affected threaded/async tests that stall in the restricted runner, as previously documented. No production workaround was introduced. One meaningful checkpoint passed434 before Claude revealed the quota mismatch; one new regression plus the configuration correction justified the final435 run. Documentation-only changes afterward do not rerun the suite.

Final source-changed gateway image passed **47/47 make verify-gateway-boundary**, **27/27 make verify-demo-boundary**, and **42/42 make verify-codex-boundary**, the latter fully synthetic/pinned CLI with synthetic provider state/backend and zero real Codex calls. Direct/host/sibling/DNS/UDP/IPv6 and inference-proxy denial, non-root/all-capability-zero/NNP/resources, protected config/key/credentials denial, durable admission and cleanup remain enforced. make compose-config validated runtime and both native auth Compose files. Unchanged lease/auth/profile/base/native/proxy code and images were reused; their historical matrices were not repeated.

Synthetic governance Docker/SDK/actual host CLI passed **33/33**, session **8762bccf-bb7f-4818-a0ea-71f8016733b9**, 35 safe events, recorded00:19:42.496023UTC. Its semantic fixture is explicitly offline. Subsequent production demonstration uses the final gateway and actual Jev as below.

### Production Jev governance demo — PASS

`.venv/bin/python scripts/verify-governance-demo.py --live --key-file <private-host-input>` passed **33/33**, exit0, session **8f0b625c-4a61-487b-b7c3-de3982c0a26d**, **38** safe durable events, recorded00:27:02.120288UTC. No LLM call. Actual host aictrl approvals/approve approved the exact counter-only fixture **58a95311-b8ad-4ce2-936b-f5d36c754698**, original request **2a32201f-ebd1-45bc-82bf-2043bfa71e3a**, requested00:26:56.812756UTC/expiry60seconds. CONSUMED once; changed arguments created another PENDING record. Product admission has no automatic approval.

Counter0 before approval→1 exactly once; four backend completions total (three safe lookups/one approved counter) with production Jev result checks. Pending/replay/changed-argument denial, small tool-quota BLOCK/no partial step increments, discovery0, host atomic policy BLOCK/feed literal reload, invalid policy/regex last-good retention, no restart, lifetime tool cap4 and cleanup all proved. No raw argument/feed marker/key/internal token in SQLite. Session containers/networks/ephemeral volumes and staged identity/key directories were removed.

The user explicitly asked to **keep today's private host key input** at `/tmp/aictrl-t07-jev-input-_lb3d7cz/jev.env`; it remains mode0600 with parent0700 outside the repo. No value printed or written into tracked files/environment manifests/workspace/audit. Gateway-staged ephemeral copies still disappear normally. No persistent host environment setup was created.

### Real Claude quota finding, correction and explicitly authorized extra trial

Initial single permitted smoke was blocked before upstream under user.tokens100000/hour: session **ba49123e-eb31-4b01-a909-eb5fe682e988**, request **9196a618-cd21-4ad7-8bc8-48fb1e314adb**, native exit1, BLOCK **d71f4cbe-3db8-4d66-9d31-d00ea922bf0a**, governance.budget.tokens_exceeded. No ALLOW, reservation, provider send, usage or completion; cleanup passed. Request payload/declared output field was not retained. Safe failure report remains .aictrl/qualifications/t07-claude-budget-block.json.

Corrected only configured quota to256000, without reducing reservation or changing models/provider/guards. Added one offline test reproducing100000BLOCK/no counters and full132096 reservation for128000 output+4096 input under256000. Official [model limits](https://platform.claude.com/docs/en/models/overview) and [Claude Code settings](https://code.claude.com/docs/en/env-vars) support accommodating128K output; the exact first request field is not inferred as observed. Targeted regression passed; final435 suite passed. Config-only correction required no image rebuild/Docker/Jev repeat.

The user then explicitly replied **“Tak, jedna próba po poprawce”**. Exactly one additional `.venv/bin/python scripts/qualify-claude-t07.py --live` invoked:

    .venv/bin/aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_T07_CLAUDE_OK' --timeout 90

PASS: **AICTRL_T07_CLAUDE_OK**, native exit0, session **afdad8fa-6bd8-4c42-babe-d6040bfc9af9**, request **8a5647d8-881f-46cb-b729-907ebac09e78**, safe report .aictrl/qualifications/t07-claude.json recorded00:42:38.356951UTC. REDACT **12852946-eea2-4ec6-b612-5131e028da13**, ALLOW **2a164af7-0572-4571-9254-2c61ef9e69a6**, completion AUDIT **f4134c2c-6333-440e-827e-5c276b29ab9f**, all schema1/policyt07; no BLOCK/failure. One EMAIL_ADDRESS context redaction remains disclosed, consistent with T06; no raw context dump or whitelist.

Reservation **745f1db6-709b-4e8a-bd4a-7e70960435c3** held request1/configuredstep1/lifetimestep1/**132096 tokens**. Final **SETTLED** with **21519 input including cache counters +20 output =21539**, releasing **110557**. SUBSCRIPTION/cost null. Actual numeric accounting and durable events survived cleanup; container/network/ephemeral-volume absence all passed, dedicated native state/workspace/audit preserved. No Jev key/call in either native smoke. All single-attempt permissions exhausted; no further automatic retry.

### Images and next boundary

Only changed gateway/demo sources rebuilt, final docker/images.lock.json:

- aictrl-gateway:t07: **sha256:8fbc7dde580c2b5d6fa92f99521878112d27fe5b28b6d1a2fe97f2107510b9d4**;
- aictrl-demo:t07: **sha256:78adcc3ca97a772dd9c120c30a788866af6f1a6f23d581d086c38159ea7fbbb7**.

No new dependency pins, native binary/auth/state/profile changes or MIT attribution changes. Shared contracts1, policy4, feed1, image manifest1. Final git diff --check passed, exact inventory47changed/17added; contracts/dependency files/T06 report unchanged. An in-memory actual-key comparison found no value in changed/new files, T07 reports or audit DB/WAL; only a boolean was printed. Private input0600/parent0700 remains. Historical benchmarks predate governance and were not repeated. No distributed quota/rolling windows/semantic feed/universal native tool approvals/hard exact-input pre-generation quota are claimed. T08 can query safe events, budget/usage/approval projections, governance_audit and active snapshot health, then integrate host restrict/terminate hooks. Dashboard/risk/alerts/exports/automatic lifecycle work is excluded. **T07 COMPLETE; STOP before T08.**

## T06 checkpoint — 2026-10-04 Europe/Berlin — PASS / COMPLETE, Codex deferred

The user explicitly authorized T06, superseding the former stop-before-T06 checkpoint. One implementing agent, no delegation. T01–T05/T05H remain COMPLETE; T07 and later remain TODO. Full capability checklist, exact file inventory, benchmark percentiles and limits are in [docs/T06_REPORT.md](docs/T06_REPORT.md). Historical notes below describe their then-current state, not today's T06 status.

Acceptance changed explicitly after the user confirmed the real Claude result: “na razie możemy odpuścić Codexa” and then “Domknij T06; T07 podam osobno.” Close T06 with Codex's unresolved regression recorded as deferred, not successful. No T07 or automatic Codex retry. Claude/Jev/production MCP demonstrate the accepted working path. Original mandatory Codex qualification and Claude's zero-unexpected-guard expectation were not fully met; the failure/redaction evidence remains below.

After closure, the user explicitly authorized committing T06 and pushing to origin/main. Publication is split into implementation and milestone documentation commits. The previously verified code is unchanged; documentation/commit publication does not repeat the 380 passing offline tests or live-provider checks.

### Implemented and qualified

- Shared ephemeral GuardEngine: stable secret signatures BLOCK before Jev; selected Presidio email/phone/Luhn-card input REDACT and output BLOCK; no NLP engine/model download. Native handlers own input provenance and output framing, while common control owns guards, durable events and lifecycle. Safe original bytes remain unchanged; actual redaction rewrites selected fields and commits REDACT/ALLOW before upstream. MCP uses the same identity, PolicyEngine, GuardEngine and EventSink, with strict schemas before dispatch and result withholding before delivery.
- External TypeSafe Jev replaces the earlier local Ollama/LiteLLM choice as explicitly approved. Fixed System One origin, jev-latest, three named noul questions/one request, thresholds 0.85, 2500 ms, max 32768 text characters/256 segments, strict numeric/model/usage parsing, bounded response, no redirects/retries/fallback. Only untrusted tool/results/resources are semantic subjects. Errors/missing key BLOCK. Known secrets prevent the call; identified PII is removed first. Residual unrecognized sensitive text can still reach this approved external service.
- Host AICTRL_JEV_API_KEY is staged into a private ephemeral 0400 file mounted read-only into gateway alone. No value in Docker environment/manifest, agent/proxy, workspace, policy, SQLite or logs. Identity and key are removed at session cleanup. Shared contracts remain byte-for-byte schema 1; MCP uses existing Channel.MCP/protocol=null. Policy configuration explicitly migrates to schema 3/version t06; config models remain configuration validation, not enforcement.
- Native output is bounded RAM-only Anthropic blocks/Responses items or ordered interleaved groups, 1 MiB/30 seconds. Split secrets/PII and decoded escaped tool arguments are checked before release. Safe raw frames/pings/order remain intact. Unsafe/malformed/incomplete/timeout/compressed output blocks, with correlated BLOCK/output_blocked AUDIT and no false completion. Previous safe units cannot be recalled. Explicit transport errors retain failure even after native terminal evidence.
- Official pinned MCP SDK 2.3.0 low-level Streamable HTTP at internal /mcp, lifecycle-managed stateless JSON transport and pre-SDK required single-header session authentication. Discovery is filtered; every guessed tool/URI is independently authorized. Synthetic backend: safe_lookup, echo_contact, poisoned_document, counter-only destructive_delete_all (blocked, never executed). Synthetic project memory is visible/readable; private memory remains gateway-only and guessed reads never execute.
- Trusted stateless demo-agent needs no LLM, provider state, login or lease and retains native state/lease requirements for Claude/Codex. Same UID/GID, zero capabilities, NNP, limits, selected workspace/public CA, firewall and readiness. Empty proxy list now means valid deny-all, never DNS/allow-by-default. Its official SDK attack sequence demonstrates all controls and concise PASS/FAIL/PARTIAL.

### Test and Docker evidence

Final make test: **380 passed in 5.02 seconds**. Shared serialization, native regression, architecture, safety, MCP and Jev fake-provider checks are included. Focused groups: 173 passes/six initial fixture failures; only those six corrected cases reran and passed; 73 runtime/adapter checks; 75 native/Jev/MCP/output checks; 13 terminal/argument checks; three additional Responses redaction cases; four identity cases; 14 proxy checks; 11 transport/terminal regressions; 62 Responses checks; 95 combined native framing checks plus two changed label/privacy cases. Diagnostics then passed 48/77 focused checks; 16 diagnostic cases, including six final non-SSE/transport/production-logging cases, are in the final suite. Counts overlap. One full checkpoint initially had 349 passes/one transport-audit regression; the targeted correction passed, then 350 passed. Later live findings justified 359/364 checkpoints; one final checkpoint qualifies the completed diagnostics and user-accepted scope. No suite/live tests were rerun for docs.

Restricted runner async/thread tests stalled, including an isolated StreamingResponse comparison; the same comparison outside that runner passed. Only this task's stalled test processes were stopped. Affected targeted/full tests ran outside the runner; no production workaround or weakened durability/enforcement was added.

make verify-gateway-boundary passed **47 actual Docker checks** once. make verify-codex-boundary passed **42** initially and again after the first Responses-only compatibility change. make verify-demo-boundary passed **27** after fixing its empty-list startup, inaccessible-root-path probe and copying the current qualified gateway-readiness script into the demo image. Six provider lease checks and make compose-config passed. Original broad state/auth/lifecycle matrices and unchanged native binaries were not rebuilt/repeated. Native 47/42 checks cover direct/host/sibling/DNS/UDP/IPv6 denial, proxy inference partition, non-root/capability/NNP/resource boundaries, safe durable events and cleanup. Demo 27 covers real stateless boundary/MCP attacks and gateway-only read-only 0400 synthetic-key staging. Demo verifier explicitly injects an offline semantic fixture and makes zero live Jev calls; production has no such fallback.

### Real Jev and production demo — PASS

The initial make verify-jev returned PENDING (key absent, zero calls). The user subsequently supplied the key through a private temporary host .env file outside the repo (0700 parent, 0600 file). It was loaded into host subprocess environment without showing it. Production still stages a separate gateway-only 0400 file. After the final authorized qualification, the temporary input file and its directory were removed and their absence verified. No persistent key configuration was created; future runs need AICTRL_JEV_API_KEY supplied securely in the host environment again. The key was never printed.

Real make verify-jev made exactly two fixed synthetic requests:

| Case | Model | Injection / exfiltration / bypass | Latency | Input/output tokens | Result |
|---|---|---|---:|---:|---|
| Safe public document | jev-1.13.0 | 0.04 / 0.03 / 0.02 | 371.170 ms | 404 / 62 | ALLOW / PASS |
| Indirect injection | jev-1.13.0 | 0.98 / 0.99 / 0.99 | 260.728 ms | 418 / 62 | BLOCK / PASS |

Only model/probabilities/tokens/latency/action were recorded in ignored .aictrl/benchmarks/jev-qualification.json; no key/state/prompt. These two observations are not a latency distribution/classifier accuracy guarantee.

Production `.venv/bin/aictrl run demo-agent demo/project --timeout 90`, with the host key supplied securely, returned **T06 DEMO PASS**, exit 0. Session **5ea56280-5255-4c0d-a2f5-49011fac925b**, **21** durable MCP events, policy t06/schema 1. Destructive guessed-call BLOCK **50df6f5b-8d86-4f76-94e6-65fb981b9d1f**; secret input BLOCK **657dd231-0d27-4284-8e53-3be1fc78c4a6**; PII REDACT **a64dce38-1b7b-47dc-a60f-94afe5a08bdd** then ALLOW **0a47ed11-d072-455c-a30b-ad02e8d1b5f1** and completion **4de88371-f3a5-4651-8cda-4251ce2d3674**. Private guessed read BLOCK **fda4e65d-4ebe-4f5a-a248-7691b6082a77**. Poison request **706601e2-d344-4d7e-b5b5-f6db04ab8350**: ALLOW **714d6f5b-b242-49c9-a879-6e94d2294a1d**, semantic BLOCK **7e3518ea-44bc-49cc-a028-044b7611f747**, mcp.result_blocked **3d457a77-bea6-4601-a551-a1db6a9e5e95**. No poisoned result delivered or successful backend completion for it. All session-labelled containers/networks/ephemeral volumes and host identity/key directory were removed.

### Native real-provider regression and deferred Codex issue

One real Claude smoke returned exactly **AICTRL_T06_CLAUDE_OK**, exit 0, session **4bce4aa4-2967-4421-8539-4d5dc6d7dae6**. Request **0d7e6746-887e-4556-bd39-3fc3b59de637** has EMAIL_ADDRESS REDACT **61b0d16c-e96b-4dc3-865f-9b6c1f2574eb**, ALLOW **3959896f-763a-4ef5-845c-15462fe7d5f1** and completion **2a881296-62ef-4847-995e-e2805c5b9ffb** at 22:17:49.700/49.705/51.244 UTC. Native context contained an email-shaped value even though the supplied prompt did not; no context dump identified it. Exact output/completion passed, no BLOCK/failure, but the requested zero unexpected guard events is not claimed. No email whitelist or relaxed policy was introduced. Initial reporting helper expected a hyphenated UUID instead of the launcher’s hex identifier; it was corrected by reading the one existing safe session from SQLite without repeating the call.

Three real Codex tool-loop attempts failed closed before final output:

- Session **f88cc6b5-88ca-4944-98af-a1a59ed5f9b4**, admitted request **f3b47fdc-56e7-40ce-a83d-af2f03f39371**: ALLOW **bbee0439-361d-4881-ad7e-cc2bb7dab047**, guard.output.invalid BLOCK **dc738532-0889-4ead-a4e7-b82baf1f0088**, output_blocked AUDIT **a913f431-d701-4b0a-a50c-58bf393bbd62**. Native exit 1, no expected response/completion.
- After item-ID/done-only/delta-first/nullable reasoning corrections and 62 tests/42 Docker/359 offline passes, session **caf357ed-c407-41a5-88a9-24254cb60b2d** still failed: ALLOW **ba3751af-f6ba-487c-8131-931e541521e7**, BLOCK **c2deaa00-1885-42c0-a34c-b490b16d6641**, output_blocked **ca6ed048-2b8e-48ac-b3cd-5cd9873ae27c**, request **b71cac4d-aec3-4f7c-b24a-959f2474a184**. Native exit 1. Actual key absent from native output and SQLite. Unsupported auxiliary requests remained policy BLOCK as before.
- After final generic-label/DONE/null-placeholder corrections and 364 offline passes, the user received an explanation and explicitly authorized exactly one additional attempt. Session **bb81b2a7-53bf-4fa9-b15a-cd1112082617**, request **a143f9e5-f798-4282-9d76-b1b6fb167065**: ALLOW **5bcffe14-3612-4571-9cd1-7170b1837c52** at 22:50:58.074735 UTC, guard.output.invalid BLOCK **e71c2992-71e2-4669-9849-e6ae171c89ef** at 22:51:03.017548, llm.output_blocked AUDIT **05c45a5e-09b4-4755-aa1d-17d69d2c981a** at 22:51:03.030793, 2026-10-03 UTC. Native exit **1**, expected-response check false, no successful completion. Four unsupported auxiliary requests remained BLOCK. Container/network/ephemeral volume/host key and identity cleanup all verified; actual key absent from native output and SQLite. The wrapper's exit 0 only means the safe failure report was written; it is not a native PASS. Ignored safe reports preserve the initial/second failures and latest t06-codex.json. No further real attempt was made.

The [pinned client parser](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/codex-api/src/sse/responses.rs) confirms item IDs and done-only snapshots; it dispatches on JSON type rather than SSE label and ignores unparseable transport events. Latest compatibility code supports generic transport labels, known DONE sentinels without closing an active unit, and null initial placeholders while still requiring checked complete final arguments. Five extra safety cases and 95 native/two changed cases passed, followed by 364 offline tests. Exact rejected payloads were not logged, so the root cause remains unconfirmed. All three failed qualification sessions completely cleaned up and preserved provider state/workspace/audit. Do not claim Codex PASS, invent a root cause or silently disable guards.

The user then supplied diagnostic advice and separately authorized one live diagnostic without Jev key/calls. Added bounded metadata only: known labels/type names, key names from a fixed vocabulary, JSON value types, counts, depth two, 16 fields/four array samples, sanitized structural hash and constant rejection-condition IDs. Unknown keys/labels/type values are not retained or hashed; no scalar body values/IDs/auth/tokens enter logs. The fixed diagnostic record remains outside shared SecurityEvent/SQLite schema. Script diagnose-codex-output.py captures only the first record before ordinary supervisor cleanup; --live is required and there is no retry.

Diagnostic session **f6ba1fa7-af16-427f-8fc3-3d8169bdb9f7** also failed, native exit 1. Request **57a2805e-c4db-4d51-b219-08d7ecf6494d**: ALLOW **79e54895-d1d4-4106-a8a4-7bf191c71adb**, guard.output.invalid BLOCK **7b88c33f-0d5e-4d60-aa28-24380dd46e29**, llm.output_blocked AUDIT **dc60273a-11e9-4b65-8a06-ac3f812ec739**. No rejected structural record was captured, so the exact failing branch/frame remains unidentified. All container/network/volume/host-identity cleanup checks passed. Safe report .aictrl/qualifications/t06-codex-diagnostic.json records this failure. The initial instrumentation covered only SSE errors; offline follow-up now covers non-SSE failures and every output-block path, recording safe HTTP status/media class/header counts/encoding and selected format. Synthetic duplicate/whitespace/unknown Content-Type cases reproduce the previously uncovered branch, without establishing the real cause. Production uvicorn logging configuration is tested. No new parser admission behavior was added and no further live run followed. Final suite: 380 passed.

The user explicitly deferred Codex after confirming Claude works and requested T06 closure; no remaining live permission or automatic retry is active. Leave native auth/state/profile/egress intact and return to this issue only when separately requested.

### Guard benchmark and images

make benchmark-guards measured **21:46:05 UTC**, Python 3.12.15/Linux 7.0.0-34 x86_64/glibc 2.43, i7-10750H, 12 logical CPUs, 200 samples/five warm-ups, public synthetic ASCII, zero external calls. Combined deterministic p50/p95/p99 microseconds: **378.705/669.797/730.503** (1 KiB), **3227.976/3331.040/3530.626** (10 KiB), **10285.282/11064.589/11605.653** (32 KiB). Secret-only, PII-only and explicitly fake-semantic percentiles are in the T06 report and ignored .aictrl/benchmarks/guards-latest.json. This excludes HTTP/TLS/Docker/SQLite/provider latency; fake semantic is not real Jev latency. Historical T05H gateway numbers below predate guards and were not repeated.

Rebuilt source-changed images only, final docker/images.lock.json:

- gateway aictrl-gateway:t06: **sha256:82f1b5af26f4d76cad210c914b298178b52f34a9764399f2a093070680eb2008**;
- demo aictrl-demo:t06: **sha256:9707fb91dc66d4a70a86f11893130a5d6d38696d17c4b99417e254d332c51063**;
- proxy aictrl-proxy:mitm-t02: **sha256:aa7e0d1b9ec3ed70ff68572c4af75d933a5ebb1a288c41c0cf6d1db6232831f6**, only empty-list deny-all startup changed.

Base/Claude/Codex pins/binaries/profiles and native auth were reused. MCP==2.3.0, presidio-analyzer==2.2.364 and jsonschema==4.26.0 are new direct MIT pins; installed transitive versions/notices and inherited agent-sandbox MIT attribution remain in lock/images. No local NLP model, Ollama, LiteLLM, ORM or distributed service was added.

Third native qualification used gateway b262f5d43c6ab03419603b7154988ea6f5ba600f33f81227586a673ec18468cf; separately authorized diagnostic used 36dde1b6baf5cff69e31f3f33d101617caea8e0ed7ab4c096a593a35a5532feb. Final image adds diagnostic coverage only, with unchanged admission/output enforcement and Docker topology. Existing Docker/live checks were not repeated for this logging-only update.

### Deferred qualification and T07 boundary

T06 is closed under the user's accepted Claude/Jev/MCP scope; Codex compatibility remains unresolved and deferred. On a separately requested return, diagnose with `env -u AICTRL_JEV_API_KEY .venv/bin/python scripts/diagnose-codex-output.py --live` before changing protocol handling. Correct the observed condition, add a synthetic regression and qualify targeted checks. A final real Codex qualification then requires AICTRL_JEV_API_KEY supplied securely again; the native command is:

    .venv/bin/aictrl run codex demo/project --prompt 'Read demo_codex.txt using a local tool and reply with exactly its content and nothing else.' --timeout 90

Restoring Codex requires AICTRL_CODEX_TOOL_OK, a real tool-result/Jev-safe follow-up, correlated durable ALLOW/completion pairs and complete cleanup. All one-run permissions are exhausted, and the user explicitly deferred further work. Do not repeat successful Jev/Claude/MCP/Docker checks or tests for documentation, retry automatically or weaken output inspection. Claude's additional email redaction remains disclosed; the user accepted proceeding with its successful exact response/completion.

T07 stays TODO. Atomic budget reservation enters ControlPipeline after guards/REDACT and before durable ALLOW/upstream; usage/failure/cancellation settlement remains unimplemented. MCP request-bound expiring approvals/budgets enter after authorization/argument guards before ALLOW/backend, with equivalent resource-read governance. Replace static validated policy snapshots with atomic versioned policy/threat-feed reload and runaway limits. Risk/dashboard/local alerts remain T08. No automatic continuation.

## T05H architecture hardening verified on 2026-10-03 — PASS / COMPLETE

The PRE-T06 checkpoint preserves T01–T05 completion and the current isolation/durable admission boundary. It does not implement guards, MCP, governance or distributed deployment. Debt confirmed before refactoring and resolved (A–J); the following checklist preserves the original findings:

- [x] A: RuntimeSupervisor selects concrete Claude/Codex classes.
- [x] B: run_agent branches on provider for configuration, authentication and prompt commands.
- [x] C: a preliminary AgentSession/config is replaced by another identity and reconstructed adapter.
- [x] D: Compose chooses provider volume keys and mount paths by brand.
- [x] E: create_app chooses gateway implementations by adapter brand.
- [x] F: ResponsesGateway inherits AnthropicGateway.
- [x] G: PolicyEngine embeds provider/protocol/target literals.
- [x] H: admission, events, upstream transport and native protocol behavior share one provider class.
- [x] I: gateway admission depends directly on SQLite EventStore.
- [x] J: no independent gateway/policy/durable SQLite overhead measurement exists.

The completed replacement is a trusted static adapter registry, adapter-owned native commands, one runtime-created identity/config, generic provider-state rendering, independent protocol handlers composed with ControlPipeline, strict per-agent policy rules (configuration schema 2), and a synchronous durable EventSink protocol. Shared serialized contracts remain schema 1. Measurements use a local synthetic upstream and preserve SQLite WAL/FULL commits.


### T05H implementation and offline evidence

RuntimeSupervisor now accepts a trusted adapter, creates exactly one authoritative AgentSession/token and renders configuration once. The immutable RuntimeAgentSpec registry owns factory/config/auth/hint/gateway requirements; run_agent no longer selects brands or reconstructs adapters. Adapter metadata includes typed protocol/billing and provider-owned prompt commands; the unchanged Codex exec/stderr privacy wrapper moved into CodexAdapter. The generic external provider-state Compose key validates trusted named-volume/home metadata and uses a stable volume-derived reservation, preserving both native authentication lock names. Missing state, bind syntax, host paths, traversal and nested/wildcard paths fail before Docker actions. Auth/bootstrap remain explicit Claude/Codex allowlists and reviewed extension points, not dynamic configuration.

GatewaySession adds required internal protocol metadata; it is not a shared serialized contract. The static protocol registry selects independent AnthropicMessagesHandler/ResponsesHandler instances from that trusted protocol. Agent/adapter consistency is separate. ControlPipeline owns normalized requests, identity, generic policy, bounded RAM-only validation, durable ALLOW/BLOCK, one upstream send, raw streaming and correlated safe completion/failure. Native handlers own paths, fixed origins, headers and terminal framing; Responses no longer inherits Anthropic. ControlPipeline imports EventSink/StoreFailure, not concrete SQLite queries. EventStore retains its existing connection/transaction/storage logic and query interface; StoreFailure is re-exported for existing query callers.

Policy configuration explicitly migrates to schema 2 and version t05h. Enabled-agent exact rules match channel/direction/protocol/target/operation/inspection; matching BLOCK wins independently of order, otherwise ALLOW, otherwise BLOCK. IDs/enums/unknown fields/nonempty operations/global duplicate IDs are validated. Schema 1 receives a safe explicit migration error. The engine contains zero Claude/Codex/Anthropic/OpenAI literals or protocol branches. src/aictrl/contracts.py, uv.lock, pyproject.toml, firewall/bootstrap, native profiles, provider auth restrictions and upstream/header/SSE helpers remain byte-for-byte unchanged.

Targeted adapter/runtime/Compose checks: 52 passed. Policy/gateway/Responses/terminal/store/integration group: 103 passed initially and one enum model_copy handling case failed; that case was corrected and rerun successfully. New architecture group: 16 passed initially and one test compared the native empty-query URL incorrectly; only its assertion was corrected and rerun successfully. The corrected policy case and architecture checks cover the synthetic third RuntimeAgentSpec/adapter, one render/identity/token, generic state/lease, existing ResponsesHandler, policy, durable admission/events, stripping, cleanup, immutable registries, unsupported protocol startup, missing/unsafe state, APP_GATEWAY requirement, non-SQLite sink failure and bounded body rejection. No third production adapter, authentication mechanism or image was added.

Benchmark smoke passed using actual loopback HTTP and paired durable events; it asserts correctness only. One final make test passed **227 tests in 1.76 seconds**, including the final benchmark fixture, all shared serialization tests and both native protocol regressions. It is not repeated for subsequent docs-only changes.

Only the changed gateway was rebuilt: aictrl-gateway:t05 is now sha256:d6f9d844ce307f31f0f2124aab544804c304c7193d5639f46b754eda4ab0c874, recorded in docker/images.lock.json. Base, Claude, Codex and proxy images/pins were reused. make verify-gateway-boundary passed **47** actual Docker checks and make verify-codex-boundary passed **42**, once each after stabilization. They cover native raw Messages/count_tokens/Responses/SSE/tool-follow-up composition, admission/completion/BLOCK attribution, proxy partition, direct/host/sibling/DNS/UDP/IPv6 denials, absence of host credentials/socket, UID/GID/capability/NNP/resource boundaries, workspace/state writes/preservation, startup readiness and cleanup. Denied upstream/host hit counts remain zero. make compose-config validated the runtime and both auth topologies. The volume-derived lease qualification passed **six** actual checks: second Codex refused, failed contender preserved its owner, concurrent native auth refused, Claude/Codex prepared independently, full cleanup and both provider volumes preserved. The full historical T02 signal/deadline matrix and auth-only probes were not repeated: those mechanisms/commands are unchanged, while the focused Docker checks exercise changed ownership, mounts, readiness, forwarding and cleanup. No authentication flow or credential-file inspection/copy occurred.


### T05H real-provider regression

One final Claude command after green offline/synthetic checks:

    .venv/bin/aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_HARDENING_CLAUDE_OK' --timeout 90

Actual native output was exactly **AICTRL_HARDENING_CLAUDE_OK**, native/launcher exit 0. Session **18da6e18-6e21-42eb-b25e-39bb9e705eb6** has durable ALLOW **b367b63a-0723-46f0-97fa-17c29d268a92** and completion AUDIT **3c13055b-a95c-4cfa-812f-54d188125638**, correlated by request **e3502ff6-0abe-41dc-a5ad-bc95e823b93a**. They were read after production cleanup and identify claude/claude, LLM OUTBOUND, ANTHROPIC_MESSAGES, STRUCTURED, policy t05h and shared schema 1. Admission/completion occurred at 20:44:33.287931/20:44:35.762573 UTC. No payload/provider credential/internal token appears in the safe event fields.


One final Codex command:

    .venv/bin/aictrl run codex demo/project --prompt 'Reply with exactly: AICTRL_HARDENING_CODEX_OK' --timeout 90

Actual native output was exactly **AICTRL_HARDENING_CODEX_OK**, native/launcher exit 0. Session **c85da670-dbb8-4528-834e-089baf380353** has durable ALLOW **0344747d-ce98-4101-8566-1096a06c7e05** and completion AUDIT **c8c85357-4ab0-4e93-8616-ab8f79b16da5**, correlated by request **6f0b37bc-7233-4e9d-85e3-e169edcba334**. They identify codex/codex, LLM OUTBOUND, RESPONSES, STRUCTURED, policy t05h and shared schema 1. Admission/completion occurred at 20:45:31.937197/20:45:34.647557 UTC. Four unsupported native auxiliary/catalog requests remained durable BLOCK; no endpoint, proxy allowance or fallback was added.

Both safe event sets were read after production cleanup. Read-only checks found zero session-labelled containers/networks/volumes and no ephemeral host identity directories for either UUID. Both named provider volumes, workspace and audit survived; audit directory/database remain 0700/0600. Each real smoke ran once. No live provider call or test was repeated for documentation. The old Codex local file-tool proof was not rerun: prompt_command contains the exact existing exec flags and stderr wrapper, while the Docker verifier already exercises the unchanged native tool-call/follow-up path. No auth flow was repeated and no native credential file was opened, exported or copied.

### Local synthetic performance, 2026-10-03

Command: make benchmark-gateway. Final measurement: **20:34:45 UTC**, Python 3.12.15, Linux 7.0.0-34-generic x86_64/glibc 2.43, Intel i7-10750H @ 2.60 GHz, 12 logical CPUs. SQLite directory: this checkout’s .aictrl/benchmarks on the host filesystem. Client, local upstream and gateway share one asyncio/h11 Python process. No TLS, Docker network cost, external provider, local model, judge or deliberate provider delay is measured. WAL/FULL admission and completion commits are retained. Each independent load cohort uses a fresh downstream pool and three warm-up requests; the gateway keeps production upstream connection limits 20/10. Nearest-rank percentiles use perf_counter_ns and include the complete HTTP stream/final commit.

| Path | Concurrency | Requests | Successful / failed | p50 / p95 / p99 (ms) | Successful requests/s |
|---|---:|---:|---|---|---:|
| Direct | 1 | 500 | 500 / 0 | 2.029 / 3.005 / 3.354 | 461.194 |
| Gateway | 1 | 500 | 500 / 0 | 10.492 / 11.707 / 13.553 | 94.263 |
| Direct | 10 | 500 | 500 / 0 | 19.612 / 23.485 / 42.028 | 481.954 |
| Gateway | 10 | 500 | 500 / 0 | 54.882 / 72.378 / 103.500 | 175.534 |
| Direct | 50 | 500 | 500 / 0 | 96.106 / 650.011 / 1039.039 | 244.193 |
| Gateway | 50 | 500 | 500 / 0 | 395.450 / 1291.600 / 2161.422 | 93.524 |

100,000 policy-only decisions: p50/p95/p99 **5.496 / 9.370 / 10.396 microseconds**. 300 durable EventStore appends (including serialization, connection and commit): **2.461 / 2.753 / 3.281 ms**. Append p50/p95/p99 under the actual gateway load: **2.664/3.058/3.874 ms** at 1, **3.587/10.173/35.962** at 10, **4.663/11.981/36.826** at 50. All 1509 gateway requests including warm-ups have paired durable ALLOW/completion, 3018 total synthetic hits, and no internal token in SQLite. The JSON result is .aictrl/benchmarks/latest.json (ignored local artifact); benchmark SQLite files are removed afterwards.

Durable SQLite writes materially outweigh generic policy cost; two commits plus the extra HTTP hop form much of the sequential overhead. At concurrency 50, local scheduling/pool/storage contention produces a substantial tail. The direct baseline itself degrades at 50, so the tail is not solely SQLite or native protocol handling. This is local synthetic application-layer overhead, not inferred provider latency, an enterprise throughput guarantee or distributed deployment proof. No speculative policy index, shared persistent SQLite writer, async admission, weakened fsync or retry was introduced.

Measurement diagnostics were handled openly: the initial proto=0 listener skipped asyncio TCP_NODELAY, giving direct p50 45.019 ms and gateway 50.654 ms at concurrency 1 despite no provider delay. A short direct-only probe confirmed about 42 ms and client TCP_NODELAY=1; inspection of pinned asyncio identified the server socket protocol check. Only the benchmark listener now requests IPPROTO_TCP. The next run measured direct/gateway p50 1.917/10.531 ms, but reported **499 successful / 1 transport failure** at gateway concurrency 50 and exited nonzero. Fresh downstream pools for independent cohorts remove stale cross-phase connections from the experiment; the final run above has zero failures without retries. Diagnostic JSON remains in ignored initial-proto-zero.json and shared-client-pools.json alongside latest.json. No failed request was silently reclassified as success and production networking was unchanged.

### Scalability and T06 boundary

The implementation remains a local per-session agent/gateway/proxy/private network on one Docker host, with local SQLite, one active lease per provider-state identity, no distributed session registry and no horizontal orchestration. It favors strong isolation and demo reliability over density for thousands of agents. These constraints are now deployment/storage boundaries rather than provider-specific control logic.

A possible enterprise deployment would need stateless shared gateway replicas, a trusted distributed identity/session service, coherent policy snapshots/cache, acknowledged transactional EventSink (for example a future Postgres/Kafka backend), and protected auth state per user/principal or short-lived credentials from a broker. None exists in this checkpoint. Security-critical admission/BLOCK stays synchronous; only separate noncritical telemetry/counters/dashboard samples could later be batched. ARCHITECTURE.md describes these as future work.

T06 deterministic guards and Jev semantic evaluation belong in src/aictrl/gateway/control.py after bounded native validation and before durable ALLOW/upstream, once for both providers. MCP should implement/reuse src/aictrl/gateway/protocols.py NativeProtocolHandler and shared control/event boundaries with MCP-specific native transport; AgentProtocol has no MCP wire variant yet, so T06 must make a coordinated contract decision. No guards, PII/secrets, Jev, MCP, budgets/rate limits, reload, dashboard or automatic response were implemented. No unresolved T05H blocker remains. T01–T05 and T05H are COMPLETE; T06 remains TODO and must not start automatically.


### T05H file inventory

Added (8):

- `scripts/benchmark-gateway.py`
- `src/aictrl/gateway/control.py`
- `src/aictrl/gateway/protocols.py`
- `src/aictrl/gateway/registry.py`
- `src/aictrl/reporting/sink.py`
- `src/aictrl/runtime/registry.py`
- `tests/unit/test_architecture.py`
- `tests/unit/test_gateway_benchmark.py`

Modified (37):

- `AGENTS.md`
- `ARCHITECTURE.md`
- `Makefile`
- `NOTES.md`
- `OPEN_SOURCE.md`
- `README.md`
- `REUSE_DECISIONS.md`
- `TASKS.md`
- `config/policy.yaml`
- `docker/compose.yaml`
- `docker/images.lock.json`
- `scripts/qualify-codex.py`
- `scripts/verify-codex-boundary.py`
- `scripts/verify-gateway-boundary.py`
- `scripts/verify-runtime-boundary.py`
- `src/aictrl/adapters/base.py`
- `src/aictrl/adapters/claude.py`
- `src/aictrl/adapters/codex.py`
- `src/aictrl/adapters/demo.py`
- `src/aictrl/gateway/anthropic.py`
- `src/aictrl/gateway/app.py`
- `src/aictrl/gateway/responses.py`
- `src/aictrl/gateway/session.py`
- `src/aictrl/policy/engine.py`
- `src/aictrl/policy/loader.py`
- `src/aictrl/policy/models.py`
- `src/aictrl/reporting/store.py`
- `src/aictrl/runtime/compose.py`
- `src/aictrl/runtime/integration.py`
- `src/aictrl/runtime/supervisor.py`
- `tests/fixtures/gateway_factory.py`
- `tests/unit/test_codex.py`
- `tests/unit/test_gateway.py`
- `tests/unit/test_gateway_runtime.py`
- `tests/unit/test_policy.py`
- `tests/unit/test_responses.py`
- `tests/unit/test_runtime.py`

Shared contracts, dependency lock and native/bootstrap/firewall/proxy/profile source were unchanged. Local audit, provider state, diagnostic benchmark artifacts and images were not published as repository files.

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
