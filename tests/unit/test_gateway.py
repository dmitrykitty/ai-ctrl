import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from aictrl.gateway.app import create_app
from aictrl.gateway.session import GatewaySession
from aictrl.policy.models import AgentPolicy, LLMPolicy, Policy
from aictrl.reporting.store import EventStore, StoreFailure

TOKEN = 'synthetic_internal_identity_abcdefghijklmnopqrstuvwxyz'
PROVIDER = 'Bearer synthetic_provider_credential_never_store'
PROMPT = 'synthetic private prompt never store'
BODY = json.dumps({'model': 'synthetic-model', 'messages': [{'role': 'user', 'content': PROMPT}], 'stream': True, 'future_field': {'unchanged': True}}).encode()
FRAMES = [b'event: message_start\ndata: {"type":"message_start"}\n\n',
          b'event: ping\ndata: {"type":"ping"}\n\n',
          b'event: message_delta\ndata: {"type":"message_delta"}\n\n',
          b'event: message_stop\ndata: {"type":"message_stop"}\n\n']


class Frames(httpx.AsyncByteStream):
    def __init__(self, values=FRAMES, error=False):
        self.values, self.error, self.closed = values, error, False

    async def __aiter__(self):
        for value in self.values:
            yield value
        if self.error:
            raise httpx.ReadError('synthetic upstream exception with private details')

    async def aclose(self):
        self.closed = True


def fixture(tmp_path, *, policy=None, status=200, frames=None):
    session = GatewaySession(session_id=uuid4(), agent_id='claude', adapter='claude', user_id='local', profile_id='default',
                             expires_at=datetime.now(timezone.utc) + timedelta(minutes=5), session_token=TOKEN)
    policy = policy or Policy(schema_version=1, policy_version='t03', default_action='BLOCK',
                              agents={'claude': AgentPolicy(enabled=True)}, llm=LLMPolicy(messages='ALLOW', count_tokens='ALLOW'))
    store = EventStore(tmp_path / 'events.sqlite3')
    calls = []

    async def upstream(request):
        # Durable admission must already be visible through a fresh connection.
        events = EventStore(store.path).events(session.session_id)
        assert events and events[-1].reason_code == 'llm.policy.allowed'
        calls.append(request)
        return httpx.Response(status, stream=frames or Frames(), headers={
            'content-type': 'text/event-stream', 'request-id': 'synthetic-provider-request',
            'anthropic-ratelimit-unified-status': 'allowed', 'retry-after': '7', 'x-should-retry': 'false',
            'connection': 'keep-alive, x-hop', 'x-hop': 'remove', 'x-aictrl-session': 'must-strip',
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream), trust_env=False)
    app = create_app(session, policy, store, client)
    return app, store, session, calls, client


async def invoke(app, client, *, path='/anthropic/v1/messages?beta=true', method='POST', token=TOKEN, body=BODY, extra=None):
    headers = {'anthropic-version': '2023-06-01', 'anthropic-beta': 'oauth-future-beta,unchanged',
               'authorization': PROVIDER, 'content-type': 'application/json', 'x-app': 'cli',
               'anthropic-future-feature': 'preserve', 'x-claude-code-session-id': 'native-session',
               'connection': 'keep-alive, x-hop', 'x-hop': 'remove', 'x-upstream-host': 'evil.test'}
    if token is not None:
        headers['x-aictrl-session'] = token
    headers.update(extra or {})
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
            return await downstream.request(method, path, content=body, headers=headers)


