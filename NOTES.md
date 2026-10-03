# Implementation notes

T1 / repository T02 STATUS: PASS. T01 remains COMPLETE; T02 launcher and isolation COMPLETE. Next milestone: T03, native application gateway. The user requested closing T02 and moving onward; this record covers only the completed T02 scope.

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
