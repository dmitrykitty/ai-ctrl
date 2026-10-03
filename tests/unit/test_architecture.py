"""Offline trusted extension proof: no additional production adapter/plugin."""

import asyncio
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from aictrl.adapters.base import AgentConfig, RoutingMode
from aictrl.contracts import AgentProtocol, AgentSession, BillingMode
from aictrl.gateway.app import create_app
from aictrl.gateway.control import MAX_BODY, ControlPipeline
from aictrl.gateway.registry import PROTOCOL_HANDLERS, resolve_handler
from aictrl.gateway.session import GatewaySession, load_session
from aictrl.policy.models import AdmissionRule, AgentPolicy, Policy
from aictrl.reporting.sink import EventSink, StoreFailure
from aictrl.reporting.store import EventStore
from aictrl.runtime import registry, supervisor
from aictrl.runtime.compose import provider_lease_name, validate_provider_state
from aictrl.runtime.config import load_config
from aictrl.runtime.workspace import PROJECT_ROOT

from test_gateway import Frames
from test_responses import FRAMES


class ThirdAdapter:
    name = 'synthetic-third'
    protocol = AgentProtocol.RESPONSES
    billing_mode = BillingMode.LOCAL
    image_ref = 'synthetic-prepared-image'
    persistent_state_volume = 'aictrl-third-state'
    state_mount = '/home/dev/.third'
    entry_command = ('python', 'synthetic-agent.py')
    environment = {}
    required_provider_endpoints = ()

    def __init__(self, image_ref, routing_mode):
        self.image_ref, self.routing_mode = image_ref, routing_mode
        self.rendered = []

    def render_config(self, session):
        self.rendered.append(session)
        return AgentConfig(adapter=self.name, image_ref=self.image_ref, entry_command=self.entry_command,
                           persistent_state_volume=self.persistent_state_volume, state_mount=self.state_mount,
                           environment={'AICTRL_SESSION_TOKEN': session.session_token.get_secret_value()})

    def smoke_command(self):
        return ('python', '--version')

    def prompt_command(self):
        return (*self.entry_command, '--print')


def third_policy():
    rule = AdmissionRule(id='third.responses', channel='LLM', direction='OUTBOUND', protocol='RESPONSES',
                         target='openai', operations=('responses',), action='ALLOW')
    return Policy(schema_version=2, policy_version='synthetic-extension', default_action='BLOCK',
                  agents={'synthetic-third': AgentPolicy(enabled=True, rules=(rule,))})


def test_trusted_third_adapter_uses_one_identity_config_and_existing_pipeline(tmp_path, monkeypatch):
    project, workspace = tmp_path / 'control', tmp_path / 'workspace'
    (project / 'docker').mkdir(parents=True)
    (project / 'config').mkdir()
    workspace.mkdir()
    (project / 'docker/compose.yaml').write_bytes((PROJECT_ROOT / 'docker/compose.yaml').read_bytes())
    (project / 'config/policy.yaml').write_text(third_policy().model_dump_json())
    settings = load_config(PROJECT_ROOT)
    monkeypatch.setattr(supervisor, 'load_config', lambda root: settings)
    spec = registry.RuntimeAgentSpec(ThirdAdapter, lambda config: SimpleNamespace(image='synthetic-prepared-image'),
                                     lambda image: True, 'synthetic auth is test-only')
    monkeypatch.setattr(registry, 'AGENT_REGISTRY', MappingProxyType({**registry.AGENT_REGISTRY, ThirdAdapter.name: spec}))
    identities, runs = [], []

    def identity(**kwargs):
        result = AgentSession(**kwargs)
        identities.append(result)
        return result

    monkeypatch.setattr(supervisor, 'AgentSession', identity)

    def docker(arguments, **kwargs):
        current = runs[0]
        output = current.identifier if arguments[0] in ('create', 'inspect') else ''
        return subprocess.CompletedProcess(arguments, 0, output, '')

    monkeypatch.setattr(supervisor, 'docker', docker)

    def run(current, command, *, input_text):
        runs.append(current)
        assert command == current.adapter.prompt_command() and input_text == 'public synthetic input'
        directory = Path(current.directory.name)
        try:
            current.prepare()
            trusted = load_session(directory / 'session.json')
            assert len(identities) == 1 and current.adapter.rendered == identities
            assert identities[0] is current.session.identity
            assert trusted.session_id == identities[0].session_id
            assert trusted.protocol == current.adapter.protocol
            token = identities[0].session_token.get_secret_value()
            manifest = json.loads(current.manifest.read_text())
            assert manifest['volumes']['provider-state'] == {'external': True, 'name': ThirdAdapter.persistent_state_volume}
            assert manifest['services']['agent']['volumes'][1] == 'provider-state:/home/dev/.third'
            assert manifest['services']['agent']['environment']['AICTRL_SESSION_TOKEN'] == token
            assert current.lock_name == provider_lease_name(ThirdAdapter.persistent_state_volume)
            store = EventStore(project / '.aictrl/audit/events.sqlite3')

            async def proof():
                calls = []
                async def upstream(request):
                    events = EventStore(store.path).events(trusted.session_id)
                    assert events[-1].action == 'ALLOW'
                    assert request.url.scheme == 'https' and request.url.host == 'chatgpt.com'
                    assert request.url.path == '/backend-api/codex/responses' and request.url.query == b''
                    assert 'x-aictrl-session' not in request.headers
                    calls.append(request)
                    return httpx.Response(200, stream=Frames(FRAMES))
                async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                    app = create_app(trusted, third_policy(), store, client)
                    async with app.router.lifespan_context(app):
                        assert type(app.state.gateway) is ControlPipeline
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                            result = await downstream.post('/codex/responses', content=b'{"input":"public"}',
                                                           headers={'X-AICtrl-Session': token})
                            assert result.status_code == 200 and result.content == b''.join(FRAMES)
                            denied = await downstream.get('/codex/responses', headers={'X-AICtrl-Session': token})
                            assert denied.status_code == 403 and len(calls) == 1
            asyncio.run(proof())
            events = EventStore(store.path).events(trusted.session_id)
            assert [event.action for event in events] == ['ALLOW', 'AUDIT', 'BLOCK']
            assert events[0].request_id == events[1].request_id
            assert all(event.session_id == identities[0].session_id and event.agent_id == event.adapter == ThirdAdapter.name
                       and event.protocol == 'RESPONSES' and event.schema_version == 1 for event in events)
            assert token.encode() not in store.path.read_bytes()
        finally:
            current.close()
        assert not directory.exists()
        return 0, ''

    monkeypatch.setattr(supervisor.RuntimeSupervisor, 'run', run)
    assert supervisor.run_agent(ThirdAdapter.name, workspace, project, prompt='public synthetic input') == 0
    assert len(runs) == len(identities) == 1


