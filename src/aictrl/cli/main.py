from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from aictrl.cli.doctor import inspect_environment
from aictrl.runtime.auth import AuthenticationCheckError
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import run_claude
from aictrl.runtime.workspace import PROJECT_ROOT
from aictrl.runtime.config import load_config
from aictrl.reporting.store import EventStore, StoreFailure

app = typer.Typer(help="AI Control Layer — isolated coding-agent supervisor.", no_args_is_help=True)


@app.command()
def doctor(
    project: Annotated[Path, typer.Option(help="Project root containing config/project.yaml.")] = Path("."),
) -> None:
    """Check foundation prerequisites without starting containers."""
    typer.echo("AI Control Layer doctor\n")
    checks = inspect_environment(project.resolve())
    for check in checks:
        typer.echo(f"[{check.status}] {check.name}: {check.detail}")
    if any(check.status == "FAIL" for check in checks):
        raise typer.Exit(1)


@app.command()
def run(
    agent: Annotated[str, typer.Argument(help="Agent adapter, e.g. claude or demo-agent.")],
    workspace: Annotated[Path, typer.Argument(help="Workspace directory.")],
    prompt: Annotated[str | None, typer.Option(help="Print-mode prompt sent on stdin; omitted for interactive Claude.")] = None,
    timeout: Annotated[int | None, typer.Option(help="Shorter host wall-clock limit in seconds.")] = None,
) -> None:
    """Launch real Claude with enforced egress and host-owned cleanup."""
    if agent != 'claude':
        typer.echo('Unsupported agent. T03 supports claude; demo-agent scenarios remain a later fixture.', err=True)
        raise typer.Exit(2)
    try:
        result = run_claude(workspace, PROJECT_ROOT, prompt=prompt, timeout=timeout)
    except (AuthenticationCheckError, RuntimeFailure, ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    raise typer.Exit(result)


@app.command()
def events(session: Annotated[UUID, typer.Option(help="Managed session UUID.")]) -> None:
    """Show safe durable events for one session."""
    try:
        settings = load_config(PROJECT_ROOT)
        path = PROJECT_ROOT / settings.gateway.audit_directory / 'events.sqlite3'
        if not path.is_file():
            typer.echo('No audit events stored yet.')
            return
        for event in EventStore(path).events(session):
            typer.echo(event.model_dump_json())
    except (ValueError, StoreFailure) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
