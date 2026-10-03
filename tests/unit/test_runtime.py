from pathlib import Path
from datetime import datetime, timezone
import time

import pytest
from pydantic import ValidationError

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.contracts import AgentSession, SessionState
from aictrl.runtime.auth import AuthenticationCheckError
from aictrl.runtime.compose import render_compose
from aictrl.runtime.config import TestDestination as Destination, load_config
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import RuntimeSupervisor, run_claude
from aictrl.runtime.workspace import PROJECT_ROOT, validate_workspace


def session(token=None):
    return AgentSession(agent_id='claude', adapter='claude', user_id='local', profile_id='local',
                        workspace='/workspace', protocol='ANTHROPIC_MESSAGES', billing_mode='SUBSCRIPTION',
                        started_at=datetime.now(timezone.utc), session_token=token)


def test_egress_only_keeps_native_provider_without_gateway_identity():
    agent = ClaudeAdapter('pinned', RoutingMode.EGRESS_ONLY).render_config(session(token=None))
    assert 'ANTHROPIC_BASE_URL' not in agent.environment
    assert 'ANTHROPIC_CUSTOM_HEADERS' not in agent.environment
    assert 'gateway' not in agent.environment['NO_PROXY']
    assert agent.environment['HTTPS_PROXY'] == 'http://proxy:8080'


def test_selected_workspace_and_symlink_permissions_are_preserved(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir(mode=0o750)
    link = tmp_path / 'link'
    link.symlink_to(workspace, target_is_directory=True)
    assert validate_workspace(link) == workspace
    assert workspace.stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize('path', [PROJECT_ROOT, PROJECT_ROOT / 'docker', Path('/'), Path('/etc'), Path('/tmp'), Path.home()])
def test_control_host_paths_are_rejected(path):
    with pytest.raises(ValueError):
        validate_workspace(path)


@pytest.mark.parametrize('name', ['.ssh', '.aws', '.kube', '.claude', '.codex', '.git/ssh', '.aictrl'])
def test_workspace_containing_credential_or_control_storage_is_rejected(tmp_path, name):
    (tmp_path / name).mkdir(parents=True)
    with pytest.raises(ValueError, match='protected credential'):
        validate_workspace(tmp_path)


def test_workspace_missing_file_and_protected_symlink_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='does not exist'):
        validate_workspace(tmp_path / 'absent')
    file = tmp_path / 'file'
    file.touch()
    with pytest.raises(ValueError, match='directory'):
        validate_workspace(file)
    link = tmp_path / 'control-link'
    link.symlink_to(PROJECT_ROOT, target_is_directory=True)
    with pytest.raises(ValueError, match='control files'):
        validate_workspace(link)
    assert validate_workspace(PROJECT_ROOT / 'demo/project') == PROJECT_ROOT / 'demo/project'


@pytest.mark.parametrize('host', ['https://example.com', '*.example.com', 'user@example.com', 'example.com/path', 'example..com'])
def test_trusted_destination_requires_exact_authority(host):
    with pytest.raises(ValidationError):
        Destination(host=host, port=443)


@pytest.mark.parametrize('ip', ['127.0.0.1', '169.254.169.254', '0.0.0.0', '224.0.0.1'])
def test_test_destination_cannot_pin_host_metadata_or_loopback(ip):
    with pytest.raises(ValidationError):
        Destination(host='example.test', port=443, connect_ip=ip)


def test_rendered_topology_separates_state_ca_network_and_resource_limits(tmp_path):
    settings = load_config(PROJECT_ROOT)
    settings.runtime.routing_mode = RoutingMode.EGRESS_ONLY
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY).render_config(session(token=None))
    topology = render_compose(PROJECT_ROOT, tmp_path, tmp_path / 'workspace', settings, agent,
                              'synthetic-session', '172.30.10.0/24', '172.30.10.2', 1000, 1001, False)
    native, proxy = topology['services']['agent'], topology['services']['proxy']
    assert native['networks'] == ['agent-internal']
    assert topology['networks']['agent-internal']['internal'] is True
    assert topology['networks']['agent-internal']['enable_ipv6'] is False
    assert native['cap_drop'] == ['ALL']
    assert 'no-new-privileges:true' in native['security_opt']
    assert native['environment']['AICTRL_UID'] == '1000'
    assert native['environment']['AICTRL_GID'] == '1001'
    assert 'AICTRL_GATEWAY_IP' not in native['environment']
    assert (native['cpus'], native['mem_limit'], native['pids_limit']) == (2, '2048m', 256)
    assert len(native['volumes']) == 3
    assert native['volumes'][0]['source'] == str(tmp_path / 'workspace')
    assert native['volumes'][1:] == ['claude-state:/home/dev/.claude', 'proxy-public-ca:/etc/aictrl:ro']
    assert topology['volumes']['claude-state'] == {'external': True, 'name': 'aictrl-claude-state'}
    assert 'proxy-private-ca:/home/mitmproxy/.mitmproxy' in proxy['volumes']
    assert proxy['read_only'] and proxy['cap_drop'] == ['ALL']
    assert native['labels']['io.aictrl.session'] == 'synthetic-session'
    assert not any('docker.sock' in str(mount) for mount in native['volumes'] + proxy['volumes'])


