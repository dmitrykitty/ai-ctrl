from pathlib import Path
from typing import Annotated

import typer

from aictrl.cli.doctor import inspect_environment

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
) -> None:
    """Launch an agent (implementation begins in milestone T02)."""
    typer.echo("runtime not implemented yet — milestone T02", err=True)
    raise typer.Exit(2)
