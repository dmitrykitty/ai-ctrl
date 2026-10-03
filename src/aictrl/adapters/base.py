from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field

from aictrl.contracts import AgentProtocol, AgentSession, BillingMode, Contract


class EndpointPurpose(StrEnum):
    INFERENCE = "INFERENCE"
    AUTHENTICATION = "AUTHENTICATION"
    AUXILIARY = "AUXILIARY"


class RoutingMode(StrEnum):
    EGRESS_ONLY = "EGRESS_ONLY"
    APPLICATION_GATEWAY = "APPLICATION_GATEWAY"


class ProviderEndpoint(Contract):
    host: str
    port: int = Field(default=443, ge=1, le=65535)
    purpose: EndpointPurpose


class AgentConfig(Contract):
    adapter: str
    image_ref: str
    entry_command: tuple[str, ...]
    persistent_state_volume: str | None = None
    state_mount: str | None = None
    stateless: bool = False
    # Internal identity can appear here. Exclude all environment from exports/repr.
    environment: dict[str, str] = Field(default_factory=dict, exclude=True, repr=False)
    required_provider_endpoints: tuple[ProviderEndpoint, ...] = ()


@runtime_checkable
class AgentAdapter(Protocol):
    name: str
    protocol: AgentProtocol
    billing_mode: BillingMode
    image_ref: str
    entry_command: tuple[str, ...]
    persistent_state_volume: str | None
    state_mount: str | None
    environment: dict[str, str]
    required_provider_endpoints: tuple[ProviderEndpoint, ...]

    def render_config(self, session: AgentSession) -> AgentConfig: ...

    def smoke_command(self) -> tuple[str, ...]: ...

    def prompt_command(self) -> tuple[str, ...]: ...
