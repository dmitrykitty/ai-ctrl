# Architecture

`plan.md` is the approved detailed design. This file records the implementation boundary.

The host `aictrl` supervisor controls Docker. Configuration-oriented adapters describe Claude, the deterministic demo agent, and later Codex. The shared runtime owns container lifecycle, session identity, limits, workspace mounts, and isolation. Agents use an internal network; application gateways inspect LLM/MCP/company API traffic, while an enforcing proxy handles generic egress. Only the gateway and proxy join an upstream network. Neither receives the Docker socket.

The Python 3.12 modular monolith separates gateway forwarding, policy, guards, governance, reporting, and dashboard modules. SQLite stores durable events, admission/budget state, and alerts. Shared versioned Pydantic models contain safe metadata, never raw provider credentials or full prompts. Claude uses native Anthropic Messages forwarding; later Codex uses native Responses forwarding.

Provider state is a dedicated Docker named volume, `aictrl-claude-state`, mounted at `/home/dev/.claude`. It may hold the agent's own subscription authentication and native history. Enterprise resource credentials remain outside agents. Ordinary shutdown preserves state. Authentication uses the native CLI and a restricted provider-only bootstrap path, with no custom OAuth bridge.

T01 prepares contracts, pinned runtime assets, images, Compose structure, doctor, and authentication instructions. It does not provide the launcher, application gateway, policy enforcement, or audit store. `aictrl run` must report this explicitly. Runtime service profiles must not silently run unenforced agents while these components are absent.

Future runtime isolation blocks direct internet, host services, sibling containers, DNS, IPv6, and UDP. Trusted setup drops privileges before running the agent. Public CA material is shared with the agent; the CA private key stays exclusively with the proxy. Inspection-required routes fail closed and opaque TLS exceptions are explicit.
