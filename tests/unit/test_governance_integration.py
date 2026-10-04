"""Protected sends/backends must pass the actual governance and audit boundary."""

import asyncio
import json
import sqlite3
from datetime import timedelta
from uuid import uuid4

import httpx
from typer.testing import CliRunner

from aictrl.cli.main import app as cli
from aictrl.contracts import UsageMetric
from aictrl.gateway.app import create_app
from aictrl.governance.approvals import ApprovalManager
from aictrl.governance.store import GovernanceStore
from aictrl.policy.loader import load_policy
from aictrl.policy.models import GovernanceSettings
from aictrl.runtime.workspace import PROJECT_ROOT
from test_gateway import fixture, invoke, native_policy, Frames, BODY, TOKEN
from test_mcp import setup, DemoSemanticFake, with_sdk
from test_governance import Clock


def controlled(**changes):
    settings = GovernanceSettings.model_validate(changes)
    return native_policy().model_copy(update={'governance': settings})


def test_request_step_budget_blocks_before_send_with_durable_reason(tmp_path):
    policy = controlled(budgets=[dict(id='requests', scope='session', dimension='requests', limit=1, window_seconds=60)])
    app, store, session, calls, client = fixture(tmp_path, policy=policy)
    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                for status in (200, 403):
                    result = await downstream.post('/anthropic/v1/messages', content=BODY, headers={'X-AICtrl-Session': TOKEN})
                    assert result.status_code == status
    asyncio.run(run())
    assert len(calls) == 1
    assert store.events(session.session_id)[-1].reason_code == 'governance.budget.requests_exceeded'
    counters = app.state.governance.budgets()
    assert all(item.used + item.reserved == 1 for item in counters)


