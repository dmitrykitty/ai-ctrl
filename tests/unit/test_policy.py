import pytest
from pydantic import ValidationError

from aictrl.contracts import ControlRequest, PolicyContext
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.loader import load_policy
from aictrl.policy.models import AdmissionRule, AgentPolicy, Policy
from aictrl.runtime.workspace import PROJECT_ROOT
from datetime import datetime, timezone
from uuid import uuid4


@pytest.mark.parametrize('bad', [
    {'unknown': True}, {'default_action': 'ALLOW'}, {'llm': {'messages': 'REDACT'}},
    {'agents': {'claude': {'enabled': 'true'}}}, {'llm': {'messages': 'ALLOW', 'model': 'anything'}},
])
def test_strict_policy_rejects_unsafe_or_unknown_configuration(bad):
    with pytest.raises(ValidationError):
        Policy.model_validate({'schema_version': 3, 'policy_version': 't03', 'default_action': 'BLOCK'} | bad)


def test_policy_only_allows_explicit_enabled_native_operations():
    policy = load_policy(PROJECT_ROOT / 'config/policy.yaml')
    sid = uuid4()
    context = PolicyContext(session_id=sid, agent_id='claude', user_id='local', profile_id='local', policy_version=policy.policy_version)
    request = ControlRequest(session_id=sid, channel='LLM', direction='OUTBOUND', protocol='ANTHROPIC_MESSAGES',
                             inspection_level='STRUCTURED', target_id='anthropic', operation_id='messages', created_at=datetime.now(timezone.utc))
    engine = PolicyEngine(policy)
    assert engine.decide(context, request).action == 'ALLOW'
    for change in ({'operation_id': 'unsupported'}, {'target_id': 'other'}, {'channel': 'MCP'}, {'direction': 'INBOUND'}, {'session_id': uuid4()}, {'protocol': 'RESPONSES'}, {'inspection_level': 'DESTINATION_ONLY'}):
        assert engine.decide(context, request.model_copy(update=change)).action == 'BLOCK'
    assert engine.decide(context.model_copy(update={'agent_id': 'unknown'}), request).action == 'BLOCK'
    default = Policy(schema_version=3, policy_version='empty', default_action='BLOCK')
    assert PolicyEngine(default).decide(context, request).action == 'BLOCK'


def test_invalid_loader_does_not_echo_candidate_content(tmp_path):
    candidate = tmp_path / 'policy.yaml'
    candidate.write_text('unknown: synthetic-secret\n')
    with pytest.raises(ValueError) as error:
        load_policy(candidate)
    assert 'synthetic-secret' not in str(error.value)


def native_rule(**changes):
    return AdmissionRule.model_validate(dict(id='synthetic.rule', channel='LLM', direction='OUTBOUND',
                         protocol='RESPONSES', target='synthetic-target', operations=['responses'], action='ALLOW') | changes)


@pytest.mark.parametrize('changes', [
    {'id': '*'}, {'target': '*.provider'}, {'operations': []}, {'operations': ['*']},
    {'operations': [1]}, {'channel': 'HTTP'}, {'direction': 'BOTH'}, {'protocol': 'ANY'},
    {'action': 'REDACT'}, {'inspection_level': 'MAGIC'}, {'unknown': 'forbidden'},
])
def test_rules_reject_ambiguous_or_invalid_configuration(changes):
    with pytest.raises(ValidationError):
        native_rule(**changes)


@pytest.mark.parametrize('reversed_order', [False, True])
def test_exact_block_wins_independently_of_rule_order(reversed_order):
    allow, block = native_rule(id='allow'), native_rule(id='block', action='BLOCK')
    rules = (block, allow) if reversed_order else (allow, block)
    policy = Policy(schema_version=3, policy_version='generic', default_action='BLOCK',
                    agents={'synthetic-third': AgentPolicy(enabled=True, rules=rules)})
    sid = uuid4()
    context = PolicyContext(session_id=sid, agent_id='synthetic-third', user_id='local', profile_id='local', policy_version='generic')
    request = ControlRequest(session_id=sid, channel='LLM', direction='OUTBOUND', protocol='RESPONSES',
                             inspection_level='STRUCTURED', target_id='synthetic-target', operation_id='responses',
                             created_at=datetime.now(timezone.utc))
    assert PolicyEngine(policy).decide(context, request).action == 'BLOCK'
    unrelated = block.model_copy(update={'target': 'other'})
    enabled = policy.model_copy(update={'agents': {'synthetic-third': AgentPolicy(enabled=True, rules=(unrelated, allow))}})
    assert PolicyEngine(enabled).decide(context, request).action == 'ALLOW'
    assert PolicyEngine(enabled).decide(context.model_copy(update={'policy_version': 'stale'}), request).action == 'BLOCK'
    disabled = enabled.model_copy(update={'agents': {'synthetic-third': AgentPolicy(enabled=False, rules=(allow,))}})
    assert PolicyEngine(disabled).decide(context, request).action == 'BLOCK'


def test_duplicate_ids_across_agents_are_rejected():
    rule = native_rule()
    with pytest.raises(ValidationError, match='globally unique'):
        Policy(schema_version=3, policy_version='generic', default_action='BLOCK',
               agents={'first': AgentPolicy(enabled=True, rules=(rule,)), 'second': AgentPolicy(enabled=True, rules=(rule,))})


def test_schema_one_has_explicit_safe_migration_error(tmp_path):
    candidate = tmp_path / 'policy.yaml'
    candidate.write_text('schema_version: 1\nprivate: synthetic-secret\n')
    with pytest.raises(ValueError, match='schema 1 is unsupported; configuration schema 3 is required') as error:
        load_policy(candidate)
    assert 'synthetic-secret' not in str(error.value)
