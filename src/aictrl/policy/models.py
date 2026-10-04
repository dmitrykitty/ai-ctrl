"""Strict configuration only. Enforcement belongs to control/governance."""

from typing import Literal
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from aictrl.contracts import AgentProtocol, Channel, Direction, Identifier, InspectionLevel


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class AdmissionRule(PolicyModel):
    id: Identifier
    channel: Channel = Field(strict=False)
    direction: Direction = Field(strict=False)
    protocol: AgentProtocol | None = Field(strict=False)
    target: Identifier
    operations: tuple[Identifier, ...] = Field(min_length=1, strict=False)
    action: Literal['ALLOW', 'BLOCK', 'REQUIRE_APPROVAL']
    inspection_level: InspectionLevel = Field(default=InspectionLevel.STRUCTURED, strict=False)


class AgentPolicy(PolicyModel):
    enabled: bool
    rules: tuple[AdmissionRule, ...] = Field(default=(), strict=False)


class SecretSettings(PolicyModel):
    enabled: bool = True
    input_action: Literal['BLOCK'] = 'BLOCK'
    output_action: Literal['BLOCK'] = 'BLOCK'


class PiiSettings(PolicyModel):
    enabled: bool = True
    input_action: Literal['REDACT'] = 'REDACT'
    output_action: Literal['BLOCK'] = 'BLOCK'
    entities: tuple[Literal['EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD'], ...] = Field(
        default=('EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD'), min_length=1, strict=False)


class SemanticThresholds(PolicyModel):
    prompt_injection: float = Field(default=0.85, ge=0, le=1, allow_inf_nan=False)
    data_exfiltration: float = Field(default=0.85, ge=0, le=1, allow_inf_nan=False)
    security_bypass: float = Field(default=0.85, ge=0, le=1, allow_inf_nan=False)


class SemanticSettings(PolicyModel):
    enabled: bool = True
    provider: Literal['jev'] = 'jev'
    model: Literal['jev-latest'] = 'jev-latest'
    on_error: Literal['BLOCK'] = 'BLOCK'
    timeout_ms: int = Field(default=2500, ge=100, le=10000)
    max_chars: int = Field(default=32768, ge=1024, le=131072)
    thresholds: SemanticThresholds = Field(default_factory=SemanticThresholds)


class OutputSettings(PolicyModel):
    max_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    timeout_ms: int = Field(default=30000, ge=100, le=120000)


class GuardSettings(PolicyModel):
    secrets: SecretSettings = Field(default_factory=SecretSettings)
    pii: PiiSettings = Field(default_factory=PiiSettings)
    semantic: SemanticSettings = Field(default_factory=SemanticSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)

    @model_validator(mode='after')
    def external_privacy(self):
        if self.semantic.enabled and (not self.secrets.enabled or not self.pii.enabled
                                     or set(self.pii.entities) != {'EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD'}):
            raise ValueError('External semantic inspection requires all deterministic privacy guards.')
        return self


class BudgetRule(PolicyModel):
    id: Identifier
    scope: Literal['session', 'agent', 'user', 'profile']
    dimension: Literal['requests', 'tokens', 'tool_calls', 'agent_steps']
    limit: int = Field(gt=0, le=1_000_000_000)
    window_seconds: int = Field(ge=1, le=86400)


class RunawaySettings(PolicyModel):
    max_agent_steps: int = Field(default=60, ge=1, le=100000)
    max_tool_calls: int = Field(default=40, ge=1, le=100000)


class GovernanceSettings(PolicyModel):
    approval_ttl_seconds: int = Field(default=60, ge=1, le=3600)
    token_reservation: int = Field(default=8192, ge=1, le=10_000_000)
    input_token_allowance: int = Field(default=4096, ge=1, le=10_000_000)
    budgets: tuple[BudgetRule, ...] = Field(default=(), max_length=128, strict=False)
    runaway: RunawaySettings = Field(default_factory=RunawaySettings)

    @model_validator(mode='after')
    def unique_ids(self):
        ids = [rule.id for rule in self.budgets]
        if len(ids) != len(set(ids)) or any(id.startswith('runaway.') for id in ids):
            raise ValueError('Budget IDs must be unique; runaway namespace is reserved.')
        return self


class RiskThresholds(PolicyModel):
    medium: int = Field(default=25, ge=1, le=1000000)
    high: int = Field(default=100, ge=1, le=1000000)
    critical: int = Field(default=160, ge=1, le=1000000)

    @model_validator(mode='after')
    def increasing(self):
        if not self.medium < self.high < self.critical:
            raise ValueError('Risk thresholds must increase.')
        return self


class RiskSettings(PolicyModel):
    window_seconds: int = Field(default=300, ge=1, le=86400)
    weights: dict[Identifier, int] = Field(default_factory=lambda: {
        'guard.secret.detected': 40, 'guard.semantic.prompt_injection': 35,
        'guard.semantic.data_exfiltration': 50, 'guard.semantic.security_bypass': 50,
        'guard.threat_feed.detected': 35, 'mcp.policy.blocked': 20,
        'operation.resource.private.read': 25, 'governance.budget': 15,
        'governance.runaway': 20, 'llm.invalid_session': 25, 'mcp.invalid_session': 25,
    }, max_length=128)
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)

    @model_validator(mode='after')
    def safe_weights(self):
        if any(type(value) is not int or not 0 <= value <= 1000 for value in self.weights.values()):
            raise ValueError('Risk weights must be bounded nonnegative integers.')
        object.__setattr__(self, 'weights', MappingProxyType(dict(self.weights)))
        return self

    @field_serializer('weights')
    def serialize_weights(self, weights):
        return dict(weights)


class ResponseSettings(PolicyModel):
    medium: Literal['notify', 'restrict', 'terminate'] = 'notify'
    high: Literal['notify', 'restrict', 'terminate'] = 'restrict'
    critical: Literal['notify', 'restrict', 'terminate'] = 'terminate'
    alert_cooldown_seconds: int = Field(default=60, ge=1, le=3600)


class Policy(PolicyModel):
    schema_version: Literal[5]
    policy_version: Identifier
    default_action: Literal['BLOCK']
    agents: dict[Identifier, AgentPolicy] = Field(default_factory=dict)
    guards: GuardSettings = Field(default_factory=GuardSettings)
    governance: GovernanceSettings = Field(default_factory=GovernanceSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    response: ResponseSettings = Field(default_factory=ResponseSettings)

    @model_validator(mode='after')
    def unique_rule_ids(self):
        identifiers = [rule.id for agent in self.agents.values() for rule in agent.rules]
        identifiers += [rule.id for rule in self.governance.budgets]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('Policy rule IDs must be globally unique.')
        object.__setattr__(self, 'agents', MappingProxyType(dict(self.agents)))
        return self

    @field_serializer('agents')
    def serialize_agents(self, agents):
        return dict(agents)