def test_real_store_failure_and_admission_audit_failure_no_send_or_spent_claims(tmp_path):
    app, store, session, calls, client = fixture(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute('DROP TABLE reservations')
    result = asyncio.run(invoke(app, client))
    assert result.status_code == 503 and not calls
    assert store.events(session.session_id)[-1].reason_code == 'governance.store_unavailable'
    assert not app.state.governance.budgets()


def test_native_usage_settles_conservative_reservation_safe_numeric_only(tmp_path):
    frames = [
        b'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":7,"output_tokens":0,"cache_read_input_tokens":3,"cache_creation_input_tokens":2}}}\n\n',
        b'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":4}}\n\n',
        b'event: message_stop\ndata: {"type":"message_stop"}\n\n']
    policy = controlled(budgets=[dict(id='tokens', scope='user', dimension='tokens', limit=100, window_seconds=60)],
                        token_reservation=20, input_token_allowance=5)
    app, store, session, calls, client = fixture(tmp_path, policy=policy, frames=Frames(frames))
    assert asyncio.run(invoke(app, client)).status_code == 200
    tokens = next(item for item in app.state.governance.budgets() if item.dimension == 'tokens')
    assert tokens.used == 16 and tokens.reserved == 0
    usage = store.events(session.session_id)[-1].usage
    assert usage.input_tokens == 12 and usage.output_tokens == 4 and usage.cost_microunits is None
    assert usage.billing_mode == 'SUBSCRIPTION' and usage.requests == usage.agent_steps == 1


def test_absent_or_invalid_usage_keeps_reservation_and_next_send_blocked(tmp_path):
    policy = controlled(budgets=[dict(id='tokens', scope='user', dimension='tokens', limit=25, window_seconds=60)],
                        token_reservation=20, input_token_allowance=5)
    app, store, session, calls, client = fixture(tmp_path, policy=policy)
    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                first = await downstream.post('/anthropic/v1/messages', content=BODY, headers={'X-AICtrl-Session': TOKEN})
                assert first.status_code == 200
                second = await downstream.post('/anthropic/v1/messages', content=BODY, headers={'X-AICtrl-Session': TOKEN})
                assert second.status_code == 403
    asyncio.run(run())
    tokens = next(item for item in app.state.governance.budgets() if item.dimension == 'tokens')
    assert tokens.used == 0 and tokens.reserved == 25 and len(calls) == 1


def test_official_sdk_host_cli_exact_approval_once_and_changed_args(tmp_path):
    app, session, store, backend = setup(tmp_path, DemoSemanticFake())
    project = tmp_path / 'control'
    (project / 'config').mkdir(parents=True)
    (project / 'config/project.yaml').write_bytes((PROJECT_ROOT / 'config/project.yaml').read_bytes())
    audit = project / '.aictrl/audit'
    audit.mkdir(parents=True)
    # CLI reads the actual same protected database used by the gateway.
    store = type(store)(audit / 'events.sqlite3')
    app = create_app(session, load_policy(PROJECT_ROOT / 'config/policy.yaml'), store,
                     semantic_provider=DemoSemanticFake(), backend=backend)
    runner = CliRunner()
    async def proof(client):
        args = {'confirmation': 'synthetic approved action'}
        pending = await client.call_tool('destructive_delete_all', args)
        assert pending.is_error and backend.invocations['destructive_delete_all'] == 0
        record, = app.state.governance.approvals(session.session_id)
        listing = runner.invoke(cli, ['approvals', '--project', str(project), '--session', str(session.session_id)])
        assert listing.exit_code == 0 and str(record.approval.approval_id) in listing.output
        assert record.approval.request_digest not in listing.output and args['confirmation'] not in listing.output
        approve = runner.invoke(cli, ['approve', str(record.approval.approval_id), '--project', str(project)])
        assert approve.exit_code == 0 and 'state=APPROVED' in approve.output
        outcomes = await asyncio.gather(client.call_tool('destructive_delete_all', args), client.call_tool('destructive_delete_all', args))
        assert sum(not result.is_error for result in outcomes) == 1
        assert backend.invocations['destructive_delete_all'] == 1
        replay = await client.call_tool('destructive_delete_all', args)
        assert replay.is_error and 'governance.approval.consumed' in str(replay)
        changed = await client.call_tool('destructive_delete_all', {'confirmation': 'different'})
        assert changed.is_error and 'governance.approval.required' in str(changed)
        assert backend.invocations['destructive_delete_all'] == 1
    asyncio.run(with_sdk(app, proof))
    assert b'synthetic approved action' not in store.path.read_bytes()
    events = store.events(session.session_id)
    assert sum(event.reason_code == 'mcp.backend_completed' for event in events) == 1
    assert any(event.action == 'REQUIRE_APPROVAL' for event in events)


def test_budget_denial_preserves_approved_record_and_audit_failure_refunds_before_backend(tmp_path, monkeypatch):
    app, session, store, backend = setup(tmp_path, DemoSemanticFake())
    async def proof(client):
        pending = await client.call_tool('destructive_delete_all', {})
        assert pending.is_error
        record, = app.state.governance.approvals()
        ApprovalManager(app.state.governance).approve(record.approval.approval_id)
        original = store.append
        def fail(event):
            if event.action == 'ALLOW':
                from aictrl.reporting.sink import StoreFailure
                raise StoreFailure('private fixture detail')
            original(event)
        monkeypatch.setattr(store, 'append', fail)
        # SDK produces a safe transport error; the backend is untouched.
        from mcp.shared.exceptions import MCPError
        try:
            await client.call_tool('destructive_delete_all', {})
        except MCPError:
            pass
        assert backend.invocations['destructive_delete_all'] == 0
        assert app.state.governance.approvals()[0].approval.state == 'APPROVED'
        assert all(item.used == item.reserved == 0 for item in app.state.governance.budgets())
    asyncio.run(with_sdk(app, proof))


def test_reload_block_precedence_and_same_version_snapshot_binding(tmp_path):
    app, session, store, backend = setup(tmp_path, DemoSemanticFake())
    pp = tmp_path / 'policy.yaml'
    initial = load_policy(PROJECT_ROOT / 'config/policy.yaml')
    pp.write_text(initial.model_dump_json())
    app = create_app(session, initial, store, semantic_provider=DemoSemanticFake(), backend=backend, policy_path=pp)
    async def proof(client):
        assert (await client.call_tool('destructive_delete_all', {})).is_error
        record, = app.state.governance.approvals()
        ApprovalManager(app.state.governance).approve(record.approval.approval_id)
        data = initial.model_dump(mode='json')
        data['agents']['demo-agent']['rules'][-1]['action'] = 'BLOCK'
        data['policy_version'] = 'reload-block'
        pp.write_text(json.dumps(data))
        app.state.snapshots.poll()
        blocked = await client.call_tool('destructive_delete_all', {})
        assert blocked.is_error and 'mcp.policy.blocked' in str(blocked) and backend.invocations['destructive_delete_all'] == 0
        data['agents']['demo-agent']['rules'][-1]['action'] = 'REQUIRE_APPROVAL'
        data['policy_version'] = initial.policy_version  # same label, different validated policy contents
        data['governance']['approval_ttl_seconds'] = 61
        pp.write_text(json.dumps(data))
        app.state.snapshots.poll()
        fresh = await client.call_tool('destructive_delete_all', {})
        assert fresh.is_error and 'governance.approval.required' in str(fresh)
        assert len(app.state.governance.approvals()) == 2 and backend.invocations['destructive_delete_all'] == 0
    asyncio.run(with_sdk(app, proof))


def test_cancelled_native_send_keeps_unknown_tokens_and_audits_failure(tmp_path):
    initial, store, session, _, old_client = fixture(tmp_path)
    policy = controlled(budgets=[dict(id='tokens', scope='user', dimension='tokens', limit=100, window_seconds=60)],
                        token_reservation=20, input_token_allowance=5)
    async def run():
        began = asyncio.Event()
        async def upstream(request):
            began.set()
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            app = create_app(session, policy, store, client)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway') as downstream:
                    task = asyncio.create_task(downstream.post('/anthropic/v1/messages', content=BODY, headers={'X-AICtrl-Session': TOKEN}))
                    await asyncio.wait_for(began.wait(), 2)
                    task.cancel()
                    import pytest
                    with pytest.raises(asyncio.CancelledError):
                        await task
                tokens = next(item for item in app.state.governance.budgets() if item.dimension == 'tokens')
                assert tokens.reserved == 25 and tokens.used == 0
        await old_client.aclose()
    asyncio.run(run())
    assert [event.reason_code for event in store.events(session.session_id)] == ['llm.policy.allowed', 'llm.upstream_failed']


def test_mcp_cancel_after_dispatch_spends_one_action_and_records_safe_outcome(tmp_path):
    from aictrl.mcp.demo_backend import DemoMCPBackend
    class PausedBackend(DemoMCPBackend):
        async def call_tool(self, name, arguments):
            self.invocations[name] += 1
            began.set()
            await asyncio.Event().wait()
    async def run():
        nonlocal began
        began = asyncio.Event()
        app, session, store, backend = setup(tmp_path, DemoSemanticFake(), PausedBackend())
        async with app.router.lifespan_context(app):
            task = asyncio.create_task(app.state.mcp.call_tool('safe_lookup', {}))
            await asyncio.wait_for(began.wait(), 2)
            task.cancel()
            import pytest
            with pytest.raises(asyncio.CancelledError):
                await task
            assert backend.invocations['safe_lookup'] == 1
            assert all(item.used == 1 and item.reserved == 0 for item in app.state.governance.budgets())
            assert store.events(session.session_id)[-1].reason_code == 'mcp.backend_cancelled'
    began = None
    asyncio.run(run())


def test_production_quota_accepts_native_128k_output_cap_and_keeps_full_reservation(tmp_path):
    policy = load_policy(PROJECT_ROOT / 'config/policy.yaml')
    data = policy.model_dump(mode='json')
    for rule in data['governance']['budgets']:
        if rule['id'] == 'user.tokens':
            rule['limit'] = 100000
    from aictrl.policy.models import Policy
    old = Policy.model_validate_json(json.dumps(data))
    body = json.dumps({'max_tokens': 128000, 'messages': [{'role': 'user', 'content': 'Synthetic quota compatibility proof'}], 'stream': True}).encode()
    previous, current = tmp_path / 'previous', tmp_path / 'current'
    previous.mkdir()
    current.mkdir()
    old_app, old_store, old_session, old_calls, old_client = fixture(previous, policy=old)
    assert asyncio.run(invoke(old_app, old_client, body=body)).status_code == 403 and not old_calls
    assert old_store.events(old_session.session_id)[-1].reason_code == 'governance.budget.tokens_exceeded'
    assert not old_app.state.governance.budgets()
    app, store, session, calls, client = fixture(current, policy=policy)
    assert asyncio.run(invoke(app, client, body=body)).status_code == 200 and len(calls) == 1
    tokens = next(item for item in app.state.governance.budgets() if item.dimension == 'tokens')
    assert tokens.limit == 256000 and tokens.reserved == 132096 and tokens.used == 0
