# T06 — Guards, Jev semantic control, MCP authorization and protected memory

T06 STATUS: **PASS — Codex regression explicitly deferred by the user**. Guards/Jev/MCP/stateless demo implementation and offline qualification pass. Real Jev and the production MCP attack demo pass. Native Claude returns the exact reply with durable completion and a disclosed email redaction. Real Codex remains blocked by guard.output.invalid; this is an unresolved regression, not a successful qualification. After confirming Claude works, the user authorized closing T06 while deferring Codex, then explicitly instructed: “Domknij T06; T07 podam osobno.” T07 remains TODO.

Qualification began 2026-10-03 UTC and continued after midnight 2026-10-04 Europe/Berlin. One implementing agent owned the milestone; no delegation or later milestone was started. After closure, the user explicitly authorized committing the T06 changes and pushing them to origin. The approved external-Jev amendment is recorded in plan.md.

## Guards

| Required item | Implementation / evidence |
|---|---|
| GuardEngine | One engine shared by Anthropic, Responses and MCP; secrets → PII → relevant external semantics |
| Inspection model | Ephemeral InspectionSegment: source, JSON path, mutability, untrusted-external flag and RAM-only text; shared contracts unchanged |
| Secret signatures | PEM private-key headers; AWS AKIA/ASIA IDs; OpenAI/Anthropic/GitHub token patterns; conservative Bearer tokens; AICTRL_SECRET_ marker. Stable IDs, no entropy classifier |
| Secret input | BLOCK before upstream/backend/Jev; tests prove zero side effects and zero semantic calls |
| Secret output | BLOCK before releasing a complete native unit/MCP result; split-delta and escaped-JSON tests pass |
| PII implementation | Presidio selected recognizers directly; no AnalyzerEngine, NLP pipeline or downloaded model. Email pattern avoids remote public-suffix lookup; cards use Luhn; phone regions US/GB/DE/FR |
| Supported entities | EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD |
| Input redaction | Typed markers, deterministic overlap resolution, reverse offsets; immutable/unsafe-to-rewrite PII blocks. Native selected fields rewritten; MCP backend receives redacted arguments |
| Output policy | PII BLOCK, no risky output rewriting |
| Raw persistence | No segment/prompt/tool/result/semantic payload or auth/token in AICTRL SQLite/events/logs; synthetic SQLite/caplog/client checks and live-key absence checks. Accepted native provider state remains the existing credential/history exception |

GuardResult contains safe IDs, action/reason, severity and measured latency; it never contains text. Aggregation is BLOCK > REQUIRE_APPROVAL > REDACT > ALLOW. No approval implementation is added.

## Semantic / Jev

