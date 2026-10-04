import asyncio
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from aictrl.gateway.app import create_app
from aictrl.gateway.session import GatewaySession
from aictrl.guards.semantic import QUESTIONS,SemanticAssessment
from aictrl.mcp.demo_backend import DemoMCPBackend,POISON,PRIVATE_SENTINEL
from aictrl.policy.loader import load_policy
from aictrl.runtime.workspace import PROJECT_ROOT
from aictrl.reporting.store import EventStore
from aictrl.reporting.sink import StoreFailure
from guard_fakes import FakeSemanticProvider
from test_gateway import TOKEN


class DemoSemanticFake(FakeSemanticProvider):
    async def evaluate(self,segments):
        self.calls.append(segments)
        poisoned=any(segment.text==POISON for segment in segments)
        return SemanticAssessment(dict.fromkeys(QUESTIONS,0.99 if poisoned else 0.01))


def setup(tmp_path,provider=None,backend=None):
    session=GatewaySession(session_id=uuid4(),agent_id='demo-agent',adapter='demo-agent',protocol=None,
                           user_id='local',profile_id='default',expires_at=datetime.now(timezone.utc)+timedelta(minutes=5),session_token=TOKEN)
    store=EventStore(tmp_path/'events.sqlite3')
    backend=backend or DemoMCPBackend()
    app=create_app(session,load_policy(PROJECT_ROOT/'config/policy.yaml'),store,
                   semantic_provider=provider,backend=backend)
    return app,session,store,backend


async def with_sdk(app,proof,*,token=TOKEN):
    async with app.router.lifespan_context(app):
        headers={'X-AICtrl-Session':token} if token else {}
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),headers=headers,trust_env=False) as http:
            async with Client(streamable_http_client('http://gateway:8000/mcp',http_client=http),cache=None) as client:
                return await proof(client)


def test_official_sdk_discovery_independent_authorization_memory_and_no_leaks(tmp_path,caplog):
    fake=DemoSemanticFake()
    app,session,store,backend=setup(tmp_path,fake)
    async def proof(client):
        tools=await client.list_tools()
        names={tool.name for tool in tools.tools}
        assert names=={'safe_lookup','echo_contact','poisoned_document','destructive_delete_all'}
        resources=await client.list_resources()
        assert {str(resource.uri) for resource in resources.resources}=={'memory://project/demo'}
        safe=await client.call_tool('safe_lookup',{})
        assert not safe.is_error and 'AICTRL_SAFE_LOOKUP_OK' in safe.content[0].text
        forbidden=await client.call_tool('destructive_delete_all',{})
        assert forbidden.is_error and 'governance.approval.required' in str(forbidden) and backend.invocations['destructive_delete_all']==0
        project=await client.read_resource('memory://project/demo')
        assert project.contents[0].text=='AICTRL_PROJECT_MEMORY_OK'
        with pytest.raises(MCPError):
            await client.read_resource('memory://private/demo')
        assert backend.private_reads==0
        poisoned=await client.call_tool('poisoned_document',{})
        assert poisoned.is_error and POISON not in str(poisoned)
        assert backend.invocations['poisoned_document']==1
    asyncio.run(with_sdk(app,proof))
    events=store.events(session.session_id)
    assert any(event.action=='BLOCK' and event.reason_code=='guard.semantic.prompt_injection' for event in events)
    assert all(event.channel=='MCP' and event.protocol is None and event.schema_version==1 for event in events)
    assert all(event.agent_id==event.adapter=='demo-agent' and event.inspection_level=='STRUCTURED' for event in events)
    for private in (POISON,PRIVATE_SENTINEL,TOKEN):
        assert private not in caplog.text and private.encode() not in store.path.read_bytes()


def test_mcp_arguments_secret_block_and_pii_redaction_before_execution(tmp_path):
    fake=DemoSemanticFake()
    app,session,store,backend=setup(tmp_path,fake)
    async def proof(client):
        blocked=await client.call_tool('echo_contact',{'contact':'AICTRL_SECRET_demo'})
        assert blocked.is_error and backend.invocations['echo_contact']==0 and not fake.calls
        redacted=await client.call_tool('echo_contact',{'contact':'user@example.com'})
        assert not redacted.is_error and redacted.content[0].text=='[REDACTED_EMAIL_ADDRESS]'
        assert backend.last_contact=='[REDACTED_EMAIL_ADDRESS]'
        assert fake.calls[-1][0].text=='[REDACTED_EMAIL_ADDRESS]'
    asyncio.run(with_sdk(app,proof))
    operations=[event for event in store.events(session.session_id) if 'operation.tool.echo_contact' in event.rule_ids]
    assert [event.action for event in operations]==['BLOCK','REDACT','ALLOW','AUDIT']
    assert all(value not in store.path.read_bytes() for value in (b'user@example.com',b'AICTRL_SECRET_demo'))


@pytest.mark.parametrize('text,reason', [('AICTRL_SECRET_demo','guard.secret.detected'),
                                       ('user@example.com','guard.pii.output_blocked'),
                                       ('ordinary data','guard.semantic.unavailable')])
def test_mcp_result_withheld_and_never_completed(tmp_path,text,reason):
    class ResultBackend(DemoMCPBackend):
        async def call_tool(self,name,arguments):
            self.invocations[name]+=1
            return text
    app,session,store,backend=setup(tmp_path,backend=ResultBackend())
    async def proof(client):
        result=await client.call_tool('safe_lookup',{})
        assert result.is_error and text not in result.content[0].text
    asyncio.run(with_sdk(app,proof))
    events=store.events(session.session_id)
    assert [event.action for event in events]==['ALLOW','BLOCK','AUDIT']
    assert events[1].reason_code==reason and events[-1].reason_code=='mcp.result_blocked'


@pytest.mark.parametrize('action',['REDACT','ALLOW'])
def test_mcp_admission_audit_failure_prevents_backend(tmp_path,action):
    app,session,store,backend=setup(tmp_path,DemoSemanticFake())
    original=store.append
    def persist(event):
        if event.action==action:
            raise StoreFailure('private exception details')
        original(event)
    store.append=persist
    async def proof(client):
        with pytest.raises(MCPError):
            await client.call_tool('echo_contact',{'contact':'user@example.com'})
        assert backend.invocations['echo_contact']==0
    asyncio.run(with_sdk(app,proof))


@pytest.mark.parametrize('token',[None,'wrong','duplicate','expired'])
def test_mcp_transport_requires_session_identity(tmp_path,token):
    app,session,store,backend=setup(tmp_path,DemoSemanticFake())
    if token == 'expired':
        session = session.model_copy(update={'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)})
        app = create_app(session, load_policy(PROJECT_ROOT/'config/policy.yaml'), store,
                         semantic_provider=DemoSemanticFake(), backend=backend)
    async def proof():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),trust_env=False) as client:
                headers = [('X-AICtrl-Session', TOKEN), ('X-AICtrl-Session', TOKEN)] if token == 'duplicate' else {'X-AICtrl-Session': TOKEN if token == 'expired' else token} if token else {}
                response=await client.post('http://gateway:8000/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
                assert response.status_code==401
    asyncio.run(proof())
    assert not backend.invocations and store.events(session.session_id)[0].reason_code=='mcp.invalid_session'
