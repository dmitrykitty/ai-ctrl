"""Bounded native subscription qualification with safe failure classification."""
import json
from datetime import datetime, timezone
from pathlib import Path

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.codex import CodexAdapter
from aictrl.contracts import AgentSession
from aictrl.reporting.store import EventStore
from aictrl.runtime.codex_auth import codex_authenticated
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


def main():
    settings = load_config(PROJECT_ROOT)
    assert codex_authenticated(settings.codex.image), 'Native ChatGPT authentication required'
    settings.limits.wall_time_seconds = 90
    workspace = PROJECT_ROOT/'demo/project'
    identity = AgentSession(agent_id='codex',adapter='codex',user_id='local',profile_id='local',workspace=str(workspace),
                            protocol='RESPONSES',billing_mode='SUBSCRIPTION',started_at=datetime.now(timezone.utc))
    agent = CodexAdapter(settings.codex.image,RoutingMode.EGRESS_ONLY).render_config(identity)
    runtime = RuntimeSupervisor(workspace,settings,agent)
    source = (PROJECT_ROOT/'tests/fixtures/codex_live_probe.py').read_text()
    code, output = runtime.run(('python','-c',source),input_text='Reply with exactly: AICTRL_CODEX_OK',capture_output=True)
    lines = [line for line in output.splitlines() if line.startswith('AICTRL_CODEX_LIVE ')]
    assert code == 0 and len(lines) == 1, 'Safe native experiment result unavailable'
    result = json.loads(lines[0].removeprefix('AICTRL_CODEX_LIVE '))
    expected = {'native_exit','exact_response','http_statuses','invalid_api_key','missing_model_request_scope',
                'unsupported_authentication','configuration_error','forbidden_status','forbidden_request_id','direct_blocked','proxy_denied'}
    assert set(result) == expected and type(result['native_exit']) is int
    assert all(type(result[field]) is bool for field in expected-{'native_exit','http_statuses','forbidden_status','forbidden_request_id'})
    assert isinstance(result['http_statuses'],list) and all(type(value) is int and 400 <= value < 600 for value in result['http_statuses'])
    result['session']=str(runtime.session.identity.session_id)
    events = EventStore(PROJECT_ROOT/settings.gateway.audit_directory/'events.sqlite3').events(runtime.session.identity.session_id)
    result['events'] = [{'event_id':str(event.event_id),'request_id':str(event.request_id),'action':event.action,'reason':event.reason_code} for event in events]
    result['cleanup'] = not docker(['ps','--all','--quiet','--filter','label=io.aictrl.session='+runtime.identifier]).stdout.strip()
    print(json.dumps(result,sort_keys=True))
    passed = result['native_exit'] == 0 and result['exact_response'] and result['forbidden_status'] == 403 and result['direct_blocked'] and result['proxy_denied'] and result['cleanup']
    return 0 if passed else 1


if __name__ == '__main__': raise SystemExit(main())