| Required item | Value / evidence |
|---|---|
| Provider abstraction | SemanticDecisionProvider; production JevSemanticProvider; explicitly injected test fixtures only |
| API origin | Fixed `https://api.typesafe.ai/v1/systemone`; verified against the [official schema](https://api.typesafe.ai/openapi.json) |
| Model | Configured alias jev-latest; live response resolved to jev-1.13.0 |
| Question types | Three named noul probability questions in one request |
| Questions | prompt_injection, data_exfiltration, security_bypass |
| Thresholds | Each 0.85 inclusive, validated policy-controlled values |
| Timeout | 2500 ms end-to-end, explicit client timeouts; no retry/redirect/fallback |
| Maximum input | 32768 text characters and 256 segments; over-limit BLOCK without truncation; response bounded to 64 KiB |
| Key handling | Host AICTRL_JEV_API_KEY → private session directory → 0400 file → gateway-only read-only `/run/secrets/aictrl/jev_api_key`; no container environment value, agent/proxy/workspace/policy/audit/log access |
| Secret-before-Jev | Synthetic input/output signatures block with zero fake/HTTP semantic calls |
| PII-before-Jev | Fake provider and native Responses follow-up see typed redaction; MCP execution/result checks see the marker |
| Irrelevant content | Direct user/system content and ordinary native model output cause zero semantic calls; untrusted native tool outputs/MCP results/resources are subjects |
| Error behavior | Missing key, timeout, authentication/quota/HTTP/redirect failure, invalid answer/type/shape/usage, NaN/out-of-range, oversize or unexpected exception → BLOCK |
| Real qualification | PASS: exactly one safe and one malicious synthetic request; no actual workspace content in these two requests |

The host key was initially absent, so the first verify-jev correctly reported PENDING and made zero calls. The user then supplied it through a private host `.env` input file outside the repository (0700 parent/0600 file). It was loaded into host subprocess environment without displaying its value. Production containers receive only the staged read-only gateway file. After the final authorized attempt, the temporary input file and its directory were removed; no persistent key configuration was created. A future run needs AICTRL_JEV_API_KEY securely supplied in the host environment again.

| Live case | Model | Probabilities: injection / exfiltration / bypass | Latency | Tokens input / output | Result |
|---|---|---|---:|---:|---|
| Synthetic safe document | jev-1.13.0 | 0.04 / 0.03 / 0.02 | 371.170 ms | 404 / 62 | ALLOW, PASS |
| Synthetic indirect injection | jev-1.13.0 | 0.98 / 0.99 / 0.99 | 260.728 ms | 418 / 62 | BLOCK, PASS |

These are two external end-to-end measurements, not latency percentiles or a throughput guarantee. Live probabilities/model/usage are safe qualification metadata; state/questions/auth are not persisted. External Jev is the approved replacement for the earlier Ollama/LiteLLM plan. Recognizers/signatures cannot remove every sensitive value: residual unrecognized text can reach TypeSafe, and service availability is an explicit dependency.

## Native LLM input and output

Anthropic extraction covers system text, message text/text blocks, tool_use arguments and nested tool_result content. Responses covers instructions, input string/messages/text, replayed function/custom-tool arguments and function/custom-tool outputs. Tool outputs carry untrusted provenance; user intent remains separate. Native handlers own extraction and framing; GuardEngine has no provider shape branches.

Safe input remains byte-for-byte original, including unknown fields/query/header behavior. Actual redaction alone serializes modified JSON. Durable REDACT then ALLOW must both commit before forwarding; separate failure tests prove no upstream on either failure. The Responses redaction check also proves the semantic provider sees only the marker and matching call IDs/unrelated fields survive.

| Required output item | Behavior / proof |
|---|---|
| Anthropic buffering | Complete content blocks, including text/thinking and assembled input_json_delta arguments |
| Responses buffering | Complete native output items with index/item-ID/call-ID association; delta-first, done-only complete snapshots, nullable reasoning content, custom-tool input and summary/content deltas |
| Interleaving | Retain original ordered group until all active units close; ambiguous unidentified deltas fail closed |
| Limit | 1 MiB raw buffered unit/group and 30 seconds; heartbeat traffic does not evade the deadline |
| Split-secret proof | Both protocols, network widths 1/7/65536, split secrets/PII and decoded escaped tool arguments; unsafe unit never emitted |
| Safe bytes | Original raw frames, pings and order preserved after checks; complete JSON output/errors bounded and checked |
| Failure | Invalid/oversize/timeout/incomplete/compressed output withheld; no silent truncation or opaque fallback |
| Completion | Admission ALLOW → output BLOCK → llm.output_blocked AUDIT, no success; explicit transport error stays failed even after terminal evidence. Safe client close after a native terminal can still complete |

The first live Codex attempt failed closed with guard.output.invalid. The [pinned Codex parser](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/codex-api/src/sse/responses.rs) confirms item-ID-based fields and complete done-only items; the exact rejected payload was not logged. Nine new safety cases/62 targeted checks covered those variants, and the affected Codex Docker check passed again. A second live attempt still failed closed, so these variants did not establish the exact root cause. Additional offline checks cover generic SSE labels dispatched by JSON type, [DONE] transport sentinels, and null initial argument/text placeholders. Sentinels cannot close an active unit, malformed final arguments/ambiguous deltas still block, and transport labels receive secret inspection. The user explicitly authorized exactly one additional attempt after receiving an explanation; that third attempt also failed with guard.output.invalid. These compatibility corrections have offline evidence but did not resolve the real-provider failure. One separately authorized diagnostic invocation is described below. No raw response was persisted or unchecked output released, and the exact rejected structure/root cause remains unconfirmed.

The user's later diagnostic suggestion led to fixed-vocabulary structural logging: known event/item types, JSON value types, field/array counts, depth at most two, at most 16 known fields per object/four sampled array shapes, byte count and a SHA-256 of the sanitized shape. Unknown event labels, type values and field names are replaced/omitted because they can themselves carry sensitive text. Scalar values, IDs, prompts, arguments, text, authorization and tokens never enter this record. Constant rejection-condition names identify the rejecting check. Shared SecurityEvent schema remains unchanged; diagnostic metadata lives in protected gateway logs and the host's ignored safe report, not arbitrary SQLite event fields.

The separately approved single diagnostic ran without AICTRL_JEV_API_KEY and therefore made no Jev calls. Session **f6ba1fa7-af16-427f-8fc3-3d8169bdb9f7**, request **57a2805e-c4db-4d51-b219-08d7ecf6494d**, native exit **1**: ALLOW **79e54895-d1d4-4106-a8a4-7bf191c71adb**, guard.output.invalid BLOCK **7b88c33f-0d5e-4d60-aa28-24380dd46e29**, llm.output_blocked AUDIT **dc60273a-11e9-4b65-8a06-ac3f812ec739**. No structural record was captured, so this diagnosis did not identify the failing frame. All session resources/host identity were cleaned up. The initial instrumentation covered SSE-parser errors only; final offline-qualified diagnostics now cover every output-block path, non-SSE JSON failures and safe transport classification/header counts. Synthetic duplicate/whitespace/unknown Content-Type examples reproduce the previously uncovered branch; they do not prove the live cause. No additional live diagnostic or final smoke was run after the user deferred Codex. The final diagnostic image is not live-qualified.

Already released safe units cannot be recalled. Detection is per unit/group: text deliberately divided across independently completed units or encoded/binary/image data is outside the demonstrated coverage.

## MCP and protected memory

| Required item | Implementation / proof |
|---|---|
| SDK/version | Official Python SDK v2, mcp==2.3.0 and mcp-types==2.3.0, MIT |
| Transport/endpoint | Lifecycle-managed stateless Streamable HTTP with JSON responses at internal `/mcp`; 1 MiB requests and DNS-rebinding protection |
| Session authentication | Pre-SDK one-header constant-time token/expiry checks; missing/wrong/duplicate/expired tokens block |
| Tools exposed | safe_lookup, echo_contact, poisoned_document |
| Discovery | Exact per-operation policy-filtered tools/list and resources/list |
| Forbidden guess | destructive_delete_all independently BLOCK; backend invocation count stays zero. Backend is counter-only even if called; no deletion code |
| Argument guards | Secrets block before backend; PII is redacted before durable admission/execution; schema validated with jsonschema |
| Result guards | Secret/PII output BLOCK; relevant untrusted result classified by Jev and withheld on injection/error |
| Project memory | memory://project/demo, visible/readable synthetic public fixture |
| Private memory | memory://private/demo, gateway-only synthetic namespace, hidden and independently denied on guessed URI; backend private read count zero |
| Leakage checks | Private sentinel, poison, raw contact, synthetic secret, session token and semantic key absent from client/events/logs/SQLite in focused checks |
| Events | MCP/OUTBOUND/STRUCTURED; same trusted attribution and EventSink. Existing schema-1 Channel.MCP/protocol=null, no enum addition |

Authorization precedes backend invocation/private read. BLOCK is never followed by an ALLOW for that request. Safe backend results receive mcp.backend_completed; withheld results receive BLOCK plus mcp.result_blocked, never successful completion. Safe fixed errors omit backend exception content. SDK initialize/transport operations do not pretend to be backend tool executions.

The backend/memory are deterministic gateway-local demonstration code, not arbitrary enterprise MCP federation or persistent memory storage. Shipped MCP rules belong to demo-agent; native providers retain their existing exact LLM rules.

## Demo-agent and events

Image: aictrl-demo:t06. Trusted RuntimeAgentSpec/DemoAgentAdapter explicitly mark it stateless; no provider volume, authentication or provider lease. Both missing state fields are required for stateless operation, while native agents still require state metadata/reservations. Same workspace/public CA, firewall/readiness, host UID/GID, zero capabilities, NNP, limits and cleanup. The empty external destination list is valid deny-all, with zero DNS for forbidden authorities.

```bash
make demo-image
make verify-demo-boundary
AICTRL_JEV_API_KEY=<secure-host-input> .venv/bin/aictrl run demo-agent demo/project --timeout 90
```

The assignment above denotes a host variable; use silent input as shown in README, never put an actual key in command history. The scripted SDK attack sequence checks discovery; safe lookup; guessed destructive tool/counter zero; secret input; PII redaction; project/private discovery and reads; poisoned-result withholding. It requires no LLM.

Offline Docker qualification: PASS, 27 checks, explicitly synthetic semantic fixture and synthetic mount key, zero live Jev calls. Production demo: **T06 DEMO PASS**, exit 0, live Jev, session **5ea56280-5255-4c0d-a2f5-49011fac925b**, 21 durable events after cleanup.

| Evidence | Safe durable event(s) |
|---|---|
| Forbidden backend never admitted | BLOCK 50df6f5b-8d86-4f76-94e6-65fb981b9d1f; operation.tool.destructive_delete_all |
| Secret argument | BLOCK 657dd231-0d27-4284-8e53-3be1fc78c4a6; guard.secret.detected |
| Contact input | REDACT a64dce38-1b7b-47dc-a60f-94afe5a08bdd → ALLOW 0a47ed11-d072-455c-a30b-ad02e8d1b5f1 → completed 4de88371-f3a5-4651-8cda-4251ce2d3674 |
| Private memory denied | BLOCK fda4e65d-4ebe-4f5a-a248-7691b6082a77; operation.resource.private.read |
| Poison withheld | ALLOW 714d6f5b-b242-49c9-a879-6e94d2294a1d → BLOCK 7e3518ea-44bc-49cc-a028-044b7611f747 → result_blocked 3d457a77-bea6-4601-a551-a1db6a9e5e95 |

All events remain existing safe SecurityEvent schema 1 and live outside agent mounts in SQLite WAL/FULL. EventSink.append is acknowledged durable before execution/send. The raw secret/contact/poison/private memory/provider auth/session token/key are not stored. Kernel bypass denials remain actual probe results, without invented application events.

## Performance

Command: make benchmark-guards. Measured **2026-10-03 21:46:05 UTC**, Python 3.12.15, Linux 7.0.0-34 x86_64/glibc 2.43, Intel i7-10750H, 12 logical CPUs. Each cohort: five warm-ups and 200 samples, perf_counter_ns/nearest-rank percentiles, ordinary synthetic ASCII public code. Zero API/model traffic, no CI timing thresholds. Units below are microseconds.

| Path | 1 KiB p50 / p95 / p99 | 10 KiB p50 / p95 / p99 | 32 KiB p50 / p95 / p99 |
|---|---|---|---|
| Secret only | 73.722 / 76.030 / 79.192 | 687.601 / 719.781 / 730.706 | 2213.817 / 3008.590 / 4056.272 |
| PII only | 204.080 / 220.707 / 228.271 | 1822.048 / 2125.834 / 2744.164 | 5754.480 / 6317.213 / 6418.670 |
| Combined deterministic | 378.705 / 669.797 / 730.503 | 3227.976 / 3331.040 / 3530.626 | 10285.282 / 11064.589 / 11605.653 |
| Explicit fake semantic | 417.693 / 443.847 / 460.189 | 3262.825 / 3559.200 / 3696.857 | 10294.035 / 11187.395 / 11640.110 |

Combined p50 is approximately 0.379/3.228/10.285 ms. Fake-provider timing includes local interface/engine work, not external Jev latency. This is guard CPU overhead, excluding Docker/TLS/HTTP/SQLite/provider cost; it cannot be added mechanically to historical T05H gateway percentiles. Separate real Jev observations are 371.170/260.728 ms for the two synthetic examples. Ignored local artifacts: .aictrl/benchmarks/guards-latest.json and jev-qualification.json.

## Security and live regression

| Check | Result |
|---|---|
| Gateway Docker | 47/47 PASS; native Messages/count_tokens, durable audit, no denied upstream hits, topology/isolation/cleanup |
| Codex Docker | 42/42 PASS initially and after the later affected Responses correction; actual pinned client, function/tool follow-up, raw safe SSE |
| Demo Docker | 27/27 PASS after empty-list startup/probe/packaging corrections; offline fixture clearly labelled |
| Provider leases | 6/6 PASS; second same-provider/auth refused, owner retained, independent native preparations, state preserved |
| Compose | Runtime and both native authentication topologies validate |
| Direct network | Actual direct internet, DNS/TCP/UDP, UDP, IPv6 and native host/sibling bypass checks denied |
| Proxy inference | Claude/OpenAI/ChatGPT denied; demo deny-all also denies TypeSafe |
| Credentials | No host credentials/socket/CA private material; no semantic key in agent/proxy/environment/audit; native provider-volume exception preserved |
| Cleanup | Qualified sessions have no labelled containers/networks/ephemeral volumes or host identity/key directory; workspace/state/audit preserved |
| Claude live | Exact AICTRL_T06_CLAUDE_OK, exit 0, durable REDACT/ALLOW/completion; one actual call |
| Codex live | Three qualification attempts and one separately approved diagnostic failed closed with guard.output.invalid. Diagnostic captured no rejected structure. Regression explicitly deferred by user; no successful live qualification claimed |
| Jev live | Two synthetic examples PASS; production MCP demo PASS |

Claude session **4bce4aa4-2967-4421-8539-4d5dc6d7dae6** has request **0d7e6746-887e-4556-bd39-3fc3b59de637**: REDACT **61b0d16c-e96b-4dc3-865f-9b6c1f2574eb**, ALLOW **3959896f-763a-4ef5-845c-15462fe7d5f1**, completion **2a881296-62ef-4847-995e-e2805c5b9ffb**, at 22:17:49.700/49.705/51.244 UTC. EMAIL_ADDRESS was redacted in native context even though the explicit smoke prompt contained none. No BLOCK/failure occurred and the exact reply passed. This is a disclosed deviation from the requested zero unexpected guard events; the native context was not dumped/captured to identify the value, and no email exception or relaxed guard was introduced.

Final authorized Codex attempt: session **bb81b2a7-53bf-4fa9-b15a-cd1112082617**, request **a143f9e5-f798-4282-9d76-b1b6fb167065**. Durable ALLOW **5bcffe14-3612-4571-9cd1-7170b1837c52** at 22:50:58.074735 UTC was followed by guard.output.invalid BLOCK **e71c2992-71e2-4669-9849-e6ae171c89ef** at 22:51:03.017548 and llm.output_blocked AUDIT **05c45a5e-09b4-4755-aa1d-17d69d2c981a** at 22:51:03.030793 on 2026-10-03 UTC. Native exit 1, no expected AICTRL_CODEX_TOOL_OK response and no successful completion. Four unsupported auxiliary requests stayed policy BLOCK. All session containers/networks/ephemeral volumes and host identity/key directory were removed; the actual key was absent from native output and SQLite. The report wrapper returned zero because it successfully recorded these checks; the native test itself failed. Safe qualification metadata is in ignored .aictrl/qualifications/t06-codex.json, with the first two failures retained separately.

## Tests, dependencies and images

Final make test: **380 passed in 5.02 s**. Relevant targeted loops included 173 initial passes/6 fixture failures, six corrected cases, 73 runtime/adapter checks, 75 native/Jev/MCP/output checks, 13 terminal/argument checks, three Responses redaction cases, four MCP identity cases, 14 proxy destination cases, 11 transport/terminal regressions, 62 Responses cases and 95 combined native framing cases plus two label/privacy checks. Structural diagnostics then passed 48 and 77 focused checks. Six additional non-SSE/transport/production-logging cases are included in the final suite, along with ten prior diagnostic cases. Counts overlap and are not summed. The first full checkpoint had 349 passes/one stream-audit failure; its targeted correction passed, followed by 350 passes. Later live findings justified 359 and 364 checkpoints. After the user deferred Codex, one final checkpoint qualified the finished diagnostics and accepted T06 scope. Documentation edits do not rerun tests.

Restricted test runner hung on asynchronous/threaded streaming tests; a minimal comparison outside it passed. Only task-owned stalled processes were stopped, and affected targeted/full checks ran outside that runner. No production behavior/durability was weakened to address the environment.

New direct pins: MCP 2.3.0 (MIT), Presidio analyzer 2.2.364 (MIT), jsonschema 4.26.0 (MIT). MCP types 2.3.0 and HTTPX2 2.13.1 are SDK dependencies; phonenumbers 9.0.40 and spaCy 3.8.16 are analyzer dependencies. All transitive versions/hashes are frozen in uv.lock; spaCy library is installed but no language model is downloaded. Attribution/notices are retained as detailed in OPEN_SOURCE.md.

| Rebuilt image | Final recorded identity |
|---|---|
| aictrl-gateway:t06 | sha256:82f1b5af26f4d76cad210c914b298178b52f34a9764399f2a093070680eb2008 |
| aictrl-demo:t06 | sha256:9707fb91dc66d4a70a86f11893130a5d6d38696d17c4b99417e254d332c51063 |
| aictrl-proxy:mitm-t02 | sha256:aa7e0d1b9ec3ed70ff68572c4af75d933a5ebb1a288c41c0cf6d1db6232831f6 |

Base, Claude and Codex images were reused unchanged. Only source-changed images were rebuilt; dependency layers remained cached on subsequent framing fixes. Native auth flows/credential files and old full lifecycle/auth-only matrices were not repeated. docker/images.lock.json retains original upstream commit, binary/checksum and MIT attribution pins.

The third qualification used gateway b262f5d43c6ab03419603b7154988ea6f5ba600f33f81227586a673ec18468cf; the diagnostic used 36dde1b6baf5cff69e31f3f33d101617caea8e0ed7ab4c096a593a35a5532feb. The final rebuild adds diagnostic coverage only and changes no admission/guard decision or network boundary; existing Docker/provider checks were not repeated for it.

Policy configuration: **schema 3, version t06**. Shared serialized contracts: **schema 1, byte-for-byte unchanged**, including serialization checks. No distributed gateway, ORM, local model, governance, dashboard, reload or threat-feed service was added.

## Files added

```text
docs/T06_REPORT.md
docker/demo/Dockerfile
scripts/benchmark-guards.py
scripts/demo-image.sh
scripts/diagnose-codex-output.py
scripts/verify-demo-boundary.py
scripts/verify-jev.py
src/aictrl/gateway/audit.py
src/aictrl/gateway/inspection.py
src/aictrl/gateway/mcp_only.py
src/aictrl/gateway/output.py
src/aictrl/gateway/output_diagnostics.py
src/aictrl/guards/engine.py
src/aictrl/guards/jev.py
src/aictrl/guards/models.py
src/aictrl/guards/pii.py
src/aictrl/guards/secrets.py
src/aictrl/guards/semantic.py
src/aictrl/mcp/__init__.py
src/aictrl/mcp/backend.py
src/aictrl/mcp/control.py
src/aictrl/mcp/demo_backend.py
src/aictrl/mcp/server.py
src/aictrl/runtime/secrets.py
tests/fixtures/demo_probe.py
tests/unit/guard_fakes.py
tests/unit/test_guards.py
tests/unit/test_jev.py
tests/unit/test_mcp.py
tests/unit/test_native_guards.py
tests/unit/test_output_diagnostics.py
tests/unit/test_output_guards.py
tests/unit/test_t06_runtime.py
```

## Files changed

```text
AGENTS.md
ARCHITECTURE.md
Makefile
NOTES.md
OPEN_SOURCE.md
README.md
REUSE_DECISIONS.md
TASKS.md
plan.md
config/policy.yaml
config/project.yaml
demo/agent/main.py
docker/base/entrypoint.sh
docker/images.lock.json
docker/proxy/destinations.py
pyproject.toml
uv.lock
scripts/benchmark-gateway.py
scripts/gateway-image.sh
src/aictrl/adapters/base.py
src/aictrl/adapters/demo.py
src/aictrl/cli/doctor.py
src/aictrl/cli/main.py
src/aictrl/gateway/anthropic.py
src/aictrl/gateway/app.py
src/aictrl/gateway/control.py
src/aictrl/gateway/protocols.py
src/aictrl/gateway/registry.py
src/aictrl/gateway/responses.py
src/aictrl/gateway/session.py
src/aictrl/gateway/sse.py
src/aictrl/guards/__init__.py
src/aictrl/policy/loader.py
src/aictrl/policy/models.py
src/aictrl/runtime/compose.py
src/aictrl/runtime/config.py
src/aictrl/runtime/registry.py
src/aictrl/runtime/supervisor.py
tests/fixtures/gateway_factory.py
tests/security/test_runtime_destinations.py
tests/unit/test_architecture.py
tests/unit/test_gateway.py
tests/unit/test_policy.py
tests/unit/test_responses.py
```

## Known limitations and T07 starting point

Codex compatibility is deferred under the user's explicit acceptance change. When separately resumed, first observe the failing structural condition without raw output using `env -u AICTRL_JEV_API_KEY .venv/bin/python scripts/diagnose-codex-output.py --live`; this command makes one real invocation and never retries. After a proven minimal correction and synthetic regression, real qualification needs a securely supplied host key and `.venv/bin/aictrl run codex demo/project --prompt 'Read demo_codex.txt using a local tool and reply with exactly its content and nothing else.' --timeout 90`. Restoring Codex requires the exact response, real tool-result/Jev-safe follow-up, correlated durable admission/completion and cleanup. No remaining live authorization is active and no automatic retry is scheduled. Claude's additional email redaction remains a disclosed deviation from the original zero-unexpected-guard expectation; its exact response/completion passed, and the user accepted proceeding with Claude.

Secret signatures and three PII recognizers are bounded deterministic coverage, not universal data-loss prevention. Native text/decoded arguments are guarded; arbitrary binary/media/encoding and cross-completed-unit values are not qualified. Output buffering adds latency, and earlier safe units cannot be recalled. Jev is external, probabilistic, policy-thresholded and fail-closed; two synthetic samples do not establish general classifier accuracy. Protected memory/backend are local synthetic fixtures. Native local shell/filesystem execution stays within Docker and is not converted into MCP authorization. SQLite/local per-session topology remains the MVP deployment limit.

T07 has not started. Its exact remaining work is atomic budget reservation/settlement and runaway limits; request-bound expiring approvals; atomic policy/threat-feed reload. In ControlPipeline, reserve after input guards/durable REDACT and before durable ALLOW/upstream; settle correlated actual usage/errors/cancellation. In MCP, approve/reserve after authorization/argument guards and before ALLOW/backend dispatch, with equivalent governance for resource reads. Replace static validated PolicyEngine snapshots with coordinated versioned reload. Dashboard/counters/risk/local-alert restriction/termination remain T08. Stop here.
