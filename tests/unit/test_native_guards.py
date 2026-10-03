import asyncio
import json

import pytest

from aictrl.gateway.anthropic import AnthropicMessagesHandler
from aictrl.gateway.responses import ResponsesHandler
from aictrl.reporting.sink import StoreFailure
from test_gateway import fixture, invoke
from guard_fakes import FakeSemanticProvider


@pytest.mark.parametrize('handler,payload,source', [
    (AnthropicMessagesHandler(), {'system':[{'type':'text','text':'system fixture'}], 'messages':[{'role':'user','content':[{'type':'tool_result','tool_use_id':'test','content':[{'type':'text','text':'external data'}]}]}]}, 'tool_result'),
    (ResponsesHandler(), {'instructions':'system fixture', 'input':[{'type':'function_call_output','call_id':'call_1','output':'external data'}]}, 'tool_result'),
])
def test_actual_native_provenance_shapes(handler,payload,source):
    segments=handler.extract_inspection(payload)
    assert any(segment.source==source and segment.untrusted_external for segment in segments)
    assert any(segment.source=='system_instruction' and not segment.untrusted_external for segment in segments)


def test_input_secret_blocks_upstream_and_semantic_without_raw_persistence(tmp_path,caplog):
    app,store,session,calls,client=fixture(tmp_path)
    body=json.dumps({'messages':[{'role':'user','content':'AICTRL_SECRET_demo'}]}).encode()
    response=asyncio.run(invoke(app,client,body=body))
    assert response.status_code==403 and not calls
    events=store.events(session.session_id)
    assert len(events)==1 and events[0].reason_code=='guard.secret.detected'
    assert b'AICTRL_SECRET_demo' not in store.path.read_bytes()
    assert 'AICTRL_SECRET_demo' not in caplog.text+response.text


@pytest.mark.parametrize('failure',[None,'REDACT','ALLOW'])
def test_input_redaction_durable_before_modified_upstream(tmp_path,monkeypatch,failure):
    app,store,session,calls,client=fixture(tmp_path)
    original=store.append
    def persist(event):
        if event.action==failure:
            raise StoreFailure('private fixture details')
        original(event)
    monkeypatch.setattr(store,'append',persist)
    body=b'{ "messages" : [{"role":"user", "content":"user@example.com"}], "future":true }'
    response=asyncio.run(invoke(app,client,body=body))
    if failure:
        assert response.status_code==503 and not calls
    else:
        assert response.status_code==200 and len(calls)==1
        rewritten=json.loads(calls[0].content)
        assert rewritten['messages'][0]['content']=='[REDACTED_EMAIL_ADDRESS]' and rewritten['future'] is True
        assert [event.action for event in store.events(session.session_id)]==['REDACT','ALLOW','AUDIT']
    assert b'user@example.com' not in store.path.read_bytes()


def test_untrusted_native_followup_without_key_is_fail_closed(tmp_path):
    app,store,session,calls,client=fixture(tmp_path)
    body=json.dumps({'messages':[{'role':'user','content':[{'type':'tool_result','content':'ordinary external data'}]}]}).encode()
    response=asyncio.run(invoke(app,client,body=body))
    assert response.status_code==403 and not calls
    assert store.events(session.session_id)[-1].reason_code=='guard.semantic.unavailable'


@pytest.mark.parametrize('failure', [None, 'REDACT', 'ALLOW'])
def test_responses_tool_result_redacted_before_semantic_and_durable_admission(tmp_path, monkeypatch, failure):
    from test_responses import fixture as responses_fixture, invoke as responses_invoke
    app, session, store, calls, _ = responses_fixture(tmp_path)
    original = store.append
    def persist(event):
        if event.action == failure:
            raise StoreFailure('private fixture details')
        original(event)
    monkeypatch.setattr(store, 'append', persist)
    body = b'{ "input": [{"type":"function_call_output","call_id":"call_1","output":"user@example.com"}], "future":true }'
    response = asyncio.run(responses_invoke(app, body=body))
    inspected = app.state.gateway.guards.semantic.calls
    assert len(inspected) == 1 and inspected[0][0].text == '[REDACTED_EMAIL_ADDRESS]'
    if failure:
        assert response.status_code == 503 and not calls
    else:
        assert response.status_code == 200 and len(calls) == 1
        rewritten = json.loads(calls[0].content)
        assert rewritten['input'][0]['output'] == '[REDACTED_EMAIL_ADDRESS]'
        assert rewritten['input'][0]['call_id'] == 'call_1' and rewritten['future'] is True
        assert [event.action for event in store.events(session.session_id)] == ['REDACT', 'ALLOW', 'AUDIT']
    assert b'user@example.com' not in store.path.read_bytes()
