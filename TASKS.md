# Implementation backlog

Owner for every task: single implementing agent. Dependencies and acceptance follow `plan.md` and the supplied T1/T02 instruction. T01 cleanup and T02 are complete. The user requested closing T02 and moving onward; T03 is next.

| ID | Description | Dependencies | Status | Acceptance criteria | Affected modules |
|---|---|---|---|---|---|
| T01 | Contracts, reused assets, images, authentication | None | COMPLETE | Python 3.12.15/uv/lock ready; 40 offline tests and 10 real authentication-boundary probes pass; pinned actual Claude 2.1.285 verified; dedicated state persistence verified; native status reports authenticated; repeated login exits 0 without a new browser flow. Project environment prefix standardized; security boundary preserved. Coordination and MIT reuse records updated. | adapters, cli, contracts, docker, config, scripts, tests, docs |
| T02 | Launcher and isolation | T01 | COMPLETE | Actual Claude 2.1.285 starts interactively and returns AICTRL_OK through controlled egress; UID/GID 1000:1000, all capability sets zero, workspace read/create/edit verified; 87 offline tests and real runtime boundary/lifecycle probes pass; limits, default deny, state preservation, signals, timeout, concurrency and no-leak cleanup verified. Destination-only TLS coverage documented. | runtime, adapters, cli, docker, config, scripts, tests, docs |
| T03 | First native gateway path | T02 | TODO | Claude subscription receives a real model response through gateway; policy and SQLite events work | gateway, policy, reporting |
| T04 | Required integration proof | T03 | TODO | Allowed request succeeds, denied request and direct bypass fail; events identify real-agent session | runtime, gateway, reporting, tests |
| T05 | Second adapter or fallback completion | T04 | TODO | Timeboxed Codex integration if Claude is healthy; otherwise complete selected real-agent path first | adapters, gateway, runtime |
| T06 | Guards and MCP | T04 | TODO | Secrets, PII, semantic/output checks, native tool loop, filtered tools, protected memory | guards, gateway, policy, demo, tests |
| T07 | Governance and reload | T06 | TODO | Atomic budgets, request-bound expiring approvals, policy/feed reload, runaway limits | governance, policy, reporting, tests |
| T08 | Reporting and response | T07 | TODO | Dashboard, counters, latency, explainable risk, local alerts, restriction/termination | reporting, dashboard, runtime, governance |
| T09 | Full verification | T06, T07, T08 | TODO | Offline judge suite, recorded real-agent qualification, failure tests, documentation, offline preparation | tests, scripts, demo, docs |
| T10 | Stabilization | T09 | TODO | Clean-start rehearsal, failures fixed, features frozen | all implemented modules, docs |
| T11 | Submission | T10 | TODO | Rehearsed 3–5 minute demo and maximum ten-slide PDF | docs/submission, demo |
