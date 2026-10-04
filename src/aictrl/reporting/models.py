"""Strict safe reporting projections, separate from serialized contracts."""

from typing import Literal
from pydantic import AwareDatetime, Field
from aictrl.contracts import Identifier
from aictrl.policy.models import PolicyModel, RiskSettings, SemanticThresholds

ReloadStatus = Literal['loaded', 'static', 'applied', 'invalid_candidate']


class SemanticStatus(PolicyModel):
    provider: Literal['Jev']
    status: Literal['configured', 'unavailable', 'explicit-offline-fixture']
    enabled: bool
    thresholds: SemanticThresholds
    timeout_ms: int = Field(ge=100, le=10000)
    max_chars: int = Field(ge=1024, le=131072)


class GuardStatus(PolicyModel):
    secrets: bool
    pii: tuple[Literal['EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD'], ...] = Field(strict=False)
    output_max_bytes: int = Field(ge=1024, le=4194304)
    output_timeout_ms: int = Field(ge=100, le=120000)


class GovernanceStatus(PolicyModel):
    approval_ttl_seconds: int = Field(ge=1, le=3600)
    max_agent_steps: int = Field(ge=1, le=100000)
    max_tool_calls: int = Field(ge=1, le=100000)


class ControlStatus(PolicyModel):
    active_policy_version: Identifier
    active_feed_version: Identifier
    last_policy_reload_status: ReloadStatus
    last_feed_reload_status: ReloadStatus
    last_policy_reload_at: AwareDatetime
    last_feed_reload_at: AwareDatetime
    policy_schema: Literal[5]
    enabled_signatures: int = Field(ge=0, le=128)
    signature_ids: tuple[Identifier, ...] = Field(max_length=128, strict=False)
    semantic: SemanticStatus
    guards: GuardStatus
    governance: GovernanceStatus
    risk: RiskSettings
