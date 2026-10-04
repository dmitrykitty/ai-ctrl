import ipaddress
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from aictrl.adapters.base import RoutingMode


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaudeRuntime(StrictConfig):
    image: str = Field(min_length=1)
    state_volume: Literal["aictrl-claude-state"]
    state_mount: Literal["/home/dev/.claude"]
    auth_mode: Literal["subscription"]


class CodexRuntime(StrictConfig):
    image: str = Field(min_length=1)
    state_volume: Literal['aictrl-codex-state']
    state_mount: Literal['/home/dev/.codex']
    auth_mode: Literal['subscription']


class DemoRuntime(StrictConfig):
    image: str = Field(min_length=1)


class RuntimeLimits(StrictConfig):
    cpus: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(gt=0)
    pids: int = Field(gt=0)
    wall_time_seconds: int = Field(gt=0)


class TestDestination(StrictConfig):
    host: str
    port: int = Field(ge=1, le=65535)
    connect_ip: ipaddress.IPv4Address | None = None

    @field_validator("host")
    @classmethod
    def exact_host(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", value) or ".." in value:
            raise ValueError("destination must be an exact lowercase host, without URLs or wildcards")
        return value

    @field_validator("connect_ip")
    @classmethod
    def safe_test_ip(cls, value: ipaddress.IPv4Address | None) -> ipaddress.IPv4Address | None:
        if value and (value.is_loopback or value.is_link_local or value.is_unspecified or value.is_multicast):
            raise ValueError("unsafe test destination address")
        return value


class RuntimeEgress(StrictConfig):
    proxy_image: str = "aictrl-proxy:mitm-t02"
    routing_mode: RoutingMode = RoutingMode.EGRESS_ONLY
    # Trusted host configuration, never a caller-supplied upstream URL.
    test_destinations: tuple[TestDestination, ...] = ()


class GatewayRuntime(StrictConfig):
    image: str = 'aictrl-gateway:t03'
    audit_directory: Literal['.aictrl/audit'] = '.aictrl/audit'


class ProjectConfig(StrictConfig):
    schema_version: Literal[1]
    milestone: Literal["T01", "T02", "T03", "T04", "T05", "T06", "T07"]
    claude: ClaudeRuntime
    codex: CodexRuntime | None = None
    demo: DemoRuntime | None = None
    limits: RuntimeLimits
    runtime: RuntimeEgress = Field(default_factory=RuntimeEgress)
    gateway: GatewayRuntime = Field(default_factory=GatewayRuntime)


def load_config(project: Path) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate(yaml.safe_load((project / "config/project.yaml").read_text()))
    except (OSError, yaml.YAMLError, ValidationError):
        raise ValueError('config/project.yaml is missing or invalid.') from None
