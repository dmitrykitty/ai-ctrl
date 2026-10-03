import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from aictrl.adapters.base import EndpointPurpose, ProviderEndpoint, RoutingMode
from aictrl.adapters.codex import CodexAdapter
from aictrl.contracts import AgentSession
from aictrl.runtime import codex_auth
from aictrl.runtime.auth import AuthenticationCheckError
from aictrl.runtime.config import CodexRuntime, TestDestination as Destination, load_config
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import RuntimeSupervisor, run_agent
from aictrl.runtime.workspace import PROJECT_ROOT


def identity(token=None):
    return AgentSession(agent_id='codex', adapter='codex', user_id='test', profile_id='local',
                        workspace='/workspace', protocol='RESPONSES', billing_mode='SUBSCRIPTION',
                        started_at=datetime.now(timezone.utc), session_token=token)


def test_native_codex_config_and_secret_separation():
    adapter = CodexAdapter('pinned')
    with pytest.raises(ValueError, match='session token'):
        adapter.render_config(identity())
    config = adapter.render_config(identity('synthetic_internal_identity_abcdefghijklmnopqrstuvwxyz'))
    assert config.entry_command == ('codex', '--no-daemon', '--profile', 'aictrl')
    assert config.state_mount == '/home/dev/.codex' and config.persistent_state_volume == 'aictrl-codex-state'
    assert config.environment['CODEX_HOME'] == '/home/dev/.codex'
    assert 'AICTRL_SESSION_TOKEN' not in config.model_dump_json() and 'synthetic_internal' not in repr(config)
    assert 'OPENAI_API_KEY' not in config.environment
    assert adapter.exec_command()[-5:] == ('exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never')


def test_verified_provider_profile_uses_environment_identity_only():
    raw = (PROJECT_ROOT / 'docker/codex/aictrl.config.toml').read_text()
    data = tomllib.loads(raw)
    provider = data['model_providers']['aictrl']
    assert data['model_provider'] == 'aictrl' and data['forced_login_method'] == 'chatgpt'
    assert data['sandbox_mode'] == 'danger-full-access' and data['approval_policy'] == 'never'
    assert data['web_search'] == 'disabled'
    assert provider['base_url'] == 'http://gateway:8000/codex'
    assert provider['wire_api'] == 'responses' and provider['requires_openai_auth']
    assert not provider['supports_websockets']
    assert provider['request_max_retries'] == provider['stream_max_retries'] == 0
    assert provider['env_http_headers'] == {'X-AICtrl-Session': 'AICTRL_SESSION_TOKEN'}
    assert 'Bearer ' not in raw and 'synthetic_internal' not in raw


@pytest.mark.parametrize('field,value', [('state_mount', '/home/dev/.claude'), ('state_volume', 'host-codex'), ('auth_mode', 'api-key')])
def test_codex_state_config_is_narrow(field, value):
    data = dict(image='pinned', state_volume='aictrl-codex-state', state_mount='/home/dev/.codex', auth_mode='subscription')
    data[field] = value
    with pytest.raises(ValidationError):
        CodexRuntime(**data)


@pytest.mark.parametrize('code,text,expected', [(0, 'Logged in using ChatGPT', 0), (1, 'Not logged in', 1),
                                               (0, 'Logged in using an API key: synthetic-secret', 2),
                                               (125, 'synthetic-private-error', 2)])
def test_auth_status_is_offline_native_and_does_not_export_diagnostics(monkeypatch, capsys, code, text, expected):
    commands = []
    def execute(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '', '') if command[1] == 'ps' else subprocess.CompletedProcess(command, code, '', text)
    monkeypatch.setattr(codex_auth.subprocess, 'run', execute)
    assert codex_auth.main() == expected
    printed = capsys.readouterr()
    assert 'synthetic-secret' not in printed.out + printed.err and 'synthetic-private-error' not in printed.out + printed.err
    command = commands[1]
    assert command[command.index('--network') + 1] == 'none'
    assert 'type=volume,source=aictrl-codex-state,target=/home/dev/.codex,readonly' in command
    assert not any('type=bind' in item or 'OPENAI_API_KEY' in item for item in command)
    assert '--bounding-set=-all' in command[-1] and 'login status' in command[-1]


