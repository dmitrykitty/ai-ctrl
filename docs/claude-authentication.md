# Native Claude subscription login

The image contains actual Claude Code 2.1.285 installed with the [official native installer](https://code.claude.com/docs/en/setup). Login uses the native command `claude auth login --claudeai`. No custom OAuth bridge or API key is configured. The subscription is confirmed by the approved plan; account authorization uses the native flow.

```bash
make claude-image
make claude-auth-status
make claude-login
```

The status helper invokes native `claude auth status --json` and displays only its authenticated/unauthenticated result. Its offline container mounts dedicated state read-only; trusted setup reads only directory-owner metadata, then drops to that non-root UID/GID with every capability removed before native status. It exits 0 when authenticated, 1 when unauthenticated, and 2 when the status cannot be checked. `make` turns either nonzero result into a failing target.

Login checks that status first. Already-authenticated state returns success without a terminal or a browser flow. Only unauthenticated state proceeds to the existing restricted flow; a status error aborts. Use an interactive host terminal for new authentication. Open the authorization URL printed by the CLI in your host browser. Follow the provider's sign-in/consent flow and enter any returned code only in that terminal. Do not put codes, tokens, or credentials in chat, project configuration, or platform logs. The command has a ten-minute timeout; rerun it if the flow expires. Cancellation preserves state and removes the temporary proxy/network containers.

The helpers use `aictrl-claude-state` at `/home/dev/.claude`, with `CLAUDE_CONFIG_DIR` set to the same path. State uses directory mode 0700. Restricted login prepares UID/GID 501; normal runtime prepares the positive host identity (verified 1000:1000). Status follows the existing directory owner without modifying it. They mount no host home/configuration directory and no workspace. They refuse an active provider-state container; status and login share a fixed container name to prevent overlapping authentication operations.

Provider authentication state can exist inside the dedicated agent state volume because the selected agent requires it. Enterprise resource credentials must never be placed there. The agent may access its own provider authentication/history. Ordinary shutdown does not delete that volume. Credential deletion is a separate explicit operation; no cleanup command here removes provider state.

## Authentication network coverage

The agent joins only an internal Docker network and can reach the authentication proxy's designated IPv4 address on TCP 8080. The trusted bootstrap blocks direct internet, embedded/external DNS, IPv6, UDP, and unrelated container destinations, then drops all capability sets and switches to `dev`. No Docker socket is mounted.

The transport permits HTTPS CONNECT only to these exact hosts on port 443:

- `claude.ai` and `claude.com`: subscription sign-in.
- `platform.claude.com` and `console.anthropic.com`: native OAuth/account endpoints, including compatibility with the installed CLI.
- `api.anthropic.com`: native connectivity and account checks during authentication.

These roles were checked against [Anthropic's network requirements](https://code.claude.com/docs/en/network-config) and [authentication documentation](https://code.claude.com/docs/en/authentication). The proxy resolves provider names itself and refuses non-public resolved addresses. TLS remains end-to-end: coverage is explicitly destination and port only. No TLS downgrade occurs. The bootstrap entrypoint accepts only the native login command; it cannot launch an agent or model conversation. Normal runtime uses a separate enforcing mitmproxy transport for declared authentication destinations. T03 routes model inference through its native application gateway and excludes that inference host from the generic runtime proxy.

Updates, optional traffic, and subscription MCP connectors are disabled. Login never inherits host `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, or gateway credentials. Browser traffic stays on the host and does not run in this container.

## Verify without displaying credentials

```bash
make claude-version
make claude-auth-status
make verify-claude-state
make verify-auth-boundary
```

Stop an active provider-state container before these checks. The status helper reports native login state; it does not perform a model request or verify a live subscription response. A not-yet-authenticated status blocks real-agent integration, separate from T01 image and persistence verification. Do not inspect or print the credentials file to verify login.

The Python/socket probes exercise the actual T01 authentication boundary. They qualify only the authentication boundary; real T02 runtime results are recorded separately in `NOTES.md`. T01 status and any observed browser/login blocker are recorded in `NOTES.md`.

## Normal runtime

`aictrl run claude demo/project` checks stored authentication first and refuses unauthenticated/uncheckable state without a browser flow. The active T03 mode sets ANTHROPIC_BASE_URL to the private gateway, preserves native subscription authorization, and adds no gateway API credential. Application inference receives structured admission and safe durable audit; other declared traffic retains destination-only proxy coverage. Native onboarding configuration is prepared after preflight; credentials are not opened by that helper and workspace trust remains interactive. Ordinary runtime cleanup preserves this same dedicated state.
