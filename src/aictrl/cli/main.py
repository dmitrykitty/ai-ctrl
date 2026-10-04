from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from aictrl.cli.doctor import inspect_environment
from aictrl.runtime.auth import AuthenticationCheckError
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import run_agent, run_claude
from aictrl.runtime.workspace import PROJECT_ROOT
from aictrl.runtime.config import load_config
from aictrl.reporting.store import EventStore, StoreFailure
from aictrl.runtime.integration import verify_claude
from aictrl.governance.approvals import ApprovalManager
from aictrl.governance.store import ApprovalRecord, GovernanceStore

app = typer.Typer(help="AI Control Layer — isolated coding-agent supervisor.", no_args_is_help=True)


def governance(project: Path) -> GovernanceStore:
    project = project.resolve()
    settings = load_config(project)
    path = project / settings.gateway.audit_directory / 'events.sqlite3'
    if not path.is_file():
        raise ValueError('No governance records stored yet.')
    return GovernanceStore(path)


def safe_approval(record: ApprovalRecord) -> str:
    item = record.approval
    return (f'{item.approval_id} session={item.session_id} request={item.request_id} '
            f'state={item.state} policy={item.policy_version} operation={record.operation_id} '
            f'requested={item.requested_at.isoformat()} expires={item.expires_at.isoformat()}')


@app.command()
def approvals(session: Annotated[UUID | None, typer.Option(help='Filter by managed session.')] = None,
              project: Annotated[Path, typer.Option(help='Protected control project directory.')] = PROJECT_ROOT) -> None:
    """List safe request-bound approvals; arguments and digests are withheld."""
    try:
        records = ApprovalManager(governance(project)).list(session)
        for record in records:
            typer.echo(safe_approval(record))
        if not records:
            typer.echo('No approvals.')
    except (ValueError, StoreFailure):
        typer.echo('Approval store unavailable.', err=True)
        raise typer.Exit(2) from None


def decide_approval(approval_id: UUID, project: Path, *, approve: bool) -> None:
    try:
        manager = ApprovalManager(governance(project))
        record = manager.approve(approval_id) if approve else manager.deny(approval_id)
        if record is None:
            typer.echo('Approval not found.', err=True)
            raise typer.Exit(1)
        typer.echo(safe_approval(record))
        expected = 'APPROVED' if approve else 'DENIED'
        if record.approval.state != expected:
            raise typer.Exit(1)
    except (ValueError, StoreFailure):
        typer.echo('Approval store unavailable.', err=True)
        raise typer.Exit(2) from None


@app.command()
def approve(approval_id: Annotated[UUID, typer.Argument(help='Exact pending approval UUID.')],
            project: Annotated[Path, typer.Option(help='Protected control project directory.')] = PROJECT_ROOT) -> None:
    """Approve one pending request until its original expiry; never execute it."""
    decide_approval(approval_id, project, approve=True)


@app.command()
def deny(approval_id: Annotated[UUID, typer.Argument(help='Exact pending approval UUID.')],
         project: Annotated[Path, typer.Option(help='Protected control project directory.')] = PROJECT_ROOT) -> None:
    """Deny one pending request without executing it."""
    decide_approval(approval_id, project, approve=False)


@app.command()
def budgets(project: Annotated[Path, typer.Option(help='Protected control project directory.')] = PROJECT_ROOT) -> None:
    """Show safe persisted counters, including conservative reservations."""
    try:
        for item in governance(project).budgets():
            typer.echo(item.model_dump_json())
    except (ValueError, StoreFailure):
        typer.echo('Budget store unavailable.', err=True)
        raise typer.Exit(2) from None


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
    agent: Annotated[str, typer.Argument(help="Agent adapter: claude, codex or demo-agent.")],
    workspace: Annotated[Path, typer.Argument(help="Workspace directory.")],
    prompt: Annotated[str | None, typer.Option(help="Print-mode prompt sent on stdin; omitted for interactive mode.")] = None,
    timeout: Annotated[int | None, typer.Option(help="Shorter host wall-clock limit in seconds.")] = None,
) -> None:
    """Launch a real agent with enforced egress and host-owned cleanup."""
    if agent not in ('claude', 'codex', 'demo-agent'):
        typer.echo('Unsupported agent. Available adapters: claude, codex, demo-agent.', err=True)
        raise typer.Exit(2)
    try:
        result = (run_claude(workspace, PROJECT_ROOT, prompt=prompt, timeout=timeout) if agent == 'claude'
                  else run_agent(agent, workspace, PROJECT_ROOT, prompt=prompt, timeout=timeout))
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


@app.command()
def verify(
    agent: Annotated[str, typer.Argument(help="Real agent to qualify (claude).")],
    workspace: Annotated[Path, typer.Argument(help="Workspace directory.")],
) -> None:
    """Prove real inference, policy denial and blocked bypass in one session."""
    if agent != 'claude':
        typer.echo('Integration proof supports claude only.', err=True)
        raise typer.Exit(2)
    try:
        proof = verify_claude(workspace, PROJECT_ROOT)
    except (AuthenticationCheckError, RuntimeFailure, StoreFailure, ValueError, OSError):
        typer.echo('T04 integration unavailable. Check authentication, configuration, Docker and audit storage.', err=True)
        raise typer.Exit(2) from None
    for line in proof.lines():
        typer.echo(line)
    raise typer.Exit(0 if proof.passed else 1)
