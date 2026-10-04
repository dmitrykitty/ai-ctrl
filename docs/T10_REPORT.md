# Overnight finalization — T08 → T09 → T10

**OVERNIGHT FINALIZATION STATUS: PASS, 2026-10-04.** T07, T08, T09 and T10 are COMPLETE. One implementing agent, no delegation. FEATURE FREEZE was respected; T11 remains TODO. Detailed prior evidence: [T07](T07_REPORT.md), [T08](T08_REPORT.md), [T09](T09_REPORT.md).

## Product and qualified behavior

T07 entry verification passed 55 focused governance/reload/usage tests. Its qualified local source was preserved in commit 5e93c1a. The overnight work keeps the approved shared runtime, native handlers, ControlPipeline, SQLite enforcement, dedicated authentication and Docker boundary. Policy schema is 5, threat feed 1, shared serialized contracts 1. No real Codex invocation or compatibility investigation occurred.

T08 supplies a host-side dashboard:

    .venv/bin/aictrl dashboard

It binds only to 127.0.0.1:8787 and has Overview, Sessions, Events, Policies, Budgets and Alerts, plus session details. Reads use safe selected durable metadata; assets are local Jinja/CSS/vanilla JavaScript/SVG, with no CDN, Node build, external font or frontend service. The dark layout has status badges with text/icons, compact tables, budget progress, filters, pagination and a bounded activity chart. Two-second JSON polling preserves filters, pauses in hidden tabs and reports safe read errors. Keyboard focus, skip link, labelled filters, navigation landmarks, table headings and reduced-motion styles are included.

Counters distinguish requests, BLOCK/REDACT/approval actions, tokens, used/reserved budgets and pending/expired approvals. Latency reports n/p50/p95/p99 separately for deterministic guards, real Jev, governance, full upstream stream, MCP backend and total controlled operation. Unobserved stages remain empty. Risk sums explainable safe rule contributions in the configured rolling window, with validated weights and ordered thresholds. Alerts are durable, use stable rule/severity/session identity and threshold-crossing cooldowns, and retain incomplete response failures.

Only the owning host supervisor performs notify/restrict/terminate after Docker session-label validation. Restriction disconnects the agent's managed network; termination sends the bounded stop signal and cleanup. The gateway/dashboard receive no Docker socket. Real Docker response qualification passed 27/27; restriction removed gateway reachability and termination returned 143 with durable terminal lifecycle/completion. This is actual response enforcement.

The dashboard already contains labelled native, live-demo and offline-demo evidence. The offline rehearsal uses actual Docker, official MCP SDK, governance CLI, protected SQLite and runtime response. Only semantic classification is explicitly injected as an offline fixture; it is outside the production factory. Recorded native Claude and production Jev evidence remains separately identifiable.

## T09 verification and real providers

T09 make verify-final passed in 154.15 seconds: full suite 470, focused governance 55 and reporting 30; valid Compose; Docker gateway 47, MCP boundary 27, fully synthetic Responses 42, governance/host CLI 33 and owned response 27. Privacy and resource cleanup passed. The judge calls no live provider and stops at the first failure.

The deterministic failure matrix covers invalid startup/reload/feed, last-good retention, unavailable audit/governance/reporting stores, semantic/provider/MCP failures, safe dashboard read errors, incomplete alert response, foreign response ownership and eventual response cleanup. T09_REPORT.md maps each failure to its focused tests or Docker proof. The reset tests cover active/shared-scope refusal and preserved native history/workspace.

Final real Claude PASS: session 44a58b6d-c9f5-4e6c-b83c-e97ef3c3898a, exact AICTRL_FINAL_OK, exit 0, durable ALLOW/completion and SETTLED reservation, 21514 input/15 output tokens, lifecycle/latency and cleanup. Subscription money is unknown. One context email redaction is disclosed; no raw value is retained. Observed deterministic 38.448 ms, governance 12.311 ms, upstream full stream 1598.799 ms and total 1662.423 ms, n=1. The fixed trusted prompt caused no Jev sample.