@pytest.mark.parametrize('path', ['/anthropic/v1/messages?beta=true&x=a%2Fb', '/anthropic/v1/messages/count_tokens?beta=true'])
def test_native_forwarding_and_durable_attributable_events(tmp_path, path, caplog):
    app, store, session, calls, client = fixture(tmp_path)
    response = asyncio.run(invoke(app, client, path=path))
    assert response.status_code == 200 and response.content == b''.join(FRAMES)
    assert len(calls) == 1
    upstream = calls[0]
    assert str(upstream.url) == 'https://api.anthropic.com' + path.removeprefix('/anthropic')
    assert upstream.content == BODY
    for header, expected in [('anthropic-version', '2023-06-01'), ('anthropic-beta', 'oauth-future-beta,unchanged'), ('authorization', PROVIDER), ('anthropic-future-feature', 'preserve'), ('x-app', 'cli')]:
        assert upstream.headers[header] == expected
    assert upstream.headers['host'] == 'api.anthropic.com'
    assert int(upstream.headers['content-length']) == len(BODY)
    assert not any(name in upstream.headers for name in ('x-aictrl-session', 'connection', 'proxy-connection', 'x-hop', 'x-upstream-host'))
    assert response.headers['retry-after'] == '7' and response.headers['x-should-retry'] == 'false'
    assert response.headers['anthropic-ratelimit-unified-status'] == 'allowed'
    assert not any(name in response.headers for name in ('connection', 'x-hop', 'x-aictrl-session'))
    events = EventStore(store.path).events(session.session_id)
    assert [event.reason_code for event in events] == ['llm.policy.allowed', 'llm.upstream_completed']
    assert events[0].request_id == events[1].request_id
    assert all(event.channel == 'LLM' and event.inspection_level == 'STRUCTURED' and event.adapter == 'claude' for event in events)
    raw = store.path.read_bytes() + (store.path.with_name('events.sqlite3-wal').read_bytes() if store.path.with_name('events.sqlite3-wal').exists() else b'')
    for private in (TOKEN, PROVIDER, PROMPT):
        assert private.encode() not in raw and private not in caplog.text


@pytest.mark.parametrize('token', [None, 'wrong-token', 'é' * 40])
def test_missing_or_wrong_identity_blocks_without_upstream(tmp_path, token):
    app, store, session, calls, client = fixture(tmp_path)
    if token and not token.isascii():
        assert not session.accepts([token])
        return
    response = asyncio.run(invoke(app, client, token=token))
    assert response.status_code == 401 and not calls
    assert store.events(session.session_id)[0].reason_code == 'llm.invalid_session'


@pytest.mark.parametrize('method,path', [('GET', '/anthropic/v1/messages'), ('POST', '/unknown'), ('POST', '/anthropic/https://evil.test'), ('POST', '/anthropic/v1/models')])
def test_unsupported_method_and_path_are_durably_blocked(tmp_path, method, path):
    app, store, session, calls, client = fixture(tmp_path)
    response = asyncio.run(invoke(app, client, path=path, method=method))
    assert response.status_code == 403 and not calls
    assert store.events(session.session_id)[0].action == 'BLOCK'


@pytest.mark.parametrize('enabled,operation', [(False, 'ALLOW'), (True, 'BLOCK')])
def test_disabled_or_denied_policy_never_calls_upstream(tmp_path, enabled, operation):
    policy = Policy(schema_version=1, policy_version='denied', default_action='BLOCK',
                    agents={'claude': AgentPolicy(enabled=enabled)}, llm=LLMPolicy(messages=operation))
    app, store, session, calls, client = fixture(tmp_path, policy=policy)
    assert asyncio.run(invoke(app, client)).status_code == 403 and not calls
    assert store.events(session.session_id)[0].policy_version == 'denied'


def test_store_failure_before_admission_is_fail_closed(tmp_path, monkeypatch):
    app, store, session, calls, client = fixture(tmp_path)
    monkeypatch.setattr(store, 'append', lambda event: (_ for _ in ()).throw(StoreFailure('private failure details')))
    response = asyncio.run(invoke(app, client))
    assert response.status_code == 503 and not calls
    assert 'private failure' not in response.text


def test_policy_exception_is_fail_closed_and_audited(tmp_path):
    app, store, session, calls, client = fixture(tmp_path)

    async def run():
        async with app.router.lifespan_context(app):
            app.state.gateway.engine.decide = lambda *a: (_ for _ in ()).throw(RuntimeError('private policy details'))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                return await downstream.post('/anthropic/v1/messages', content=BODY, headers={'x-aictrl-session': TOKEN})

    response = asyncio.run(run())
    assert response.status_code == 503 and not calls
    assert store.events(session.session_id)[0].reason_code == 'llm.policy_error'


def test_caller_selected_upstream_is_never_used(tmp_path):
    app, store, session, calls, client = fixture(tmp_path)
    response = asyncio.run(invoke(app, client, path='/anthropic/v1/messages?upstream=http%3A%2F%2Fevil.test'))
    assert response.status_code == 200
    assert calls[0].url.host == 'api.anthropic.com'
    assert 'x-upstream-host' not in calls[0].headers


