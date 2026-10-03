import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from aictrl.cli.main import app
from aictrl.contracts import SecurityEvent
from aictrl.runtime import integration
from aictrl.runtime.integration import EXPECTED, PREFIX, ProbeResult, aggregate, parse_result
from aictrl.runtime.config import load_config
from aictrl.runtime.workspace import PROJECT_ROOT


def evidence():
    session, allowed, forbidden = uuid4(), uuid4(), uuid4()
    probe = ProbeResult(claude_exit=0, claude_response=EXPECTED, forbidden_status=403,
                        forbidden_request_id=forbidden, direct_blocked=True, direct_errno=113, proxy_denied=True)
    events = []
    for action, reason, request, rule in [('ALLOW', 'llm.policy.allowed', allowed, 'operation.messages'),
                                         ('AUDIT', 'llm.upstream_completed', allowed, 'operation.messages'),
                                         ('BLOCK', 'llm.policy.blocked', forbidden, 'operation.unsupported')]:
        events.append(SecurityEvent(session_id=session, request_id=request, agent_id='claude', adapter='claude',
                                    channel='LLM', direction='OUTBOUND', protocol='ANTHROPIC_MESSAGES', inspection_level='STRUCTURED',
                                    action=action, reason_code=reason, policy_version='t03', rule_ids=(rule,), occurred_at=datetime.now(timezone.utc)))
    return session, probe, events


def result(session, probe, events, **changes):
    options = {'cleanup': True, 'provider_state': True, 'audit': True, 'workspace': True}
    options.update(changes)
    return aggregate(session, 0, probe, events, **options)


def test_real_session_result_aggregation_and_readable_output():
    session, probe, events = evidence()
    proof = result(session, probe, events)
    assert proof.passed and proof.session_id == session
    output = '\n'.join(proof.lines())
    assert f'Session: {session}' in output and f'Real Claude response: {EXPECTED}' in output
    assert 'T04 INTEGRATION PASS' in output and '[FAIL]' not in output
    # The firewall denial is a probe, not an invented application event.
    assert len(events) == 3 and not any('network' in event.reason_code for event in events)


@pytest.mark.parametrize('failure', ['claude', 'response', 'allow', 'block', 'audit', 'session', 'adapter',
                                   'bypass', 'proxy', 'block_identity', 'allow_forbidden', 'request_id'])
def test_required_evidence_failure_fails_whole_proof(failure):
    session, probe, events = evidence()
    if failure == 'claude':
        probe = probe.model_copy(update={'claude_exit': 1})
    elif failure == 'response':
        probe = probe.model_copy(update={'claude_response': None})
    elif failure in ('allow', 'block', 'audit'):
        events = [event for event in events if event.action != failure.upper()]
    elif failure == 'session':
        events[0] = events[0].model_copy(update={'session_id': uuid4()})
    elif failure == 'adapter':
        events[0] = events[0].model_copy(update={'adapter': 'other'})
    elif failure == 'bypass':
        probe = probe.model_copy(update={'direct_blocked': False})
    elif failure == 'proxy':
        probe = probe.model_copy(update={'proxy_denied': False})
    elif failure == 'block_identity':
        events[2] = events[2].model_copy(update={'reason_code': 'llm.invalid_session'})
    elif failure == 'allow_forbidden':
        events.append(events[0].model_copy(update={'request_id': probe.forbidden_request_id}))
    elif failure == 'request_id':
        events = [event.model_copy(update={'request_id': None}) for event in events]
    assert not result(session, probe, events).passed


@pytest.mark.parametrize('missing', ['cleanup', 'provider_state', 'audit', 'workspace'])
def test_cleanup_and_persistence_are_required(missing):
    session, probe, events = evidence()
    assert not result(session, probe, events, **{missing: False}).passed


def test_uncorrelated_completion_and_nonzero_workload_fail():
    session, probe, events = evidence()
    events[1] = events[1].model_copy(update={'request_id': uuid4()})
    assert not result(session, probe, events).passed
    assert not aggregate(session, 124, probe, events, cleanup=True, provider_state=True, audit=True, workspace=True).passed


def test_safe_parse_and_output_do_not_expose_tokens_or_native_output():
    session, probe, events = evidence()
    secret = 'synthetic_session_token_never_display'
    raw = 'native private output ' + secret + '\n' + PREFIX + probe.model_dump_json() + '\n'
    parsed = parse_result(raw)
    assert parsed == probe
    assert secret not in '\n'.join(result(session, parsed, events).lines())
    for invalid in (PREFIX + json.dumps({'claude_response': secret}), PREFIX + '{bad-json', raw + PREFIX + probe.model_dump_json()):
        failed = parse_result(invalid)
        assert failed == ProbeResult()
        assert secret not in '\n'.join(result(session, failed, events).lines())


