# Tomorrow's demo

Use the existing checkout and pinned local assets. No rebuild or login is needed for the offline demonstration.

Start in the repository:

```bash
cd /home/dnikitsin-lenovo/repositories/private/goldman_sachs
make demo-ready
```

Start the dashboard in terminal A and leave it running:

```bash
.venv/bin/aictrl dashboard
```

It opens http://127.0.0.1:8787. Add `--no-open` if you prefer opening the browser yourself. Stop it with Ctrl+C. Run the preflight before the dashboard, because it checks that this port is free.

In terminal B, from the same repository:

```bash
make demo-rehearsal
```

Allow about 77 seconds. This uses actual Docker, MCP, SQLite and the host approval CLI, with explicitly offline semantic fixtures. It demonstrates guards, approvals, budgets, reload, risk, alerts, restriction and termination. It creates safe history visible in Sessions, Events, Budgets and Alerts. No live provider or key is needed. Overview's current risk can return to zero when the rolling window expires; historical alerts remain.

Optional real Claude Code, using the saved subscription:

```bash
.venv/bin/aictrl run claude demo/project \
  --prompt 'Reply with exactly: AICTRL_DEMO_OK' \
  --timeout 90
```

This needs provider connectivity. Supply `AICTRL_JEV_API_KEY` securely on the host only if the chosen live path inspects untrusted content with real Jev. The simple prompt above needs no Jev key. Keep secrets outside the repository and chat; the previously supplied private host input is preserved. Runtime key copies are ephemeral and gateway-only.

Optional `make demo-reset` clears only terminal offline-demo history, preserving native history, workspace and authentication. Active or shared-scope accounting makes reset refuse safely.

Real Codex T06+ output compatibility remains deferred. Final offline qualification: `make verify-final`. T11 presentation/submission is not started.
