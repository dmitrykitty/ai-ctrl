"""Safe durable reporting, risk windows, escalation and host ownership."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.contracts import SecurityEvent
from aictrl.governance.store import GovernanceStore
from aictrl.policy.models import RiskSettings, ResponseSettings
from aictrl.policy.loader import load_policy
from aictrl.governance.reload import ConfigSnapshotManager
from aictrl.governance.store import BudgetClaim
from aictrl.reporting.queries import ReportingQueries, percentiles
from aictrl.reporting.risk import RiskEngine
from aictrl.reporting.service import ReportingStore
from aictrl.reporting.sink import StoreFailure
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import RuntimeFailure
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


class Clock:
    def __init__(self): self.now=datetime(2026,10,4,tzinfo=timezone.utc)
    def __call__(self): return self.now
    def advance(self, seconds): self.now+=timedelta(seconds=seconds)


def environment(tmp_path):
    (tmp_path/'config').mkdir()
    for name in ('policy.yaml','threat-feed.json'):
        shutil.copy(PROJECT_ROOT/'config'/name,tmp_path/'config'/name)
    clock=Clock(); path=tmp_path/'events.sqlite3'
    reporting=ReportingStore(path,clock=clock)
    GovernanceStore(path)
    return reporting, ReportingQueries(path,tmp_path,clock=clock), clock


def event(clock, session, **changes):
    fields=dict(session_id=session,request_id=uuid4(),agent_id='demo-agent',adapter='demo-agent',channel='MCP',
                direction='OUTBOUND',protocol=None,inspection_level='STRUCTURED',action='BLOCK',
                reason_code='guard.secret.detected',rule_ids=('operation.tool.echo_contact',),policy_version='test',
                occurred_at=clock())
    return SecurityEvent(**(fields|changes))


def record(store, item, risk=None, response=None):
    EventStore(store.path).append(item)
    store.observe_event(item,risk or RiskSettings(),response or ResponseSettings())


def test_counts_lifecycle_pagination_filter_and_no_payload(tmp_path):
    store,queries,clock=environment(tmp_path); sid=uuid4()
    store.start_session(sid,'demo-agent','demo-agent',None,clock(),kind='offline-demo')
    store.lifecycle(sid,'ACTIVE')
    first=event(clock,sid,action='REDACT',reason_code='guard.pii.redacted'); record(store,first)
    clock.advance(1)
    record(store,event(clock,sid,action='ALLOW',reason_code='mcp.policy.allowed',request_id=first.request_id))
    clock.advance(1);record(store,event(clock,sid))
    store.lifecycle(sid,'TERMINATED',ended=clock(),exit_code=0)
    summary=queries.summary()
    assert summary['sessions']==1 and summary['controlled_actions']==2
    assert (summary['allow'],summary['redacted'],summary['blocked'],summary['tool_calls'])==(1,1,1,1)
    rows=queries.events(limit=1)
    assert rows['total']==3 and rows['items'][0]['action']=='BLOCK'
    assert queries.events(action='ALLOW',channel='MCP',session=sid)['total']==1
    assert queries.events(since=clock())['total']==1
    assert queries.events(page=2,limit=1)['items'][0]['action']=='ALLOW'
    info=queries.sessions()['items'][0]
    assert info['state']=='TERMINATED' and info['kind']=='offline-demo' and info['duration_seconds']==2
    assert 'event_json' not in json.dumps(rows) and 'rule_ids' not in json.dumps(rows)
    assert 'workspace' not in json.dumps(info) and 'session_token' not in json.dumps(info)
    with pytest.raises(ValueError): queries.events(limit=101)


def test_risk_exact_explanation_escalation_dedup_and_expiry(tmp_path):
    store,queries,clock=environment(tmp_path); sid=uuid4()
    risk=RiskSettings(window_seconds=10,thresholds={'medium':25,'high':70,'critical':100})
    assert queries.risk(sid,risk)['score']==0
    first=event(clock,sid);record(store,first,risk)
    assert queries.risk(sid,risk)=={'score':40,'severity':'MEDIUM','window_seconds':10,'contributions':[{'rule':'guard.secret.detected','count':1,'points':40}]}
    store.observe_event(first,risk,ResponseSettings())
    assert queries.risk(sid,risk)['score']==40 and queries.alerts()['total']==1
    for _ in range(2): record(store,event(clock,sid),risk)
    assert queries.risk(sid,risk)['score']==120
    assert {row['severity'] for row in queries.alerts()['items']}=={'MEDIUM','HIGH','CRITICAL'}
    for _ in range(4): record(store,event(clock,sid),risk)
    assert queries.alerts()['total']==3
    clock.advance(11)
    assert queries.risk(sid,risk)['score']==0
    record(store,event(clock,sid),risk)
    assert queries.alerts()['total']==3  # renewed crossing suppressed by same-level cooldown
    clock.advance(60);record(store,event(clock,sid),risk)
    assert queries.alerts()['total']==4


@pytest.mark.parametrize('value',[-1,float('nan'),float('inf'),True,1.5,1001])
def test_risk_rejects_unbounded_weights(value):
    with pytest.raises(ValidationError): RiskSettings(weights={'guard.secret.detected':value})


def test_thresholds_and_response_settings_are_validated():
    with pytest.raises(ValidationError): RiskSettings(thresholds={'medium':50,'high':25,'critical':100})
    with pytest.raises(ValidationError): ResponseSettings(high='docker')
    with pytest.raises(ValidationError): ResponseSettings(alert_cooldown_seconds=0)
    risk=RiskSettings()
    with pytest.raises(TypeError): risk.weights['guard.secret.detected']=0
    assert RiskEngine(risk).contribution(event(Clock(),uuid4(),action='ALLOW')) is None


def test_stage_percentiles_and_durable_samples(tmp_path):
    store,queries,clock=environment(tmp_path);sid=uuid4()
    for value in (1,2,3,100): store.latency(sid,uuid4(),{'deterministic_guards':value,'semantic_jev':value*10,'total':value*11})
    assert queries.latency(sid)['deterministic_guards']=={'count':4,'p50':2,'p95':100,'p99':100}
    assert queries.latency(sid)['semantic_jev']['p50']==20
    assert percentiles([])['p50'] is None
    for invalid in (float('nan'),-1,float('inf')):
        with pytest.raises(ValueError): store.latency(sid,uuid4(),{'total':invalid})
    with pytest.raises(ValueError): store.latency(sid,uuid4(),{'raw-payload':1})


def test_semantic_summary_excludes_offline_fixtures_and_risk_uses_own_snapshot(tmp_path):
    store,queries,clock=environment(tmp_path)
    real,fixture=uuid4(),uuid4()
    manager=ConfigSnapshotManager(load_policy(tmp_path/'config/policy.yaml'))
    for sid,kind,semantic in ((real,'native','configured'),(fixture,'offline-demo','explicit-offline-fixture')):
        store.start_session(sid,'demo-agent','demo-agent',None,clock(),kind=kind)
        store.status(sid,manager.capture(),manager.status(),semantic)
        store.latency(sid,uuid4(),{'semantic_jev':200 if sid==real else 0.1,'total':201})
    assert queries.latency()['semantic_jev']=={'count':1,'p50':200,'p95':200,'p99':200}
    assert queries.latency(fixture)['semantic_jev']['p50']==0.1
    assert queries.status(fixture)['session_kind']=='offline-demo'
    risk=RiskSettings(thresholds={'medium':1,'high':2,'critical':3})
    policy=manager.capture().policy.model_copy(update={'risk':risk,'policy_version':'response-case'})
    own=ConfigSnapshotManager(policy)
    store.status(fixture,own.capture(),own.status(),'explicit-offline-fixture')
    record(store,event(clock,fixture),risk)
    store.status(real,manager.capture(),manager.status(),'configured')  # latest global observation has different thresholds
    assert queries.risk(fixture)['severity']=='CRITICAL'
    assert next(row for row in queries.sessions()['items'] if row['session_id']==str(fixture))['risk']['severity']=='CRITICAL'


def test_budget_warning_reserved_and_lazy_approval_expiry_counts(tmp_path):
    store,queries,clock=environment(tmp_path);sid=uuid4()
    governance=GovernanceStore(store.path,clock=clock)
    claim=BudgetClaim('demo.tools','session',str(sid),'tool_calls',10,60,8)
    admitted=governance.reserve((claim,),session_id=sid,request_id=uuid4(),policy_version='test',snapshot_key='fixture')
    assert admitted.reservation
    governance.dispatch(admitted.reservation)
    item=queries.budgets(sid)[0]
    assert item['used']==8 and item['reserved']==0 and item['percentage']==80 and item['status']=='WARNING'
    governance.reserve((),session_id=sid,request_id=uuid4(),policy_version='test',snapshot_key='fixture',
                       approval_digest='a'*64,operation_id='tool.destructive_delete_all',approval_ttl=1)
    assert queries.summary()['pending_approvals']==1
    clock.advance(2)
    assert queries.summary()['pending_approvals']==0 and queries.summary()['approval_states']['EXPIRED']==1


def test_malformed_storage_and_unavailable_database_fail_safely(tmp_path):
    store,queries,clock=environment(tmp_path);sid=uuid4();item=event(clock,sid);record(store,item)
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE events SET event_json=?', ('{"raw":"PRIVATE_SENTINEL"}',))
    with pytest.raises(StoreFailure) as error: queries.events()
    assert 'PRIVATE_SENTINEL' not in str(error.value)
    store.path.unlink()
    with pytest.raises(StoreFailure): queries.summary()


def runtime_with_alert(tmp_path, response):
    settings=load_config(PROJECT_ROOT)
    runtime=RuntimeSupervisor(tmp_path,settings,DemoAgentAdapter(settings.demo.image))
    runtime.reporting=ReportingStore(tmp_path/'events.sqlite3')
    runtime.reporting.start_session(runtime.session.identity.session_id,'demo-agent','demo-agent',None,datetime.now(timezone.utc),kind='verification')
    runtime.internal_network='synthetic-owned-network'
    runtime.session.identity.state='ACTIVE'
    risk=RiskSettings(thresholds={'medium':1,'high':2,'critical':3})
    item=event(lambda:datetime.now(timezone.utc),runtime.session.identity.session_id)
    record(runtime.reporting,item,risk,ResponseSettings(critical=response))
    return runtime


@pytest.mark.parametrize('response',['notify','restrict','terminate'])
def test_response_completed_once_and_only_owned_session(tmp_path,monkeypatch,response):
    runtime=runtime_with_alert(tmp_path,response);commands=[]
    monkeypatch.setattr(runtime,'_owned',lambda identifier:True)
    monkeypatch.setattr('aictrl.runtime.supervisor.docker',lambda args,**kw:commands.append(args) or subprocess.CompletedProcess(args,0,'',''))
    runtime._poll_responses(); runtime._response_poll_at=0;runtime._poll_responses()
    assert not runtime.reporting.pending(runtime.session.identity.session_id)
    assert len(commands)==(0 if response=='notify' else 1)
    if response=='restrict': assert commands[0][:2]==['network','disconnect'] and runtime.session.identity.state=='RESTRICTED'
    if response=='terminate': assert commands[0][:3]==['kill','--signal','SIGTERM'] and runtime._response_termination
    runtime.close()


def test_failed_or_foreign_response_never_completed_or_leaked(tmp_path,monkeypatch,capsys):
    runtime=runtime_with_alert(tmp_path,'restrict')
    monkeypatch.setattr(runtime,'_owned',lambda identifier:False)
    monkeypatch.setattr('aictrl.runtime.supervisor.docker',lambda *a,**kw:pytest.fail('unowned mutation'))
    runtime._poll_responses()
    with sqlite3.connect(runtime.reporting.path) as db:
        completed, failures=db.execute('SELECT response_completed_at,failures FROM alerts').fetchone()
        assert completed is None and failures==1
    runtime._response_poll_at=0
    monkeypatch.setattr(runtime,'_owned',lambda identifier:True)
    monkeypatch.setattr('aictrl.runtime.supervisor.docker',lambda *a,**kw:(_ for _ in ()).throw(RuntimeFailure('PRIVATE_DOCKER_DETAIL')))
    with sqlite3.connect(runtime.reporting.path) as db: db.execute('UPDATE alerts SET last_attempt_at=NULL')
    runtime._poll_responses()
    assert 'PRIVATE_DOCKER_DETAIL' not in capsys.readouterr().err
    with sqlite3.connect(runtime.reporting.path) as db:
        raw=json.loads(db.execute('SELECT alert_json FROM alerts').fetchone()[0]);raw['session_id']=str(uuid4())
        db.execute('UPDATE alerts SET last_attempt_at=NULL,alert_json=?',(json.dumps(raw),))
    with pytest.raises(StoreFailure): runtime.reporting.pending(runtime.session.identity.session_id)
    runtime.close()
