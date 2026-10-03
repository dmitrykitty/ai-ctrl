"""Strict, intentionally small native LLM admission configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aictrl.contracts import Identifier


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class AgentPolicy(PolicyModel):
    enabled: bool


class LLMPolicy(PolicyModel):
    messages: Literal['ALLOW', 'BLOCK'] = 'BLOCK'
    count_tokens: Literal['ALLOW', 'BLOCK'] = 'BLOCK'


class Policy(PolicyModel):
    schema_version: Literal[1]
    policy_version: Identifier
    default_action: Literal['BLOCK']
    agents: dict[Identifier, AgentPolicy] = Field(default_factory=dict)
    llm: LLMPolicy = Field(default_factory=LLMPolicy)
