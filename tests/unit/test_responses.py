import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from aictrl.gateway.app import create_app
from aictrl.gateway.session import GatewaySession
from aictrl.policy.models import AdmissionRule, AgentPolicy, Policy
from aictrl.reporting.store import EventStore, StoreFailure
from test_gateway import Frames, TOKEN, PROVIDER, PROMPT

FRAMES = [b'event: response.created\ndata: {"type":"response.created"}\n\n',
          b'event: response.output_item.added\ndata: {"type":"response.output_item.added","item":{"type":"function_call","call_id":"call_1"}}\n\n',
          b'event: response.function_call_arguments.delta\ndata: {"type":"response.function_call_arguments.delta","delta":"{\\"cmd\\":\\"pwd\\"}"}\n\n',
          b'event: response.output_item.done\ndata: {"type":"response.output_item.done","item":{"type":"function_call","call_id":"call_1","arguments":"{\\"cmd\\":\\"pwd\\"}"}}\n\n',
          b'event: response.completed\ndata: {"type":"response.completed","response":{"usage":{"input_tokens":7,"output_tokens":3}}}\n\n']
BODY = json.dumps({'model':'native-model','instructions':PROMPT,'input':[{'role':'user','content':PROMPT}],
                   'tools':[{'type':'function','name':'exec_command','parameters':{'type':'object'}}],
                   'stream':True,'store':False,'future_field':{'unchanged':True}}).encode()


def fixture(tmp_path, *, enabled=True, action='ALLOW', status=200, store_error=False):
    session = GatewaySession(session_id=uuid4(), agent_id='codex', adapter='codex', protocol='RESPONSES', user_id='local', profile_id='default',
                             expires_at=datetime.now(timezone.utc)+timedelta(minutes=5),session_token=TOKEN)
    policy = Policy(schema_version=5, policy_version='t05', default_action='BLOCK',
                    agents={'codex': AgentPolicy(enabled=enabled, rules=(AdmissionRule(
                        id='native.responses', channel='LLM', direction='OUTBOUND', protocol='RESPONSES',
                        target='openai', operations=('responses',), action=action),))})
    store = EventStore(tmp_path/'events.sqlite3')
    if store_error:
        def fail(event): raise StoreFailure('safe store failure')
        store.append = fail
    calls = []
    async def upstream(request):
        assert EventStore(store.path).events(session.session_id)[-1].action == 'ALLOW'
        calls.append(request)
        return httpx.Response(status,stream=Frames(FRAMES),headers={'content-type':'text/event-stream',
              'x-request-id':'provider-request','x-ratelimit-remaining-requests':'7','retry-after':'3',
              'connection':'keep-alive, x-hop','x-hop':'remove','x-aictrl-session':'strip'})
    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream),trust_env=False)
    from guard_fakes import FakeSemanticProvider
    return create_app(session,policy,store,client,semantic_provider=FakeSemanticProvider()),session,store,calls,client


async def invoke(app, *, path='/codex/responses?x=a%2Fb&future=true', method='POST', token=TOKEN, body=BODY):
    headers = {'authorization':PROVIDER,'chatgpt-account-id':'synthetic-account','content-type':'application/json',
               'openai-beta':'responses','x-codex-future-feature':'retain','originator':'codex_cli_rs',
               'connection':'keep-alive, x-hop','x-hop':'remove','x-upstream-host':'evil.test'}
    if token is not None: headers['x-aictrl-session']=token
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://gateway') as client:
            return await client.request(method,path,headers=headers,content=body)


def test_responses_preserve_raw_protocol_headers_sse_and_durable_events(tmp_path,caplog):
    app,session,store,calls,_ = fixture(tmp_path)
    response = asyncio.run(invoke(app))
    assert response.status_code == 200 and response.content == b''.join(FRAMES)
    assert len(calls) == 1
    request = calls[0]
    assert str(request.url) == 'https://chatgpt.com/backend-api/codex/responses?x=a%2Fb&future=true'
    assert request.content == BODY
    assert request.headers['authorization'] == PROVIDER
    assert request.headers['chatgpt-account-id'] == 'synthetic-account'
    assert request.headers['x-codex-future-feature'] == 'retain'
    assert request.headers['host'] == 'chatgpt.com' and int(request.headers['content-length']) == len(BODY)
    assert not any(name in request.headers for name in ('x-aictrl-session','x-upstream-host','x-hop','connection'))
    assert response.headers['retry-after'] == '3' and response.headers['x-ratelimit-remaining-requests'] == '7'
    assert not any(name in response.headers for name in ('x-aictrl-session','x-hop','connection'))
    events = EventStore(store.path).events(session.session_id)
    assert [event.action for event in events] == ['ALLOW','AUDIT']
    assert events[0].request_id == events[1].request_id
    assert all(event.agent_id == event.adapter == 'codex' and event.protocol == 'RESPONSES'
               and event.inspection_level == 'STRUCTURED' and event.direction == 'OUTBOUND' for event in events)
    assert events[1].reason_code == 'llm.upstream_completed'
    raw = store.path.read_bytes()
    for secret in (TOKEN,PROVIDER,PROMPT,'synthetic-account'):
        assert secret.encode() not in raw and secret not in caplog.text


@pytest.mark.parametrize('arguments,kwargs,expected', [({}, {'token':None},401),({}, {'token':'wrong-token'},401),
    ({'enabled':False},{},403),({'action':'BLOCK'},{},403),({}, {'method':'GET'},403),
    ({},{'path':'/anthropic/v1/messages'},403),({},{'path':'/codex/v1/responses'},403),
    ({},{'path':'/codex/models'},403),({},{'body':b'{bad'},400),({},{'body':b'{"messages":[]}'},400),
    ({'store_error':True},{},503)])
def test_denied_responses_have_no_upstream_effect(tmp_path,arguments,kwargs,expected):
    app,session,store,calls,_ = fixture(tmp_path,**arguments)
    response = asyncio.run(invoke(app,**kwargs))
    assert response.status_code == expected and not calls
    if not arguments.get('store_error'):
        assert [event.action for event in store.events(session.session_id)] == ['BLOCK']


@pytest.mark.parametrize('status',[400,401,429,500,307])
def test_native_provider_errors_and_redirect_are_preserved_without_retries(tmp_path,status):
    app,session,store,calls,_ = fixture(tmp_path,status=status)
    response = asyncio.run(invoke(app))
    assert response.status_code == status and response.content == b''.join(FRAMES) and len(calls) == 1
    assert store.events(session.session_id)[-1].reason_code == ('llm.upstream_failed' if status>=400 else 'llm.upstream_completed')


def test_tool_call_and_matching_followup_remain_native(tmp_path):
    app,session,store,calls,_ = fixture(tmp_path)
    first = asyncio.run(invoke(app))
    followup = json.dumps({'model':'native-model','input':[{'type':'function_call','call_id':'call_1','name':'exec_command','arguments':'{}'},
                           {'type':'function_call_output','call_id':'call_1','output':'synthetic-private-tool-output'}],'stream':True}).encode()
    second = asyncio.run(invoke(app,body=followup))
    assert first.status_code == second.status_code == 200
    assert calls[-1].content == followup
    assert [event.action for event in store.events(session.session_id)] == ['ALLOW','AUDIT','ALLOW','AUDIT']
    assert b'synthetic-private-tool-output' not in store.path.read_bytes()
