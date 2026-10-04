# T09 — Full verification and demo preparation

**COMPLETE, 2026-10-04.** One agent, no delegation. The current local T07 implementation was preserved. T08 reporting/response remains qualified. No real Codex invocation or compatibility investigation occurred.

**make verify-final** is the single offline judge. It orchestrates existing make test, verify-governance, verify-reporting, Compose validation, native gateway Docker boundary, demo MCP boundary, fully synthetic Responses/Codex Docker boundary, governance Docker/host CLI and owned response Docker proofs. Child environments remove the Jev key; neither real native Claude/Codex nor external Jev is called. It records only stage identifiers, exit codes, elapsed times, safe counts and privacy/cleanup booleans, and stops at the first failure without retry. Required real-provider proofs are deliberately separate.

T09 judge **PASS in154.15s**:

| Stage | Result |
|---|---|
| Full offline suite | 470 passed9.36s |
| Governance/reload/usage | 55 passed |
| Reporting/dashboard/integration | 30 passed |
| Compose | Runtime and both auth manifests valid |
| Actual native gateway boundary | 47/47 |
| Actual stateless MCP boundary | 27/27 |
| Synthetic Responses/Codex boundary | 42/42; zero real Codex calls |
| Actual governance/host CLI/reload demo | 33/33 |
| Actual restrict/terminate/cleanup | 27/27 |
| Safe data and cleanup | All checks passed, including in-memory actual-key comparison |

Deterministic failure coverage:

| Failure | Evidence / resulting behavior |
|---|---|
| Invalid initial policy | test_final_failures refuses startup before any container launch; fixed error, no private YAML |
| Invalid policy/feed reload | test_reload and governance Docker retain last good independently without gateway restart |
| Audit/governance unavailable | test_gateway, test_mcp, test_governance_integration deny protected dispatch |
| Semantic unavailable | test_jev, test_guards, native/MCP tests BLOCK relevant untrusted text |
| Provider unavailable | test_gateway records fixed safe failure; no exception content exposed |
| MCP backend unavailable | test_final_failures records mcp.backend_failed and withholds private exception |
| Reporting/risk write unavailable | test_reporting_integration prevents provider dispatch |
| Alert response fails/foreign ownership | test_reporting leaves incomplete and never mutates foreign Docker session |
| Dashboard read unavailable/malformed row | test_dashboard/test_reporting safe 503/error shell and retry |
| Restrict/terminate | Real Docker proof removes path/stops agent; terminal state/completion survives cleanup |
| Demo reset active/shared accounting | Three targeted tests prove refusal rolls back and native/workspace history remains |

**Real Claude PASS**, session **44a58b6d-c9f5-4e6c-b83c-e97ef3c3898a**: exact AICTRL_FINAL_OK, exit0, durable ALLOW/completion, request/step/token reservation and SETTLED usage, TERMINATED lifecycle, no BLOCK/critical alert, separated persisted latency and cleanup. Observed usage: input21514/output15, subscription money unknown. One context email redaction is disclosed; its value is not recorded. Deterministic38.448ms, governance12.311ms, complete upstream stream1598.799ms, total1662.423ms (n1; not a benchmark). This fixed prompt has no untrusted external text, so no semantic call/sample is fabricated. No real retry was needed.

**Real Jev/MCP governance PASS**, session **bb963658-5f32-424a-80fb-1850c34e4791**: production factory/fixed Jev transport, existing exact-request approvals, budgets, feed reload, runaway, safe audit and cleanup **33/33**. An additional reporting assertion confirms separate semantic samples. Jev latency n4: p50 **246.327ms**, p95/p99 **635.070ms**; deterministic n12 p50 **0.215ms**, p95 **2.663ms**. Four backend completions,35 safe events. This is a production semantic-path regression, not a new model accuracy benchmark; T06 malicious classification evidence remains in its historical report. One successful live attempt; the preserved private host key was read in RAM and staged only gateway-side.

**make demo-ready** checks Python/lock, daemon, recorded existing images, read-only native Claude authentication, validated policy/feed, protected audit writes, local assets, loopback port and active managed sessions. It installs/rebuilds nothing, prints exact remedies, and passed14 checks in **0.722s**. **make demo-rehearsal** passed in **76.255s**: guard18.003s, governance20.786s, response37.449s (rounded). Actual Docker/official MCP SDK/SQLite and host CLI create safe representative history labelled offline-demo; only semantic assessment is an explicitly injected fixture. Production policy is never rewritten. The response demonstrations run last. No live LLM/Jev needed.

**make demo-reset** selects only host-labelled terminal offline-demo sessions in one transaction and deletes their safe event/alert/lifecycle and session-only governance rows. It refuses active or shared user/agent/profile accounting. Native/live-demo/legacy history, workspace/source and provider volumes are never selected or touched. A lock excludes concurrent rehearsals/resets. No Docker mutation is used.

Privacy checks read only known safe audit/WAL/qualification files and source, never native auth contents. Known synthetic secret/PII/poison/private-memory/provider/internal-token markers are absent from persisted data. The actual Jev key is compared in memory when AICTRL_JEV_KEY_FILE selects its private host input; only a boolean is reported. This optional path is not passed to judge children and no credential is required for an offline judge. All session-labelled containers/networks/volumes and managed temporary identity/key directories are absent. Provider volumes, project workspace, durable audit and the user's requested host key input are preserved.

New host scripts: demo-ready.py, demo-rehearsal.py, demo-reset.py, final-checks.py, verify-final.py, qualify-claude-final.py. Existing T06/T07 proof clients/gateway fixtures and production boundary are reused. New tests: test_demo_reset.py, test_final_failures.py. Makefile/README/config milestone and coordination/reuse notes are updated. No new dependency, provider, service or enforcement architecture is added. Policy schema5/shared schema1 remain unchanged.

Artifacts under .aictrl/qualifications: t09-final-judge.json, final-claude.json, final-jev.json, demo-ready.json, demo-rehearsal.json, final-privacy-cleanup.json. Reports contain safe metadata only. Image identity remains the T08 source-qualified gateway/demo images; native/base/proxy images are reused.

Continue immediately to **T10 FEATURE FREEZE**: one clean start, warm measurements, representative visual inspection, obvious reliability/UX fixes only, repository hygiene and the final offline judge. T11 remains TODO.
