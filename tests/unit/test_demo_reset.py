"""Only terminal explicitly offline-demo rows may be removed."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from aictrl.governance.store import BudgetClaim, GovernanceStore
from aictrl.runtime.workspace import PROJECT_ROOT
from test_reporting import environment, event, record


def reset_module(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('test_demo_reset_script', PROJECT_ROOT / 'scripts/demo-reset.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data(tmp_path, state='TERMINATED', scope='session'):
    store, queries, clock = environment(tmp_path)
    native, demo = uuid4(), uuid4()
    for sid, kind in ((native, 'native'), (demo, 'offline-demo')):
        store.start_session(sid, 'demo-agent', 'demo-agent', None, clock(), kind=kind)
        store.lifecycle(sid, state if sid == demo else 'TERMINATED', ended=clock())
        record(store, event(clock, sid))
    governance = GovernanceStore(store.path, clock=clock)
    governance.reserve((BudgetClaim('demo.budget', scope, str(demo), 'tool_calls', 10, 60, 1),),
                       session_id=demo, request_id=uuid4(), policy_version='demo', snapshot_key='fixture')
    return store, queries, native, demo


def test_reset_preserves_native_history_and_workspace(tmp_path, monkeypatch):
    module = reset_module(monkeypatch)
    store, queries, native, demo = data(tmp_path)
    workspace = tmp_path / 'workspace'; workspace.mkdir(); sentinel = workspace / 'keep.txt'; sentinel.write_text('retain')
    assert module.reset_demo(store.path) == 1
    assert queries.events(session=native)['total'] == 1 and queries.events(session=demo)['total'] == 0
    assert queries.sessions()['total'] == 1 and queries.alerts(native)['total'] == 1
    assert sentinel.read_text() == 'retain' and module.reset_demo(store.path) == 0


@pytest.mark.parametrize('state,scope', [('ACTIVE', 'session'), ('TERMINATED', 'user')])
def test_active_or_shared_demo_reset_is_refused_atomically(tmp_path, monkeypatch, state, scope):
    module = reset_module(monkeypatch)
    store, queries, native, demo = data(tmp_path, state, scope)
    before = queries.summary()
    with pytest.raises(ValueError):
        module.reset_demo(store.path)
    assert queries.summary() == before and queries.events(session=native)['total'] == 1