Final production Jev/MCP PASS: session bb963658-5f32-424a-80fb-1850c34e4791, 33 governance checks plus a separate semantic-latency assertion, four backend completions and 35 safe events. Real Jev n=4, p50 246.327 ms, p95/p99 635.070 ms. Deterministic n=12, p50 0.215 ms, p95 2.663 ms. These are observed path measurements, not model accuracy or performance guarantees. Both live trials passed without a retry; they were not repeated for host-only T10 fixes.

## T10 freeze, clean start and polish

T10 changes are limited to reporting correctness, visible labels, refresh reliability, two focused regressions and documentation. Session risk/details now use that session's observed policy. Aggregate Jev latency excludes offline/unavailable fixtures, while fixture session details retain explicit labels. Observation kind, ended-at UTC and full event date are visible. Budget text explains the ledger limit after reload. An unavailable reporting read changes the health label; table polling retains keyboard focus and catches up after focus moves.

One realistic clean start passed with existing pinned assets and saved native state:

| Operation | Measured warm time |
|---|---:|
| make demo-ready | 0.934 s (T09 inner preflight 0.722 s, 14 checks) |
| Dashboard startup and health | 1.634 s |
| Complete make demo-rehearsal | 77.080 s |
| Whole clean start, rehearsal and dashboard stop | 80.012 s |

The rehearsal's inner run was 75.800 s: guards 17.934 s, governance 20.917 s and response 36.928 s. It passed and stopped cleanly. This measures the full rehearsal, rather than presenting it as startup alone. No install, rebuild, authentication reset or live provider call was needed.

Visual inspection covered representative data and all six pages at laptop width 1180×800, plus overview at 1440×900 and 1920×1080. Page width stayed within the viewport; filters retained selected values, session links/details worked, dates/status/versions remained readable and empty/error states were explicit. No redesign, new page, provider, guard, dependency or presentation was added.

A separate ephemeral metadata-only query measurement used 5000 events/100 sessions, five warm reads per view. Maximum observed read times: overview 49.886 ms, sessions 28.080 ms, events 0.996 ms, budgets 0.304 ms, alerts 0.318 ms, policies 0.537 ms. Production history was not modified. These are local query timings, not HTTP/browser/provider benchmarks.

T10 focused reporting checks passed 32 in 3.57 s; the final date/template polish passed 12 dashboard tests in 2.37 s. The final combined offline/Docker judge passed once after stabilization; no unchanged image was rebuilt.

## Privacy, hygiene and limitations

Known safe SQLite/WAL/reports and project-owned source are checked without opening native authentication contents. The actual Jev key is compared only in RAM and never printed. The conservative text scan passed for 192 project-owned files: remaining matches were references or reviewed synthetic fixture values. It records only filenames/line numbers/categories, without actual secret values. Local runtime data, databases, caches, logs, environment files and qualification artifacts remain Git-ignored.

The user-requested private Jev host input remains outside the repository at mode 0600, parent 0700. Gateway-only ephemeral key copies are removed with each session. Native provider volumes, workspace and audit/reporting database are preserved. The final judge confirmed zero session-labelled containers/networks/volumes and zero temporary identity/key staging directories; all privacy checks passed.

Known limits: local single-host dashboard without external authentication; latest durable gateway observation is not a continuous provider-health probe; legacy audit has no invented lifecycle; aggregate latency uses up to 2000 recent samples per stage; full-stream timing includes provider/backpressure; risk expires with the rolling window while historical alerts remain; subscription monetary cost is unknown; request-time token reservation is conservative, with observed usage settled afterward. Demo reset safely refuses shared-scope accounting. Raw payloads and universal local-file auditing are outside scope. Native real Codex T06+ output compatibility remains fail-closed and deferred.

Separate local milestone commits preserve T07, T08, T09 and the final T10 changes. No push is performed; the worktree is clean at closure.

## Tomorrow

The short [DEMO.md](DEMO.md) contains the exact four commands and terminal arrangement:

1. make demo-ready
2. .venv/bin/aictrl dashboard
3. make demo-rehearsal
4. Optional .venv/bin/aictrl run claude demo/project --prompt 'Reply with exactly: AICTRL_DEMO_OK' --timeout 90

