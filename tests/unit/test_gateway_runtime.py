import json
import subprocess
from pathlib import Path

import pytest

from aictrl.adapters.base import EndpointPurpose, ProviderEndpoint, RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.runtime.config import TestDestination as Destination, load_config
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT



def prepared(tmp_path, monkeypatch, *, pin_inference=False):
    project = tmp_path / 'control'
    (project / 'config').mkdir(parents=True)
    (project / 'docker').mkdir()
    for file in ('config/policy.yaml', 'docker/compose.yaml'):
        (project / file).write_bytes((PROJECT_ROOT / file).read_bytes())
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    settings = load_config(PROJECT_ROOT)
    assert settings.runtime.routing_mode == RoutingMode.APPLICATION_GATEWAY
    if pin_inference:
        settings.runtime.test_destinations = (Destination(host='api.anthropic.com', port=443, connect_ip='172.29.1.2'),)
    agent = ClaudeAdapter(settings.claude.image, settings.runtime.routing_mode)
    # Duplicating the inference host as AUTH must not open an alternate path.
    agent.required_provider_endpoints += (ProviderEndpoint(host='api.anthropic.com', purpose=EndpointPurpose.AUTHENTICATION),)
    runtime = RuntimeSupervisor(workspace, settings, agent, project)
    def command(arguments, **kwargs):
        output = runtime.identifier if arguments[0] in ('create', 'inspect') else ''
        return subprocess.CompletedProcess(arguments, 0, output, '')
    monkeypatch.setattr('aictrl.runtime.supervisor.docker', command)
    return runtime


def test_gateway_manifest_identity_storage_and_proxy_partition(tmp_path, monkeypatch):
    runtime = prepared(tmp_path, monkeypatch)
    directory = Path(runtime.directory.name)
    try:
        runtime.prepare()
        topology = json.loads(runtime.manifest.read_text())
        gateway, agent = topology['services']['gateway'], topology['services']['agent']
        assert gateway['cap_drop'] == ['ALL'] and gateway['read_only']
        assert gateway['user'] == f'{runtime.uid}:{runtime.gid}'
        assert set(gateway['networks']) == {'agent-internal', 'upstream'}
        assert 'ports' not in gateway
        assert agent['networks'] == ['agent-internal']
        assert agent['extra_hosts']['gateway'] == agent['environment']['AICTRL_GATEWAY_IP']
        assert agent['depends_on']['gateway']['condition'] == 'service_healthy'
        assert len(agent['volumes']) == 3 and len(gateway['volumes']) == 3
        mounts = str(gateway['volumes'])
        assert not any(value in mounts for value in ('docker.sock', '/workspace', 'claude-state', 'proxy-private-ca'))
        assert gateway['volumes'][0]['read_only'] and gateway['volumes'][1]['read_only']
        assert gateway['volumes'][2]['source'] == str(runtime.project / '.aictrl/audit')
        secret_file = directory / 'session.json'
        record = json.loads(secret_file.read_text())
        assert secret_file.stat().st_mode & 0o777 == 0o400
        assert set(record) == {'session_id', 'agent_id', 'adapter', 'user_id', 'profile_id', 'protocol', 'expires_at', 'session_token'}
        assert record['session_token'] == agent['environment']['ANTHROPIC_CUSTOM_HEADERS'].split(': ', 1)[1]
        assert record['session_token'] not in runtime.session.identity.model_dump_json()
        assert record['session_token'] not in repr(runtime.session.identity)
        assert not any(name in agent['environment'] for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'))
        destinations = json.loads((directory / 'destinations.json').read_text())
        assert {item['host'] for item in destinations} == {'claude.ai', 'claude.com', 'platform.claude.com', 'console.anthropic.com'}
        audit = runtime.project / '.aictrl/audit'
    finally:
        runtime.close()
    assert not directory.exists() and audit.is_dir()


def test_supervisor_tokens_are_unique_and_not_serialized(tmp_path, monkeypatch):
    first = prepared(tmp_path, monkeypatch)
    # Build the second session on another controlled fixture directory.
    other = tmp_path / 'other'
    other.mkdir()
    second = prepared(other, monkeypatch)
    try:
        assert first.session.identity.session_token != second.session.identity.session_token
        assert first.session.identity.session_id != second.session.identity.session_id
    finally:
        first.close()
        second.close()


def test_inference_host_cannot_be_reintroduced_as_test_destination(tmp_path, monkeypatch):
    runtime = prepared(tmp_path, monkeypatch, pin_inference=True)
    try:
        with pytest.raises(RuntimeFailure, match='Inference destinations'):
            runtime.prepare()
    finally:
        runtime.close()
