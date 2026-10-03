"""Strict exact rules and bounded guards. Configuration schema 3."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    action: Literal['ALLOW', 'BLOCK']
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


class Policy(PolicyModel):
    schema_version: Literal[3]
    policy_version: Identifier
    default_action: Literal['BLOCK']
    agents: dict[Identifier, AgentPolicy] = Field(default_factory=dict)
    guards: GuardSettings = Field(default_factory=GuardSettings)

    @model_validator(mode='after')
    def unique_rule_ids(self):
        identifiers = [rule.id for agent in self.agents.values() for rule in agent.rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('Policy rule IDs must be globally unique.')
        return self
