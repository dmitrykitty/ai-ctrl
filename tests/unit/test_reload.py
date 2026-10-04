"""Candidate validation, independent reload and immutable in-flight snapshot."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from aictrl.governance.reload import ConfigSnapshotManager
from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import InspectionSegment, Source
from aictrl.guards.threat_feed import ThreatFeed, load_feed
from aictrl.policy.models import Policy, GovernanceSettings
from test_gateway import native_policy, fixture, Frames, TOKEN, BODY


def feed(version='test', pattern='AICTRL_FEED_MARKER', *, kind='literal', **changes):
    return dict(schema_version=1, feed_version=version, signatures=[dict(signature_id='test.signature', revision=1,
        kind=kind, pattern=pattern, action='BLOCK', severity='HIGH', channels=['LLM', 'MCP'], enabled=True) | changes])


def files(tmp_path):
    policy_path, feed_path = tmp_path / 'policy.yaml', tmp_path / 'feed.json'
    policy_path.write_text(native_policy(version='one').model_dump_json())
    feed_path.write_text(json.dumps(feed()))
    return policy_path, feed_path


@pytest.mark.parametrize('change', [
    {'scope': 'workspace'}, {'dimension': 'money'}, {'limit': 0}, {'limit': True}, {'window_seconds': 0},
    {'window_seconds': 86401}, {'unknown': True}, {'id': 'runaway.agent_steps'}])
def test_strict_governance_rejects_bad_rules(change):
    rule = dict(id='test', scope='session', dimension='requests', limit=10, window_seconds=60) | change
    with pytest.raises(ValidationError):
        GovernanceSettings.model_validate({'budgets': [rule]})


def test_duplicate_budget_unknown_fields_and_old_schema_rejected(tmp_path):
    rule = dict(id='test', scope='session', dimension='requests', limit=10, window_seconds=60)
    with pytest.raises(ValidationError):
        GovernanceSettings.model_validate({'budgets': [rule, rule]})
    with pytest.raises(ValidationError):
        GovernanceSettings.model_validate({'approval_ttl_seconds': 0})
    with pytest.raises(ValidationError):
        GovernanceSettings.model_validate({'secret': 'synthetic private YAML'})
    from aictrl.policy.loader import load_policy
    for version in (1, 2, 3, 4):
        path = tmp_path / 'old.yaml'
        path.write_text(f'schema_version: {version}\nsecret: private\n')
        with pytest.raises(ValueError, match='configuration schema 5 is required'):
            load_policy(path)


@pytest.mark.parametrize('candidate', [feed(kind='semantic'), feed(kind='regex', pattern='(a+)+$'),
    feed(kind='regex', pattern='a.*b'), feed(kind='regex', pattern='['), feed(kind='regex', pattern=r'(x)\1'),
    feed(action='ALLOW'), feed(pattern='x' * 257), feed(enabled='true'), feed(schema_version=2)])
def test_feed_rejects_unsupported_invalid_or_unbounded(candidate, tmp_path):
    path = tmp_path / 'feed.json'
    path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError, match='missing or invalid') as error:
        load_feed(path)
    assert 'pattern' not in str(error.value)


def test_feed_duplicate_ids_and_bounds(tmp_path):
    data = feed()
    data['signatures'] *= 2
    path = tmp_path / 'feed.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_feed(path)
    data = feed()
    data['signatures'] = []
    data['unknown'] = 'private marker'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_feed(path)


def test_literal_regex_channel_privacy_and_semantic_order(tmp_path):
    from guard_fakes import FakeSemanticProvider
    data = feed(kind='regex', pattern=r'AICTRL_THREAT_[0-9][0-9]')
    path = tmp_path / 'feed.json'
    path.write_text(json.dumps(data))
    fake = FakeSemanticProvider()
    guards = GuardEngine(native_policy().guards, fake, feed=load_feed(path))
    async def run():
        matched = await guards.inspect_input((InspectionSegment('s', 'AICTRL_THREAT_42', Source.TOOL_RESULT, untrusted_external=True),))
        assert matched.action == 'BLOCK' and not fake.calls
        assert 'threat.test.signature' in matched.identifiers
        secret = await guards.inspect_input((InspectionSegment('s', 'AICTRL_SECRET_x AICTRL_THREAT_42', Source.TOOL_RESULT, untrusted_external=True),))
        assert secret.reason_code == 'guard.secret.detected' and not fake.calls
        pii = await guards.inspect_output((InspectionSegment('s', 'user@example.com AICTRL_THREAT_42', Source.MODEL_OUTPUT),), semantic=True)
        assert pii.reason_code == 'guard.pii.output_blocked' and not fake.calls
        other = await guards.inspect_input((InspectionSegment('s', 'AICTRL_THREAT_42', Source.USER_INPUT),), channel='API')
        assert other.action == 'ALLOW'
    asyncio.run(run())


def test_independent_reload_retains_last_good_and_freezes_nested_config(tmp_path):
    pp, fp = files(tmp_path)
    manager = ConfigSnapshotManager(native_policy(version='one'), feed=load_feed(fp), policy_path=pp, feed_path=fp)
    original = manager.capture()
    pp.write_text('private YAML: [ invalid')
    fp.write_text(json.dumps(feed('two', pattern='new safe marker')))
    manager.poll()
    assert manager.capture().policy.policy_version == 'one' and manager.capture().feed.feed_version == 'two'
    assert manager.status()['last_policy_reload_status'] == 'invalid_candidate'
    fp.write_text(json.dumps(feed('three', kind='regex', pattern='(x+)+')))
    pp.with_suffix('.tmp').write_text(native_policy(version='two', action='BLOCK').model_dump_json())
    pp.with_suffix('.tmp').replace(pp)  # editor-style atomic replacement
    manager.poll()
    assert manager.capture().policy.policy_version == 'two' and manager.capture().feed.feed_version == 'two'
    assert original.policy.policy_version == 'one' and original.feed.feed_version == 'test'
    assert manager.status()['last_feed_reload_status'] == 'invalid_candidate'
    with pytest.raises(TypeError):
        manager.capture().policy.agents['other'] = None
    with pytest.raises(ValidationError):
        manager.capture().policy.guards.semantic.enabled = False
    with pytest.raises(ValidationError):
        manager.capture().feed.signatures[0].pattern = 'mutated'


def test_background_reload_and_active_stream_keeps_original_guard_and_version(tmp_path):
    from aictrl.gateway.app import create_app
    from aictrl.guards.threat_feed import ThreatFeed
    pp, fp = files(tmp_path)
    fp.write_text(ThreatFeed().model_dump_json())
    initial = native_policy(version='one')
    async def run():
        release = asyncio.Event()
        first = asyncio.Event()
        class Paused(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'event: message_start\ndata: {"type":"message_start"}\n\n'
                await release.wait()
                yield b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":"AICTRL_FEED_MARKER"}}\n\n'
                yield b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
                yield b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        _, store, session, _, client = fixture(tmp_path, policy=initial, frames=Paused())
        app = create_app(session, initial, store, client, policy_path=pp, feed_path=fp)
        sent = []
        async def send(message):
            if message['type'] == 'http.response.body' and message.get('body'):
                sent.append(message['body'])
                first.set()
        async def receive():
            return {'type': 'http.request', 'body': BODY, 'more_body': False}
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1',
                 'method': 'POST', 'scheme': 'http', 'path': '/anthropic/v1/messages', 'raw_path': b'/anthropic/v1/messages',
                 'query_string': b'', 'headers': [(b'x-aictrl-session', TOKEN.encode())],
                 'server': ('gateway', 8000), 'client': ('synthetic', 1), 'root_path': ''}
        async with app.router.lifespan_context(app):
            task = asyncio.create_task(app(scope, receive, send))
            await asyncio.wait_for(first.wait(), 2)
            pp.write_text(native_policy(version='two').model_dump_json())
            fp.write_text(json.dumps(feed('two')))
            for _ in range(30):
                if app.state.snapshots.capture().feed.feed_version == 'two':
                    break
                await asyncio.sleep(0.05)
            assert app.state.snapshots.status()['active_policy_version'] == 'two'
            release.set()
            await task
            assert any(b'AICTRL_FEED_MARKER' in chunk for chunk in sent)
            assert all(event.policy_version == 'one' for event in store.events(session.session_id))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                blocked = await downstream.post('/anthropic/v1/messages', json={'messages': [{'role': 'user', 'content': 'AICTRL_FEED_MARKER'}]}, headers={'X-AICtrl-Session': TOKEN})
                assert blocked.status_code == 403
            event = store.events(session.session_id)[-1]
            assert event.policy_version == 'two' and 'threat.test.signature' in event.rule_ids
        await client.aclose()
    asyncio.run(run())
