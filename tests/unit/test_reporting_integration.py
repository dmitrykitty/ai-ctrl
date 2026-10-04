"""Measurements and alert admission on the existing native and SDK paths."""

import asyncio
import json

from aictrl.gateway.app import create_app
from aictrl.reporting.queries import ReportingQueries
from aictrl.reporting.service import ReportingStore
from aictrl.reporting.sink import StoreFailure
from aictrl.runtime.workspace import PROJECT_ROOT
from test_gateway import FRAMES, Frames, fixture, invoke, native_policy
from test_mcp import DemoSemanticFake, setup, with_sdk


class MeasuredProvider(DemoSemanticFake):
    async def evaluate(self, segments):
        await asyncio.sleep(0.01)
        return await super().evaluate(segments)


class SlowFrames(Frames):
    async def __aiter__(self):
        for frame in self.values:
            await asyncio.sleep(0.01)
            yield frame


def test_native_full_stream_and_semantic_have_separate_durable_samples(tmp_path):
    original, store, session, calls, client = fixture(tmp_path, frames=SlowFrames())
    provider = MeasuredProvider()
    app = create_app(session, native_policy(), store, client, semantic_provider=provider)
    body = json.dumps({'messages': [{'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'fixture', 'content': 'ordinary external data'}]}], 'stream': True}).encode()
    response = asyncio.run(invoke(app, client, body=body))
    assert response.content == b''.join(FRAMES) and len(calls) == 1 and len(provider.calls) == 1
    metrics = ReportingQueries(store.path, PROJECT_ROOT).latency(session.session_id)
    assert all(metrics[stage]['count'] == 1 for stage in ('deterministic_guards', 'semantic_jev', 'governance', 'upstream_stream', 'total'))
    assert metrics['semantic_jev']['p50'] >= 9
    assert metrics['upstream_stream']['p50'] >= 35
    assert metrics['total']['p50'] >= metrics['upstream_stream']['p50']
    assert metrics['mcp_backend']['count'] == 0


def test_sdk_metrics_risk_and_safe_control_projection(tmp_path):
    app, session, store, backend = setup(tmp_path, MeasuredProvider())
    async def proof(client):
        assert not (await client.call_tool('echo_contact', {'contact': 'user@example.com'})).is_error
        assert (await client.call_tool('echo_contact', {'contact': 'AICTRL_SECRET_demo'})).is_error
    asyncio.run(with_sdk(app, proof))
    queries = ReportingQueries(store.path, PROJECT_ROOT)
    metrics = queries.latency(session.session_id)
    assert metrics['semantic_jev']['count'] == 1 and metrics['semantic_jev']['p50'] >= 9
    # SDK discovery is controlled and measured too; only the accepted tool
    # reaches the backend. The denied tool still has a total measurement.
    assert metrics['total']['count'] >= 2 and metrics['mcp_backend']['count'] == 1
    assert queries.risk(session.session_id)['score'] == 40
    assert len(queries.alerts(session.session_id)['items']) == 1
    assert queries.status()['semantic']['status'] == 'explicit-offline-fixture'
    serialized = json.dumps(queries.status())
    assert 'api_key' not in serialized and 'session_token' not in serialized and '/tmp/' not in serialized


def test_risk_write_failure_prevents_provider_send_after_durable_admission(tmp_path, monkeypatch):
    app, store, session, calls, client = fixture(tmp_path)
    def unavailable(*args):
        raise StoreFailure('PRIVATE_FAILURE_SENTINEL')
    monkeypatch.setattr(ReportingStore, 'observe_event', unavailable)
    response = asyncio.run(invoke(app, client))
    assert response.status_code == 503 and not calls and 'PRIVATE_FAILURE_SENTINEL' not in response.text
    assert store.events(session.session_id)[0].action == 'ALLOW'