def test_unsupported_agent_is_rejected_before_orchestration(monkeypatch, tmp_path):
    monkeypatch.setattr('aictrl.cli.main.verify_claude', lambda *args: pytest.fail('unsupported agent reached runtime'))
    response = CliRunner().invoke(app, ['verify', 'codex', str(tmp_path)])
    assert response.exit_code == 2 and 'claude only' in response.output


def test_cli_prints_pass_and_nonzero_failure(monkeypatch, tmp_path):
    session, probe, events = evidence()
    runner = CliRunner()
    monkeypatch.setattr('aictrl.cli.main.verify_claude', lambda *args: result(session, probe, events))
    assert runner.invoke(app, ['verify', 'claude', str(tmp_path)]).exit_code == 0
    monkeypatch.setattr('aictrl.cli.main.verify_claude', lambda *args: result(session, probe, []))
    failed = runner.invoke(app, ['verify', 'claude', str(tmp_path)])
    assert failed.exit_code == 1 and 'T04 INTEGRATION FAIL' in failed.output


def test_operational_error_is_safe(monkeypatch, tmp_path):
    def fail(*args):
        raise integration.RuntimeFailure('synthetic-secret-provider-state')
    monkeypatch.setattr('aictrl.cli.main.verify_claude', fail)
    response = CliRunner().invoke(app, ['verify', 'claude', str(tmp_path)])
    assert response.exit_code == 2 and 'synthetic-secret' not in response.output


def test_one_supervisor_runs_native_and_probes_then_reads_events_after_cleanup(monkeypatch, tmp_path):
    session, probe, events = evidence()
    settings = load_config(PROJECT_ROOT)
    audit = tmp_path / settings.gateway.audit_directory / 'events.sqlite3'
    audit.parent.mkdir(parents=True)
    audit.touch()
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    instances = []
    calls = []

    class Runtime:
        def __init__(self, selected, config, agent, project):
            assert selected == workspace and agent.persistent_state_volume == 'aictrl-claude-state'
            assert config.runtime.routing_mode == 'APPLICATION_GATEWAY'
            self.session = SimpleNamespace(identity=SimpleNamespace(session_id=session))
            self.identifier = session.hex
            self.directory = SimpleNamespace(name=str(tmp_path / 'ephemeral'))
            instances.append(self)
        def run(self, command, *, input_text, capture_output):
            assert command[:2] == ('python', '-c') and "['claude', '--print'" in command[2]
            assert 'socket.create_connection' in command[2] and "method='GET'" in command[2]
            assert input_text == 'Reply with exactly: ' + EXPECTED and capture_output
            calls.append('run-and-cleanup')
            return 0, PREFIX + probe.model_dump_json()

    class Store:
        def __init__(self, path):
            assert path == audit and calls[0] == 'run-and-cleanup'
        def events(self, identity):
            assert identity == session
            calls.append('read-audit')
            return events

    monkeypatch.setattr(integration, 'load_config', lambda project: settings)
    monkeypatch.setattr(integration, 'validate_workspace', lambda selected, project: workspace)
    monkeypatch.setattr(integration, 'claude_authenticated', lambda image: True)
    monkeypatch.setattr(integration, 'RuntimeSupervisor', Runtime)
    monkeypatch.setattr(integration, 'EventStore', Store)
    def docker(arguments, **kwargs):
        if '--filter' in arguments:
            assert arguments[-1] == 'label=io.aictrl.session=' + session.hex
        calls.append('docker')
        return subprocess.CompletedProcess(arguments, 0, '', '')
    monkeypatch.setattr(integration, 'docker', docker)
    proof = integration.verify_claude(workspace, tmp_path)
    assert proof.passed and len(instances) == 1
    assert calls == ['run-and-cleanup', 'docker', 'docker', 'docker', 'docker', 'read-audit']


def test_egress_only_or_missing_auth_never_starts_proof(monkeypatch, tmp_path):
    settings = load_config(PROJECT_ROOT)
    monkeypatch.setattr(integration, 'load_config', lambda project: settings)
    monkeypatch.setattr(integration, 'RuntimeSupervisor', lambda *args: pytest.fail('preflight reached runtime'))
    settings.runtime.routing_mode = 'EGRESS_ONLY'
    with pytest.raises(integration.RuntimeFailure, match='APPLICATION_GATEWAY'):
        integration.verify_claude(tmp_path)
    settings.runtime.routing_mode = 'APPLICATION_GATEWAY'
    monkeypatch.setattr(integration, 'claude_authenticated', lambda image: False)
    with pytest.raises(integration.AuthenticationCheckError, match='claude-login'):
        integration.verify_claude(tmp_path)
