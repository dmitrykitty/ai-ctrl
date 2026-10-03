import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from aictrl.guards.engine import GuardEngine
from aictrl.guards.jev import JevSemanticProvider
from aictrl.guards.models import InspectionSegment, Source
from aictrl.guards.semantic import QUESTIONS
from aictrl.policy.models import GuardSettings

KEY = 'synthetic_jev_key_for_offline_test'


def body():
    return {'model':'jev-latest','answers':{name:{'type':'noul','noul':0.01} for name in QUESTIONS},
            'usage': {'input_tokens':12,'output_tokens':3}}


def run(*, response=None, status=200, exception=None, text='user@example.com', key=KEY):
    calls=[]
    async def upstream(request):
        calls.append(request)
        if exception:
            raise exception
        return httpx.Response(status, content=json.dumps(body() if response is None else response).encode())
    async def proof():
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream),trust_env=False) as client:
            provider=JevSemanticProvider(client,SecretStr(key) if key else None)
            engine=GuardEngine(GuardSettings(),provider)
            return await engine.inspect_input((InspectionSegment('fixture',text,Source.TOOL_RESULT,('output',),True,True),))
    return asyncio.run(proof()),calls


def test_one_fixed_origin_jev_post_has_all_questions_and_redacted_state(caplog):
    evaluated,calls=run()
    assert evaluated.action == 'REDACT' and len(calls) == 1
    request=calls[0]
    assert str(request.url) == 'https://api.typesafe.ai/v1/systemone'
    parsed=json.loads(request.content)
    assert set(parsed) == {'model','state','questions'} and set(parsed['questions']) == set(QUESTIONS)
    assert all(q['type']=='noul' for q in parsed['questions'].values())
    assert request.headers['authorization']=='Bearer '+KEY
    assert '[REDACTED_EMAIL_ADDRESS]' in request.content.decode()
    assert all(value not in request.content.decode()+caplog.text for value in (KEY,'user@example.com','X-AICtrl-Session','synthetic-provider'))
    assert 'x-aictrl-session' not in request.headers


@pytest.mark.parametrize('status', [401,403,429,500,503,307])
def test_jev_status_failure_never_retries(status):
    evaluated,calls=run(status=status)
    assert evaluated.reason_code == 'guard.semantic.unavailable' and len(calls)==1


@pytest.mark.parametrize('response', [[], {}, {'answers':{}},
    body() | {'answers':{'prompt_injection':{'type':'noul','noul':0.1}}},
    body() | {'answers':{name:{'type':'noul','noul':'0.1'} for name in QUESTIONS}},
    body() | {'answers':{name:{'type':'noul','noul':float('nan')} for name in QUESTIONS}},
    body() | {'answers':{name:{'type':'noul','noul':1.1} for name in QUESTIONS}},
    body() | {'answers':{name:{'type':'choice','noul':0.1} for name in QUESTIONS}},
    body() | {'usage':{'input_tokens':True,'output_tokens':0}},
    body() | {'unexpected':'reflected private content'}])
def test_strict_jev_response_validation(response):
    evaluated,calls=run(response=response)
    assert evaluated.reason_code=='guard.semantic.unavailable' and len(calls)==1


@pytest.mark.parametrize('exception', [httpx.ConnectError('private details'), httpx.ReadTimeout('private details')])
def test_jev_transport_errors_safe(exception,caplog):
    evaluated,calls=run(exception=exception)
    assert evaluated.reason_code=='guard.semantic.unavailable' and len(calls)==1
    assert 'private details' not in repr(evaluated)+caplog.text


def test_secret_or_missing_key_prevents_any_http_call():
    evaluated,calls=run(text='AICTRL_SECRET_demo')
    assert evaluated.reason_code=='guard.secret.detected' and not calls
    evaluated,calls=run(key=None)
    assert evaluated.reason_code=='guard.semantic.unavailable' and not calls
