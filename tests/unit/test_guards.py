import asyncio
from dataclasses import replace

import pytest
from pydantic import ValidationError

from aictrl.contracts import DecisionAction
from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import InspectionSegment, Source, aggregate
from aictrl.guards.semantic import QUESTIONS
from aictrl.policy.models import GuardSettings, SemanticSettings, SemanticThresholds
from guard_fakes import FakeSemanticProvider


def segment(text, *, untrusted=True, mutable=True):
    return InspectionSegment('fixture', text, Source.TOOL_RESULT if untrusted else Source.USER_INPUT,
                             ('content',), mutable, untrusted)


def inspect(text, *, output=False, provider=None, untrusted=True, settings=None):
    engine = GuardEngine(settings or GuardSettings(), provider)
    if output:
        return asyncio.run(engine.inspect_output((segment(text, untrusted=untrusted),), semantic=True))
    return asyncio.run(engine.inspect_input((segment(text, untrusted=untrusted),)))


@pytest.mark.parametrize('secret,signature', [
    ('AICTRL_SECRET_demo123', 'secret.synthetic'),
    ('-----BEGIN PRIVATE KEY-----', 'secret.pem_private_key'),
    ('-----BEGIN OPENSSH PRIVATE KEY-----', 'secret.pem_private_key'),
    ('AKIA' + 'A' * 16, 'secret.aws_access_key'),
    ('sk-proj-' + 'a' * 40, 'secret.openai_api_key'),
    ('sk-ant-api03-' + 'a' * 40, 'secret.anthropic_api_key'),
    ('ghp_' + 'a' * 36, 'secret.github_token'),
    ('github_pat_' + 'a' * 30, 'secret.github_token'),
    ('Bearer ' + 'a' * 32, 'secret.bearer'),
])
@pytest.mark.parametrize('output', [False, True])
def test_secret_blocks_before_any_semantic_call(secret, signature, output, caplog):
    fake = FakeSemanticProvider()
    evaluated = inspect(secret, output=output, provider=fake)
    assert evaluated.action == 'BLOCK' and not fake.calls
    assert signature in evaluated.identifiers
    assert secret not in repr(evaluated) + caplog.text
    assert all(secret not in result.model_dump_json() for result in evaluated.results)


@pytest.mark.parametrize('text,entity', [('user@example.com','EMAIL_ADDRESS'),
                                       ('+1 212-555-1234','PHONE_NUMBER'),
                                       ('4111 1111 1111 1111','CREDIT_CARD')])
def test_pii_redacted_before_semantic_and_output_blocked(text, entity):
    fake = FakeSemanticProvider()
    evaluated = inspect(text, provider=fake)
    marker = '[REDACTED_' + entity + ']'
    assert evaluated.action == 'REDACT' and evaluated.replacements[0].text == marker
    assert len(fake.calls) == 1 and fake.calls[0][0].text == marker
    assert text not in repr(evaluated)
    fake.calls.clear()
    blocked = inspect(text, output=True, provider=fake)
    assert blocked.action == 'BLOCK' and not fake.calls


def test_no_semantic_for_direct_intent_or_ordinary_numeric_id():
    fake = FakeSemanticProvider()
    evaluated = inspect('Delete this file. Build 12345678. Card-like invalid 4111111111111112.', provider=fake, untrusted=False)
    assert evaluated.action == 'ALLOW' and not fake.calls
    assert inspect('ordinary data', provider=fake).action == 'ALLOW' and len(fake.calls) == 1


@pytest.mark.parametrize('question', QUESTIONS)
@pytest.mark.parametrize('score,action', [(0.849,'ALLOW'), (0.85,'BLOCK'), (0.99,'BLOCK')])
def test_semantic_thresholds_exact_boundary(question, score, action):
    scores = dict.fromkeys(QUESTIONS, 0.01) | {question: score}
    evaluated = inspect('Untrusted fixture', provider=FakeSemanticProvider(scores))
    assert evaluated.action == action
    if action == 'BLOCK':
        assert evaluated.reason_code == 'guard.semantic.' + question


@pytest.mark.parametrize('scores', [{'prompt_injection':0.1}, dict.fromkeys(QUESTIONS, '0.1'),
                                   dict.fromkeys(QUESTIONS, float('nan')), dict.fromkeys(QUESTIONS, 1.1),
                                   dict.fromkeys(QUESTIONS, True)])
def test_invalid_semantic_provider_is_fail_closed(scores):
    assert inspect('ordinary external data', provider=FakeSemanticProvider(scores)).reason_code == 'guard.semantic.unavailable'


@pytest.mark.parametrize('provider', [None, FakeSemanticProvider(error=TimeoutError()), FakeSemanticProvider(error=ConnectionError())])
def test_missing_or_failed_semantic_provider_is_fail_closed(provider):
    assert inspect('external data', provider=provider).action == 'BLOCK'


def test_semantic_bound_never_truncates_or_calls_provider():
    fake = FakeSemanticProvider()
    assert inspect('x' * 32769, provider=fake).reason_code == 'guard.semantic.input_too_large'
    assert not fake.calls


def test_redactions_reverse_offsets_and_immutable_content_fails_closed():
    fake = FakeSemanticProvider()
    evaluated = inspect('first@example.com and second@example.com', provider=fake)
    assert evaluated.replacements[0].text == '[REDACTED_EMAIL_ADDRESS] and [REDACTED_EMAIL_ADDRESS]'
    engine = GuardEngine(GuardSettings(), fake)
    evaluated = asyncio.run(engine.inspect_input((segment('user@example.com', mutable=False),)))
    assert evaluated.action == 'BLOCK'


def test_aggregation_has_explicit_precedence():
    assert aggregate([DecisionAction.ALLOW, DecisionAction.REDACT]) == 'REDACT'
    assert aggregate([DecisionAction.REQUIRE_APPROVAL, DecisionAction.REDACT]) == 'REQUIRE_APPROVAL'
    assert aggregate([DecisionAction.BLOCK, DecisionAction.REQUIRE_APPROVAL]) == 'BLOCK'


@pytest.mark.parametrize('bad', [
    {'semantic': {'provider':'unknown'}}, {'semantic': {'timeout_ms':0}},
    {'semantic': {'max_chars':0}}, {'semantic': {'on_error':'ALLOW'}},
    {'semantic': {'thresholds': {'prompt_injection':1.1}}},
    {'semantic': {'api_key':'synthetic key'}}, {'pii': {'entities':['PERSON']}},
    {'pii': {'input_action':'ALLOW'}}, {'secrets': {'output_action':'REDACT'}},
    {'secrets': {'enabled':False}}, {'pii': {'entities':['EMAIL_ADDRESS']}},
])
def test_strict_guard_configuration_and_external_privacy_order(bad):
    with pytest.raises(ValidationError):
        GuardSettings.model_validate(bad)
