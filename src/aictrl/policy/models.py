"""Strict, exact-match admission rules. Configuration schema 2."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aictrl.contracts import AgentProtocol, Channel, Direction, Identifier, InspectionLevel


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class AdmissionRule(PolicyModel):
    id: Identifier
    channel: Channel = Field(strict=False)
    direction: Direction = Field(strict=False)
    protocol: AgentProtocol = Field(strict=False)
    target: Identifier
    operations: tuple[Identifier, ...] = Field(min_length=1, strict=False)
    action: Literal['ALLOW', 'BLOCK']
    inspection_level: InspectionLevel = Field(default=InspectionLevel.STRUCTURED, strict=False)


class AgentPolicy(PolicyModel):
    enabled: bool
    rules: tuple[AdmissionRule, ...] = Field(default=(), strict=False)


class Policy(PolicyModel):
    schema_version: Literal[2]
    policy_version: Identifier
    default_action: Literal['BLOCK']
    agents: dict[Identifier, AgentPolicy] = Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_rule_ids(self):
        identifiers = [rule.id for agent in self.agents.values() for rule in agent.rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('Policy rule IDs must be globally unique.')
        return self
