import pytest
from pydantic import ValidationError

from aictrl.contracts import ControlRequest, PolicyContext
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.loader import load_policy
from aictrl.policy.models import Policy
from aictrl.runtime.workspace import PROJECT_ROOT
from datetime import datetime, timezone
from uuid import uuid4


@pytest.mark.parametrize('bad', [
    {'unknown': True}, {'default_action': 'ALLOW'}, {'llm': {'messages': 'REDACT'}},
    {'agents': {'claude': {'enabled': 'true'}}}, {'llm': {'messages': 'ALLOW', 'model': 'anything'}},
])
def test_strict_policy_rejects_unsafe_or_unknown_configuration(bad):
    with pytest.raises(ValidationError):
        Policy.model_validate({'schema_version': 1, 'policy_version': 't03', 'default_action': 'BLOCK'} | bad)


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
    default = Policy(schema_version=1, policy_version='empty', default_action='BLOCK')
    assert PolicyEngine(default).decide(context, request).action == 'BLOCK'


def test_invalid_loader_does_not_echo_candidate_content(tmp_path):
    candidate = tmp_path / 'policy.yaml'
    candidate.write_text('unknown: synthetic-secret\n')
    with pytest.raises(ValueError) as error:
        load_policy(candidate)
    assert 'synthetic-secret' not in str(error.value)