@pytest.mark.parametrize('authenticated', [False, 'error'])
def test_missing_or_uncheckable_auth_never_creates_runtime(monkeypatch, tmp_path, authenticated):
    def auth(*args):
        if authenticated == 'error':
            raise AuthenticationCheckError('safe operational error')
        return False
    monkeypatch.setattr('aictrl.runtime.supervisor.claude_authenticated', auth)
    monkeypatch.setattr('aictrl.runtime.supervisor.RuntimeSupervisor', lambda *a, **kw: pytest.fail('preflight started runtime'))
    with pytest.raises(AuthenticationCheckError, match='make claude-login' if authenticated is False else 'operational'):
        run_claude(tmp_path)


def test_timeout_cannot_extend_configured_limit(monkeypatch, tmp_path):
    monkeypatch.setattr('aictrl.runtime.supervisor.claude_authenticated', lambda *a: pytest.fail('invalid timeout reached auth'))
    with pytest.raises(ValueError, match='configured wall-clock'):
        run_claude(tmp_path, timeout=601)


def test_deadline_during_preparation_is_terminal_and_cleans_host_metadata(tmp_path):
    settings = load_config(PROJECT_ROOT)
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY).render_config(session(token=None))
    runtime = RuntimeSupervisor(tmp_path, settings, agent)
    directory = Path(runtime.directory.name)
    runtime._deadline = time.monotonic() - 1
    assert runtime.run(capture_output=True)[0] == 124
    assert runtime.session.identity.state == SessionState.FAILED
    assert runtime.session.identity.ended_at is not None
    assert not directory.exists()


def test_preparation_failure_cleans_host_metadata_and_restores_signal_handlers(monkeypatch, tmp_path):
    import signal
    before = signal.getsignal(signal.SIGINT)
    settings = load_config(PROJECT_ROOT)
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY).render_config(session(token=None))
    runtime = RuntimeSupervisor(tmp_path, settings, agent)
    directory = Path(runtime.directory.name)
    monkeypatch.setattr(runtime, 'prepare', lambda: (_ for _ in ()).throw(RuntimeFailure('synthetic failure')))
    with pytest.raises(RuntimeFailure, match='synthetic failure'):
        runtime.run(capture_output=True)
    assert signal.getsignal(signal.SIGINT) == before
    assert runtime.session.identity.state == SessionState.FAILED
    assert not directory.exists()


def test_timed_out_lock_creation_removes_only_its_own_reservation(monkeypatch, tmp_path):
    import subprocess
    settings = load_config(PROJECT_ROOT)
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY).render_config(session())
    runtime = RuntimeSupervisor(tmp_path, settings, agent)
    removed = []

    def command(arguments, **kwargs):
        if arguments[0] == 'create':
            runtime._deadline = time.monotonic() - 1
            raise RuntimeFailure('synthetic Docker timeout')
        if arguments[0] == 'inspect':
            return subprocess.CompletedProcess(arguments, 0, runtime.identifier, '')
        if arguments[0] == 'rm':
            removed.append(arguments[-1])
        return subprocess.CompletedProcess(arguments, 0, '', '')

    monkeypatch.setattr('aictrl.runtime.supervisor.docker', command)
    assert runtime.run()[0] == 124
    assert removed == ['aictrl-claude-auth']
    assert not Path(runtime.directory.name).exists()


def test_native_ui_preparation_preserves_trust_and_never_opens_credentials(monkeypatch, tmp_path):
    import json
    import os
    import runpy
    config = tmp_path / '.claude.json'
    original = {'theme': 'dark', 'projects': {'/workspace': {'hasTrustDialogAccepted': False}}}
    config.write_text(json.dumps(original))
    opened = []
    real_open = os.open

    def local_open(path, flags, mode):
        opened.append(str(path))
        assert str(path) == '/home/dev/.claude/.claude.json'
        return real_open(config, flags, mode)

    monkeypatch.setattr(os, 'open', local_open)
    helper = str(PROJECT_ROOT / 'docker/base/prepare-claude-ui.py')
    runpy.run_path(helper)
    assert json.loads(config.read_text()) == original | {'hasCompletedOnboarding': True}
    modified = config.stat().st_mtime_ns
    runpy.run_path(helper)
    assert config.stat().st_mtime_ns == modified
    assert len(opened) == 2
