"""One real-session integration proof using the existing production runtime."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.contracts import SecurityEvent
from aictrl.reporting.store import EventStore
from aictrl.runtime.auth import AuthenticationCheckError, claude_authenticated
from aictrl.runtime.docker import RuntimeFailure, docker
from aictrl.runtime.integration_probe import EXPECTED, PREFIX
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.config import load_config
from aictrl.runtime.workspace import PROJECT_ROOT, validate_workspace


class ProbeResult(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    claude_exit: int = -1
    claude_response: Literal['AICTRL_T04_OK'] | None = None
    forbidden_status: int = -1
    forbidden_request_id: UUID | None = None
    direct_blocked: bool = False
    direct_errno: int | None = None
    proxy_denied: bool = False


@dataclass(frozen=True)
class IntegrationProof:
    session_id: UUID
    probe: ProbeResult
    checks: dict[str, bool]

    @property
    def passed(self) -> bool:
        return all(self.checks.values())

    def lines(self) -> list[str]:
        return ['AICTRL integration proof', '', f'Session: {self.session_id}', '',
                *[f"[{'PASS' if passed else 'FAIL'}] {name}" for name, passed in self.checks.items()],
                '', 'T04 INTEGRATION ' + ('PASS' if self.passed else 'FAIL')]


def parse_result(output: str) -> ProbeResult:
    lines = [line[len(PREFIX):] for line in output.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        return ProbeResult()
    try:
        return ProbeResult.model_validate_json(lines[0])
    except ValidationError:
        # Never echo invalid native/subprocess output or model validation data.
        return ProbeResult()


def aggregate(session_id: UUID, code: int, probe: ProbeResult, events: list[SecurityEvent],
              *, cleanup: bool, provider_state: bool, audit: bool, workspace: bool) -> IntegrationProof:
    attributed = bool(events) and all(event.session_id == session_id and event.agent_id == 'claude'
        and event.adapter == 'claude' and event.channel == 'LLM' and event.direction == 'OUTBOUND'
        and event.protocol == 'ANTHROPIC_MESSAGES' and event.inspection_level == 'STRUCTURED' for event in events)
    allowed_ids = {event.request_id for event in events if event.action == 'ALLOW'
                   and event.request_id is not None and event.reason_code == 'llm.policy.allowed'
                   and 'operation.messages' in event.rule_ids}
    completed = any(event.action == 'AUDIT' and event.reason_code == 'llm.upstream_completed'
                    and event.request_id in allowed_ids for event in events)
    forbidden = [event for event in events if probe.forbidden_request_id is not None
                 and event.request_id == probe.forbidden_request_id]
    blocked = bool(forbidden) and all(event.action == 'BLOCK' and event.reason_code == 'llm.policy.blocked'
                                    and 'operation.unsupported' in event.rule_ids for event in forbidden)
    response = f'Real Claude response: {EXPECTED}' if probe.claude_response == EXPECTED else f'Real Claude response (expected {EXPECTED})'
    checks = {
        response: probe.claude_exit == 0 and probe.claude_response == EXPECTED,
        'Application policy blocked forbidden GET request': probe.forbidden_status == 403 and blocked,
        'Direct internet bypass blocked by sandbox': probe.direct_blocked,
        'Inference CONNECT bypass denied by proxy': probe.proxy_denied,
        'ALLOW event persisted': bool(allowed_ids),
        'AUDIT completion correlated with ALLOW': completed,
        'BLOCK persisted without an ALLOW/upstream event': blocked,
        f'Events attributed to session {session_id}': attributed,
        'Runtime cleanup complete': cleanup,
        'Provider state, workspace and SQLite preserved': provider_state and workspace and audit,
        'Qualification workload exited successfully': code == 0,
    }
    return IntegrationProof(session_id, probe, checks)


def verify_claude(workspace: Path, project: Path = PROJECT_ROOT) -> IntegrationProof:
    selected = validate_workspace(workspace, project)
    settings = load_config(project)
    if settings.runtime.routing_mode != RoutingMode.APPLICATION_GATEWAY:
        raise RuntimeFailure('Integration proof requires APPLICATION_GATEWAY.')
    if not claude_authenticated(settings.claude.image):
        raise AuthenticationCheckError('Claude is not authenticated. Run: make claude-login')
    adapter = ClaudeAdapter(settings.claude.image)
    source = Path(__file__).with_name('integration_probe.py').read_text()
    runtime = RuntimeSupervisor(selected, settings, adapter, project)
    session_id = runtime.session.identity.session_id
    directory = Path(runtime.directory.name)
    code, output = runtime.run(('python', '-c', source), input_text=f'Reply with exactly: {EXPECTED}', capture_output=True)
    probe = parse_result(output)
    resources = []
    for resource in ('container', 'network', 'volume'):
        arguments = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        resources.append(not docker([*arguments, '--filter', 'label=io.aictrl.session=' + runtime.identifier]).stdout.strip())
    provider_state = docker(['volume', 'inspect', adapter.persistent_state_volume, '--format', '{{.Name}}'], check=False).returncode == 0
    audit_path = project / settings.gateway.audit_directory / 'events.sqlite3'
    audit = audit_path.is_file()
    events = EventStore(audit_path).events(session_id) if audit else []
    return aggregate(session_id, code, probe, events, cleanup=all(resources) and not directory.exists(),
                     provider_state=provider_state, audit=audit, workspace=selected.is_dir())
