from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaudeRuntime(StrictConfig):
    image: str = Field(min_length=1)
    state_volume: Literal["aictrl-claude-state"]
    state_mount: Literal["/home/dev/.claude"]
    auth_mode: Literal["subscription"]


class RuntimeLimits(StrictConfig):
    cpus: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(gt=0)
    pids: int = Field(gt=0)
    wall_time_seconds: int = Field(gt=0)


class ProjectConfig(StrictConfig):
    schema_version: Literal[1]
    milestone: Literal["T01"]
    claude: ClaudeRuntime
    limits: RuntimeLimits
