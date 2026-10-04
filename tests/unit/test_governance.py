"""Actual SQLite rollback, windows, approvals and simultaneous contention."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4
import sqlite3

import pytest

from aictrl.contracts import ControlRequest, PolicyContext, UsageMetric
from aictrl.governance.approvals import ApprovalManager, request_digest
from aictrl.governance.budgets import BudgetManager
from aictrl.governance.store import BudgetClaim, GovernanceStore, GovernanceFailure
from aictrl.policy.models import GovernanceSettings


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    def __call__(self):
        return self.now
    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def identities():
    sid = uuid4()
    context = PolicyContext(session_id=sid, agent_id='claude', user_id='uid-1000', profile_id='local', policy_version='test')
    request = ControlRequest(session_id=sid, channel='LLM', direction='OUTBOUND', protocol='ANTHROPIC_MESSAGES',
                             inspection_level='STRUCTURED', target_id='anthropic', operation_id='messages', created_at=datetime.now(timezone.utc))
    return context, request


def claim(dimension='requests', amount=1, limit=10, *, scope='session', scope_id='test', window=60):
    return BudgetClaim('test.' + dimension, scope, scope_id, dimension, limit, window, amount)


def reserve(store, claims, context=None, request=None, **kwargs):
    if context is None:
        context, request = identities()
    return store.reserve(tuple(claims), session_id=context.session_id, request_id=request.request_id,
                         policy_version=context.policy_version, snapshot_key='snapshot-a', **kwargs)


def test_all_or_nothing_three_claims_no_partial_counters(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    reserved = reserve(store, [claim('tokens', 10, 10)])
    before = [item.model_dump() for item in store.budgets()]
    blocked = reserve(store, [claim(), claim('agent_steps'), claim('tokens', 1, 10)])
    assert blocked.reason == 'governance.budget.tokens_exceeded'
    assert before == [item.model_dump() for item in store.budgets()]
    store.cancel(reserved.reservation)
    assert all(item.used == item.reserved == 0 for item in store.budgets())


def test_fifty_simultaneous_transactions_limit_ten(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    barrier = Barrier(50)
    def attempt(_):
        barrier.wait()
        return reserve(store, [claim()])
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(attempt, range(50)))
    assert sum(result.reservation is not None for result in results) == 10
    assert sum(result.reason == 'governance.budget.requests_exceeded' for result in results) == 40
    state, = store.budgets()
    assert state.used == 0 and state.reserved == 10


def test_deterministic_fixed_window_and_session_lifetime(tmp_path):
    clock = Clock()
    store = GovernanceStore(tmp_path / 'events.sqlite3', clock=clock)
    context, request = identities()
    settings = GovernanceSettings.model_validate({'budgets': [dict(id='window', scope='session', dimension='requests', limit=1, window_seconds=60)],
                                                  'runaway': {'max_agent_steps': 2, 'max_tool_calls': 2}})
    manager = BudgetManager(store)
    first = manager.reserve(context, request, settings, snapshot_key='a')
    store.dispatch(first.reservation)
    assert manager.reserve(context, request, settings, snapshot_key='a').reason == 'governance.budget.requests_exceeded'
    clock.advance(60)
    second = manager.reserve(context, request, settings, snapshot_key='a')
    store.dispatch(second.reservation)
    clock.advance(60)
    assert manager.reserve(context, request, settings, snapshot_key='a').reason == 'governance.runaway.agent_steps_exceeded'
    windows = [b for b in store.budgets() if b.dimension == 'requests']
    assert len(windows) == 2 and (windows[1].window_start - windows[0].window_start).total_seconds() == 60


@pytest.mark.parametrize('scope', ['session', 'agent', 'user', 'profile'])
def test_all_scopes_share_only_trusted_selected_identity(tmp_path, scope):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    context, request = identities()
    settings = GovernanceSettings.model_validate({'budgets': [dict(id='scoped', scope=scope, dimension='requests', limit=1, window_seconds=60)]})
    manager = BudgetManager(store)
    assert manager.reserve(context, request, settings, snapshot_key='a').reservation
    other = context.model_copy(update={'session_id': uuid4()})
    other_request = request.model_copy(update={'session_id': other.session_id, 'request_id': uuid4()})
    outcome = manager.reserve(other, other_request, settings, snapshot_key='a')
    assert (outcome.reservation is not None) == (scope == 'session')


def test_token_settlement_known_unknown_and_excess_actual(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    context, request = identities()
    admission = reserve(store, [claim('tokens', 9, 10)], context, request)
    store.dispatch(admission.reservation)
    usage = UsageMetric(session_id=context.session_id, request_id=request.request_id,
                        input_tokens=2, output_tokens=3, billing_mode='SUBSCRIPTION')
    store.settle(admission.reservation, usage)
    store.settle(admission.reservation, usage)  # exactly once
    state, = store.budgets()
    assert state.used == 5 and state.reserved == 0
    unknown = reserve(store, [claim('tokens', 5, 10)])
    store.dispatch(unknown.reservation)
    store.settle(unknown.reservation, None)
    assert reserve(store, [claim('tokens', 1, 10)]).reason == 'governance.budget.tokens_exceeded'
    state, = store.budgets()
    assert state.used == 5 and state.reserved == 5
    # Never invent a refund after dispatch or unknown actual usage.
    store.cancel(unknown.reservation)
    assert store.budgets()[0].reserved == 5


def test_approval_digest_exact_canonical_session_operation_binding():
    context, request = identities()
    a = {'tag': 'synthetic private argument', 'nested': {'b': 2, 'a': 1}}
    b = {'nested': {'a': 1, 'b': 2}, 'tag': 'synthetic private argument'}
    digest = request_digest(context, request, a)
    assert digest == request_digest(context, request.model_copy(update={'request_id': uuid4()}), b)
    assert digest != request_digest(context, request, a | {'tag': 'changed'})
    assert digest != request_digest(context, request.model_copy(update={'operation_id': 'count_tokens'}), a)
    assert digest != request_digest(context.model_copy(update={'session_id': uuid4()}), request, a)
    with pytest.raises(ValueError):
        request_digest(context, request, {'invalid': float('nan')})


def test_approved_record_and_every_claim_commit_together(tmp_path):
    clock = Clock()
    store = GovernanceStore(tmp_path / 'events.sqlite3', clock=clock)
    context, request = identities()
    digest = request_digest(context, request, {'tag': 'private synthetic argument'})
    kwargs = dict(approval_digest=digest, operation_id='tool.synthetic', approval_ttl=60)
    pending = reserve(store, [claim('tokens', 11, 10)], context, request, **kwargs)
    assert pending.reason == 'governance.approval.required' and not store.budgets()
    approved = ApprovalManager(store).approve(pending.approval_id)
    assert approved.approval.state == 'APPROVED'
    blocked = reserve(store, [claim(), claim('tokens', 11, 10)], context, request, **kwargs)
    assert blocked.reason == 'governance.budget.tokens_exceeded' and not store.budgets()
    assert store.approvals()[0].approval.state == 'APPROVED'
    admitted = reserve(store, [claim(), claim('tokens', 9, 10)], context, request, **kwargs)
    assert admitted.reservation and store.approvals()[0].approval.state == 'CONSUMED'
    store.cancel(admitted.reservation)  # no dispatch/audit yet
    assert store.approvals()[0].approval.state == 'APPROVED'
    assert all(item.used == item.reserved == 0 for item in store.budgets())
    assert b'private synthetic argument' not in store.path.read_bytes()


def test_two_concurrent_approved_retries_only_one_consumes(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    context, request = identities()
    digest = request_digest(context, request, {})
    pending = reserve(store, [claim()], context, request, approval_digest=digest)
    ApprovalManager(store).approve(pending.approval_id)
    barrier = Barrier(2)
    def attempt(_):
        barrier.wait()
        return reserve(store, [claim()], context, request, approval_digest=digest)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(result.reservation is not None for result in results) == 1
    assert sum(result.reason == 'governance.approval.consumed' for result in results) == 1
    state, = store.budgets()
    assert state.reserved == 1


def test_expiry_denial_new_arguments_and_policy_binding(tmp_path):
    clock = Clock()
    store = GovernanceStore(tmp_path / 'events.sqlite3', clock=clock)
    context, request = identities()
    kwargs = dict(approval_digest=request_digest(context, request, {}), approval_ttl=60)
    pending = reserve(store, [claim()], context, request, **kwargs)
    ApprovalManager(store).approve(pending.approval_id)
    changed = reserve(store, [claim()], context, request, approval_digest=request_digest(context, request, {'changed': True}))
    assert changed.reason == 'governance.approval.required' and changed.approval_id != pending.approval_id
    ApprovalManager(store).deny(changed.approval_id)
    assert store.approvals()[0].approval.state == 'DENIED'
    new_version = context.model_copy(update={'policy_version': 'new'})
    assert reserve(store, [claim()], new_version, request, **kwargs).reason == 'governance.approval.required'
    clock.advance(60)
    assert reserve(store, [claim()], context, request, **kwargs).reason == 'governance.approval.expired'
    assert not store.budgets()
    assert ApprovalManager(store).approve(pending.approval_id).approval.state == 'EXPIRED'


def test_actual_sqlite_failure_is_sanitized_and_not_admitted(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    with sqlite3.connect(store.path) as db:
        db.execute('DROP TABLE budget_counters')
    with pytest.raises(GovernanceFailure, match='Governance store unavailable'):
        reserve(store, [claim()])


def test_duplicate_claims_rejected_and_settling_excess_actual_charges_all(tmp_path):
    store = GovernanceStore(tmp_path / 'events.sqlite3')
    with pytest.raises(GovernanceFailure):
        reserve(store, [claim(), claim()])
    assert not store.budgets()
    context, request = identities()
    admitted = reserve(store, [claim('tokens', 5, 10)], context, request)
    store.dispatch(admitted.reservation)
    store.settle(admitted.reservation, UsageMetric(session_id=context.session_id, request_id=request.request_id,
                 input_tokens=15, output_tokens=4, billing_mode='SUBSCRIPTION'))
    state, = store.budgets()
    assert state.used == 19 and state.reserved == 0
    assert reserve(store, [claim('tokens', 1, 10)]).reason == 'governance.budget.tokens_exceeded'
