"""Versioned data contracts. Enforcement belongs to their consuming modules.

Audit-facing contracts deliberately omit arbitrary metadata, headers, prompts,
request bodies, credentials, and free-form finding excerpts.
"""

from enum import StrEnum
import re
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")]
Counter = Annotated[int, Field(ge=0)]


class DecisionAction(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDACT = "REDACT"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    AUDIT = "AUDIT"


class Channel(StrEnum):
    LLM = "LLM"
    MCP = "MCP"
    API = "API"
    EGRESS = "EGRESS"


class Direction(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class SessionState(StrEnum):
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


class AgentProtocol(StrEnum):
    CHAT_COMPLETIONS = "CHAT_COMPLETIONS"
    ANTHROPIC_MESSAGES = "ANTHROPIC_MESSAGES"
    RESPONSES = "RESPONSES"


class InspectionLevel(StrEnum):
    STRUCTURED = "STRUCTURED"
    HTTP_METADATA = "HTTP_METADATA"
    DESTINATION_ONLY = "DESTINATION_ONLY"


class BillingMode(StrEnum):
    LOCAL = "LOCAL"
    SUBSCRIPTION = "SUBSCRIPTION"
    METERED = "METERED"
    TEST_TARIFF = "TEST_TARIFF"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal[1] = 1


class AgentSession(Contract):
    session_id: UUID = Field(default_factory=uuid4)
    agent_id: Identifier
    adapter: Identifier
    user_id: Identifier
    profile_id: Identifier
    workspace: str
    protocol: AgentProtocol
    billing_mode: BillingMode
    state: SessionState = SessionState.STARTING
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    # Internal gateway identity, supplied by the future supervisor. Never audit it.
    session_token: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @field_validator("session_token")
    @classmethod
    def valid_session_token(cls, token: SecretStr | None) -> SecretStr | None:
        if token is not None and not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token.get_secret_value()):
            raise ValueError("internal session token must be an opaque, header-safe value")
        return token


class PolicyContext(Contract):
    session_id: UUID
    agent_id: Identifier
    user_id: Identifier
    profile_id: Identifier
    policy_version: Identifier


class ControlRequest(Contract):
    request_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    channel: Channel
    direction: Direction
    protocol: AgentProtocol | None = None
    inspection_level: InspectionLevel
    target_id: Identifier
    operation_id: Identifier
    # Reference to ephemeral request data; full payloads are not audit contracts.
    payload_ref: UUID | None = None
    created_at: AwareDatetime


class GuardResult(Contract):
    guard_id: Identifier
    action: DecisionAction
    reason_code: Identifier
    signature_ids: tuple[Identifier, ...] = ()
    severity: Severity | None = None
    latency_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0


class ControlDecision(Contract):
    decision_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    action: DecisionAction
    reason_code: Identifier
    policy_version: Identifier
    guards: tuple[GuardResult, ...] = ()
    approval_id: UUID | None = None


class UsageMetric(Contract):
    request_id: UUID
    session_id: UUID
    input_tokens: Counter = 0
    output_tokens: Counter = 0
    requests: Counter = 0
    tool_calls: Counter = 0
    agent_steps: Counter = 0
    billing_mode: BillingMode
    # Subscription monetary cost stays unknown; never infer a zero price.
    cost_microunits: Counter | None = None


class SecurityEvent(Contract):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    request_id: UUID | None = None
    agent_id: Identifier
    adapter: Identifier
    channel: Channel
    direction: Direction
    protocol: AgentProtocol | None = None
    inspection_level: InspectionLevel
    action: DecisionAction
    reason_code: Identifier
    policy_version: Identifier
    rule_ids: tuple[Identifier, ...] = ()
    usage: UsageMetric | None = None
    occurred_at: AwareDatetime


class BudgetState(Contract):
    budget_id: UUID = Field(default_factory=uuid4)
    scope: Literal["session", "agent", "user", "profile"]
    scope_id: str
    dimension: Literal["requests", "tokens", "tool_calls", "agent_steps", "wall_time_seconds"]
    limit: Counter
    used: Counter = 0
    reserved: Counter = 0
    window_start: AwareDatetime
    window_end: AwareDatetime

    @model_validator(mode="after")
    def valid_window(self) -> "BudgetState":
        if self.window_end <= self.window_start:
            raise ValueError("budget window must end after it starts")
        return self


class RiskState(Contract):
    session_id: UUID
    score: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0
    # Contributions are stable rule IDs and counts, never matching raw content.
    contributions: dict[Identifier, Counter] = Field(default_factory=dict)
    updated_at: AwareDatetime


class Alert(Contract):
    alert_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    event_ids: tuple[UUID, ...] = ()
    rule_id: Identifier
    severity: Severity
    response: Literal["notify", "restrict", "terminate"]
    response_completed_at: AwareDatetime | None = None
    created_at: AwareDatetime


class ThreatSignature(Contract):
    signature_id: Identifier
    revision: Counter
    kind: Literal["literal", "regex", "semantic"]
    pattern: Annotated[str, Field(min_length=1, max_length=4096)]
    action: DecisionAction
    severity: Severity
    channels: tuple[Channel, ...]
    enabled: bool = True


class Approval(Contract):
    approval_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    request_id: UUID
    request_digest: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    policy_version: Identifier
    state: ApprovalState = ApprovalState.PENDING
    requested_at: AwareDatetime
    expires_at: AwareDatetime
    consumed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_expiry(self) -> "Approval":
        if self.expires_at <= self.requested_at:
            raise ValueError("approval expiry must follow its request")
        return self