## Files added

T08→T10 additions after the preserved T07 checkpoint (5e93c1a); T07 inventory is in T07_REPORT.md.

- demo/agent/response.py
- docs/DEMO.md
- docs/T08_REPORT.md
- docs/T09_REPORT.md
- docs/T10_REPORT.md
- scripts/demo-ready.py
- scripts/demo-rehearsal.py
- scripts/demo-reset.py
- scripts/demo_support.py
- scripts/final-checks.py
- scripts/qualify-claude-final.py
- scripts/verify-final.py
- scripts/verify-reporting-response.py
- scripts/verify-reporting.py
- src/aictrl/dashboard/app.py
- src/aictrl/dashboard/assets/dashboard.css
- src/aictrl/dashboard/assets/dashboard.js
- src/aictrl/dashboard/templates/dashboard.html
- src/aictrl/reporting/models.py
- src/aictrl/reporting/queries.py
- src/aictrl/reporting/risk.py
- src/aictrl/reporting/service.py
- src/aictrl/reporting/timing.py
- tests/unit/test_dashboard.py
- tests/unit/test_demo_reset.py
- tests/unit/test_final_failures.py
- tests/unit/test_reporting.py
- tests/unit/test_reporting_integration.py

## Files changed

- AGENTS.md
- ARCHITECTURE.md
- Makefile
- NOTES.md
- OPEN_SOURCE.md
- README.md
- REUSE_DECISIONS.md
- TASKS.md
- config/policy.yaml
- config/project.yaml
- docker/demo/Dockerfile
- docker/images.lock.json
- plan.md
- pyproject.toml
- scripts/benchmark-gateway.py
- scripts/demo-image.sh
- scripts/gateway-image.sh
- scripts/verify-codex-boundary.py
- scripts/verify-demo-boundary.py
- scripts/verify-gateway-boundary.py
- scripts/verify-governance-demo.py
- src/aictrl/cli/main.py
- src/aictrl/gateway/app.py
- src/aictrl/gateway/audit.py
- src/aictrl/gateway/control.py
- src/aictrl/governance/reload.py
- src/aictrl/mcp/control.py
- src/aictrl/policy/loader.py
- src/aictrl/policy/models.py
- src/aictrl/runtime/config.py
- src/aictrl/runtime/supervisor.py
- tests/unit/test_architecture.py
- tests/unit/test_gateway.py
- tests/unit/test_policy.py
- tests/unit/test_reload.py
- tests/unit/test_responses.py
- uv.lock

## Final test result

**make verify-final PASS — 152.665 seconds**, recorded 02:45:09 UTC on 2026-10-04, exit 0.

| Stage | Result |
|---|---|
| Full offline suite | 472 passed, 9.408 s |
| Focused governance | 55 passed, 3.941 s |
| Focused reporting/dashboard | 32 passed, 4.196 s |
| Compose validation | PASS |
| Actual gateway Docker boundary | PASS, 47 checks |
| Actual MCP Docker boundary | PASS, 27 checks |
| Fully synthetic Responses Docker boundary | PASS, 42 checks; zero real Codex calls |
| Actual governance/host CLI/reload | PASS, 33 checks |
| Actual owned restrict/terminate | PASS, 27 checks |
| Protected metadata and actual-key comparison | PASS |
| All session/identity/key staging cleanup | PASS; native state/workspace preserved |

Nine stages passed. No live dependency is required by the judge; separately recorded real Claude and Jev passed in T09. No additional full suite or live retry followed the final judge. Documentation-only closure does not rerun qualification.

Safe artifacts remain in ignored .aictrl/qualifications: t10-final-judge.json, t09-final-judge.json, final-claude.json, final-jev.json, t10-clean-start.json, t10-reporting-performance.json and t10-repository-scan.json. Exact T08–T10 inventory is 28 added / 37 changed files as listed above. T07's previously local implementation and inventory are preserved separately.

**STOP before T11. No slides, PDF, recording or submission work is started.**
