from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from aictrl.contracts import (
    AgentSession, Alert, Approval, BillingMode, BudgetState, Channel,
    ControlDecision, ControlRequest, DecisionAction, Direction, GuardResult,
    InspectionLevel, PolicyContext, RiskState, SecurityEvent, Severity,
    ThreatSignature, UsageMetric,
)

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
SESSION = uuid4()
REQUEST = uuid4()


@pytest.mark.parametrize("contract", [
    AgentSession(agent_id="claude", adapter="claude", user_id="local", profile_id="default",
                 workspace="/workspace", protocol="ANTHROPIC_MESSAGES",
                 billing_mode="SUBSCRIPTION", started_at=NOW),
    PolicyContext(session_id=SESSION, agent_id="claude", user_id="local", profile_id="default", policy_version="v1"),
    ControlRequest(request_id=REQUEST, session_id=SESSION, channel="LLM", direction="OUTBOUND",
                   inspection_level="STRUCTURED", target_id="anthropic", operation_id="messages", created_at=NOW),
    GuardResult(guard_id="secrets", action="BLOCK", reason_code="secret_detected"),
    ControlDecision(request_id=REQUEST, action="BLOCK", reason_code="default_deny", policy_version="v1"),
    SecurityEvent(session_id=SESSION, agent_id="claude", adapter="claude", channel="LLM", direction="OUTBOUND",
                  inspection_level="STRUCTURED", action="BLOCK", reason_code="default_deny", policy_version="v1", occurred_at=NOW),
    BudgetState(scope="session", scope_id=str(SESSION), dimension="tokens", limit=100,
                window_start=NOW, window_end=NOW + timedelta(minutes=1)),
    UsageMetric(request_id=REQUEST, session_id=SESSION, billing_mode="SUBSCRIPTION"),
    RiskState(session_id=SESSION, updated_at=NOW),
    Alert(session_id=SESSION, rule_id="high_risk", severity="HIGH", response="restrict", created_at=NOW),
    ThreatSignature(signature_id="test_secret", revision=1, kind="literal", pattern="synthetic-secret",
                    action="BLOCK", severity="HIGH", channels=(Channel.LLM,)),
    Approval(session_id=SESSION, request_id=REQUEST, request_digest="a" * 64, policy_version="v1",
             requested_at=NOW, expires_at=NOW + timedelta(minutes=1)),
])
def test_contract_json_round_trip_and_unknown_version_rejected(contract):
    wire = contract.model_dump_json()
    assert type(contract).model_validate_json(wire).model_dump() == contract.model_dump()
    with pytest.raises(ValidationError):
        type(contract).model_validate({**contract.model_dump(), "schema_version": 2})


def test_event_rejects_raw_credentials_and_payloads():
    data = dict(session_id=SESSION, agent_id="claude", adapter="claude", channel=Channel.EGRESS,
                direction=Direction.OUTBOUND, inspection_level=InspectionLevel.DESTINATION_ONLY,
                action=DecisionAction.BLOCK, reason_code="default_deny", policy_version="v1", occurred_at=NOW)
    for field in ("credentials", "headers", "prompt", "body", "metadata"):
        with pytest.raises(ValidationError):
            SecurityEvent(**data, **{field: "synthetic-sensitive-content"})


def test_internal_session_token_never_serializes_or_prints():
    token = "synthetic_internal_token_1234567890"
    session = AgentSession(agent_id="claude", adapter="claude", user_id="local", profile_id="default",
                           workspace="/workspace", protocol="ANTHROPIC_MESSAGES", billing_mode="SUBSCRIPTION",
                           started_at=NOW, session_token=SecretStr(token))
    assert token not in session.model_dump_json()
    assert "session_token" not in session.model_dump()
    assert token not in repr(session)
    with pytest.raises(ValidationError):
        AgentSession(**session.model_dump(), session_token=SecretStr(token + "\r\nInjected: yes"))


def test_counter_time_and_float_validation():
    with pytest.raises(ValidationError):
        UsageMetric(request_id=REQUEST, session_id=SESSION, billing_mode=BillingMode.SUBSCRIPTION, input_tokens=-1)
    with pytest.raises(ValidationError):
        RiskState(session_id=SESSION, score=float("nan"), updated_at=NOW)
    with pytest.raises(ValidationError):
        RiskState(session_id=SESSION, updated_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        BudgetState(scope="session", scope_id=str(SESSION), dimension="tokens", limit=100,
                    window_start=NOW, window_end=NOW)
    with pytest.raises(ValidationError):
        Approval(session_id=SESSION, request_id=REQUEST, request_digest="a" * 64, policy_version="v1",
                 requested_at=NOW, expires_at=NOW - timedelta(seconds=1))


def test_subscription_cost_remains_unknown():
    assert UsageMetric(request_id=REQUEST, session_id=SESSION, billing_mode="SUBSCRIPTION").cost_microunits is None