def test_active_codex_state_rejects_status_without_mounting(monkeypatch):
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'active\n', '')
    monkeypatch.setattr(codex_auth.subprocess, 'run', execute)
    with pytest.raises(AuthenticationCheckError, match='in use'):
        codex_auth.codex_authenticated()
    assert len(calls) == 1


def runtime(tmp_path, monkeypatch, *, pin=False):
    project, workspace = tmp_path / 'control', tmp_path / 'workspace'
    (project / 'config').mkdir(parents=True)
    (project / 'docker').mkdir()
    workspace.mkdir()
    for file in ('config/policy.yaml', 'docker/compose.yaml'):
        (project / file).write_bytes((PROJECT_ROOT / file).read_bytes())
    settings = load_config(PROJECT_ROOT)
    if pin:
        settings.runtime.test_destinations = (Destination(host='api.openai.com', port=443, connect_ip='172.29.1.2'),)
    agent = CodexAdapter(settings.codex.image, RoutingMode.EGRESS_ONLY).render_config(identity())
    agent.required_provider_endpoints += (ProviderEndpoint(host='api.openai.com', purpose=EndpointPurpose.AUTHENTICATION),)
    supervisor = RuntimeSupervisor(workspace, settings, agent, project)
    commands = []
    def command(arguments, **kwargs):
        commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, supervisor.identifier if arguments[0] in ('create', 'inspect') else '', '')
    monkeypatch.setattr('aictrl.runtime.supervisor.docker', command)
    return supervisor, commands


def test_one_supervisor_selects_codex_identity_mounts_and_separate_lease(tmp_path, monkeypatch):
    supervisor, commands = runtime(tmp_path, monkeypatch)
    directory = Path(supervisor.directory.name)
    try:
        supervisor.prepare()
        assert supervisor.session.identity.protocol == 'RESPONSES'
        topology = json.loads(supervisor.manifest.read_text())
        agent, gateway = topology['services']['agent'], topology['services']['gateway']
        assert len(agent['volumes']) == 3 and agent['volumes'][1] == 'codex-state:/home/dev/.codex'
        assert 'claude-state' not in topology['volumes']
        assert topology['volumes']['codex-state']['external']
        assert agent['environment']['AICTRL_SESSION_TOKEN'] == supervisor.session.identity.session_token.get_secret_value()
        assert agent['networks'] == ['agent-internal'] and agent['cap_drop'] == ['ALL']
        assert len(gateway['volumes']) == 3 and '/home/dev/.codex' not in str(gateway['volumes'])
        destinations = json.loads((directory / 'destinations.json').read_text())
        assert {item['host'] for item in destinations} == {'auth.openai.com'}
        assert supervisor.lock_name == 'aictrl-codex-auth'
        assert any(args[0] == 'create' and 'aictrl-codex-auth' in args for args in commands)
    finally:
        supervisor.close()
    assert not directory.exists()


def test_openai_cannot_be_reintroduced_as_test_destination(tmp_path, monkeypatch):
    supervisor, _ = runtime(tmp_path, monkeypatch, pin=True)
    try:
        with pytest.raises(RuntimeFailure, match='Inference destinations'):
            supervisor.prepare()
    finally:
        supervisor.close()


def test_unauthenticated_codex_run_refuses_without_starting_login(monkeypatch):
    monkeypatch.setattr('aictrl.runtime.supervisor.codex_authenticated', lambda image: False)
    with pytest.raises(AuthenticationCheckError, match='make codex-login'):
        run_agent('codex', PROJECT_ROOT / 'demo/project')