@pytest.mark.parametrize('volume,mount', [
    (None, '/home/dev/.provider'), ('named-volume', None), ('/host/state', '/home/dev/.provider'),
    ('named:bind', '/home/dev/.provider'), ('*', '/home/dev/.provider'),
    ('named-volume', 'relative'), ('named-volume', '/home/dev/../.provider'),
    ('named-volume', '/home/dev/.provider/link'), ('named-volume', '/home/dev/.provider/'),
    ('named-volume', '/root/.provider'), ('named-volume', '/home/dev/.*'),
])
def test_provider_state_rejects_bind_traversal_and_non_provider_paths(volume, mount):
    with pytest.raises(ValueError):
        validate_provider_state(volume, mount)


def test_static_registries_fail_closed_without_dynamic_loading():
    with pytest.raises(TypeError):
        registry.AGENT_REGISTRY['untrusted'] = None
    with pytest.raises(TypeError):
        PROTOCOL_HANDLERS[AgentProtocol.CHAT_COMPLETIONS] = None
    with pytest.raises(ValueError, match='Unsupported runtime agent'):
        registry.resolve_agent('untrusted')
    for protocol in (AgentProtocol.ANTHROPIC_MESSAGES, AgentProtocol.RESPONSES):
        assert resolve_handler(protocol).protocol == protocol
    with pytest.raises(ValueError, match='Unsupported trusted gateway protocol'):
        resolve_handler(AgentProtocol.CHAT_COMPLETIONS)


def test_unknown_or_missing_trusted_protocol_prevents_gateway_startup():
    record = dict(session_id=str(uuid4()), agent_id='third', adapter='third', user_id='local', profile_id='local',
                  expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), session_token='x' * 48)
    for candidate in (record, record | {'protocol': 'MISSING'}):
        with pytest.raises(ValidationError):
            GatewaySession.model_validate(candidate)
    valid_but_unsupported = GatewaySession.model_validate(record | {'protocol': 'CHAT_COMPLETIONS'})
    with pytest.raises(ValueError, match='Unsupported trusted gateway protocol'):
        create_app(valid_but_unsupported, third_policy(), SimpleNamespace(append=lambda event: None))
    mismatched = GatewaySession.model_validate(record | {'protocol': 'RESPONSES', 'agent_id': 'different'})
    with pytest.raises(ValueError, match='Inconsistent trusted gateway agent identity'):
        create_app(mismatched, third_policy(), SimpleNamespace(append=lambda event: None))


def test_generic_run_codex_requires_gateway_before_authentication(tmp_path, monkeypatch):
    settings = load_config(PROJECT_ROOT)
    settings.runtime.routing_mode = RoutingMode.EGRESS_ONLY
    monkeypatch.setattr(supervisor, 'load_config', lambda root: settings)
    with pytest.raises(supervisor.RuntimeFailure, match='requires APPLICATION_GATEWAY'):
        supervisor.run_agent('codex', tmp_path)


def test_non_sqlite_sink_controls_admission_and_completion(tmp_path):
    from test_gateway import fixture, invoke, native_policy
    _, _, session, calls, _ = fixture(tmp_path)

    class Sink:
        def __init__(self):
            self.events = []
            self.fail = False
        def append(self, event):
            if self.fail:
                raise StoreFailure('private synthetic error')
            self.events.append(event)

    sink = Sink()
    assert isinstance(sink, EventSink)
    async def upstream(request):
        assert [event.action for event in sink.events] == ['ALLOW']
        calls.append(request)
        return httpx.Response(200, stream=Frames())
    async def proof():
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            app = create_app(session, native_policy(), sink, client)
            assert (await invoke(app, client)).status_code == 200
            assert [event.action for event in sink.events] == ['ALLOW', 'AUDIT']
            sink.fail = True
            assert (await invoke(app, client)).status_code == 503
            assert (await invoke(app, client, token=None)).status_code == 503
            assert len(calls) == 1
    asyncio.run(proof())


def test_common_body_limit_has_no_upstream_side_effect(tmp_path):
    from test_gateway import fixture, invoke
    app, store, session, calls, client = fixture(tmp_path)
    assert asyncio.run(invoke(app, client, body=b'x' * (MAX_BODY + 1))).status_code == 413
    assert not calls and store.events(session.session_id)[0].reason_code == 'llm.body_too_large'