@pytest.mark.parametrize('status', [400, 401, 429, 503])
def test_provider_status_error_bytes_and_metadata_preserved(tmp_path, status):
    app, store, session, calls, client = fixture(tmp_path, status=status, frames=Frames([b'{"type":"error","error":{"type":"overloaded_error"}}']))
    response = asyncio.run(invoke(app, client))
    assert response.status_code == status and b'overloaded_error' in response.content
    assert len(calls) == 1 and store.events(session.session_id)[-1].reason_code == 'llm.upstream_failed'


def test_stream_transport_error_is_safe_and_audited(tmp_path):
    stream = Frames(error=True)
    app, store, session, calls, client = fixture(tmp_path, frames=stream)
    with pytest.raises(Exception) as error:
        asyncio.run(invoke(app, client))
    assert 'private details' not in str(error.value)
    assert stream.closed and store.events(session.session_id)[-1].reason_code == 'llm.upstream_failed'


def test_completion_audit_failure_does_not_recall_delivered_content(tmp_path, monkeypatch, caplog):
    app, store, session, calls, client = fixture(tmp_path)
    original = store.append
    def persist(event):
        if event.action == 'AUDIT':
            raise StoreFailure('private store details')
        original(event)
    monkeypatch.setattr(store, 'append', persist)
    response = asyncio.run(invoke(app, client))
    assert response.status_code == 200 and response.content == b''.join(FRAMES)
    assert 'Completion audit unavailable' in caplog.text and 'private store' not in caplog.text


def test_first_stream_bytes_arrive_before_upstream_finishes(tmp_path):
    async def run():
        release = asyncio.Event()
        first = asyncio.Event()
        class Paused(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield FRAMES[0]
                await release.wait()
                for frame in FRAMES[1:]:
                    yield frame
        app, store, session, calls, client = fixture(tmp_path, frames=Paused())
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
            await asyncio.wait_for(first.wait(), 1)
            assert sent == [FRAMES[0]] and not task.done()
            release.set()
            await task
            assert sent == FRAMES
    asyncio.run(run())


def test_actual_sqlite_write_error_blocks_before_upstream(tmp_path):
    import sqlite3
    app, store, session, calls, client = fixture(tmp_path)
    with sqlite3.connect(store.path) as connection:
        connection.execute('DROP TABLE events')
    response = asyncio.run(invoke(app, client))
    assert response.status_code == 503 and not calls


def test_expired_identity_and_duplicate_headers_are_rejected(tmp_path):
    app, store, session, calls, client = fixture(tmp_path)
    expired = session.model_copy(update={'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)})
    assert not expired.accepts([TOKEN])
    policy = Policy(schema_version=1, policy_version='t03', default_action='BLOCK', agents={'claude': AgentPolicy(enabled=True)}, llm=LLMPolicy(messages='ALLOW'))
    app = create_app(expired, policy, store, client)
    assert asyncio.run(invoke(app, client)).status_code == 401 and not calls
    assert not session.accepts([TOKEN, TOKEN])


@pytest.mark.parametrize('body', [b'not-json', b'[]', b'{"messages":"wrong"}', b'\xff'])
def test_invalid_native_body_is_blocked_without_upstream(tmp_path, body):
    app, store, session, calls, client = fixture(tmp_path)
    assert asyncio.run(invoke(app, client, body=body)).status_code == 400 and not calls
    assert store.events(session.session_id)[0].reason_code == 'llm.invalid_body'


def test_preheader_upstream_error_is_not_retried_and_is_safely_audited(tmp_path):
    app, store, session, calls, original = fixture(tmp_path)
    def fail(request):
        calls.append(request)
        raise httpx.ConnectError('synthetic-private-provider-details')
    client = httpx.AsyncClient(transport=httpx.MockTransport(fail), trust_env=False)
    policy = Policy(schema_version=1, policy_version='t03', default_action='BLOCK', agents={'claude': AgentPolicy(enabled=True)}, llm=LLMPolicy(messages='ALLOW'))
    app = create_app(session, policy, store, client)
    response = asyncio.run(invoke(app, client))
    assert response.status_code == 502 and len(calls) == 1
    assert 'private-provider' not in response.text
    assert [event.action for event in store.events(session.session_id)] == ['ALLOW', 'AUDIT']
    assert store.events(session.session_id)[-1].reason_code == 'llm.upstream_failed'
