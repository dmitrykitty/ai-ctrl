from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    operation: str


@dataclass(frozen=True)
class ResourceDefinition:
    uri: str
    name: str
    operation: str


class MCPBackend(Protocol):
    def list_tools(self) -> tuple[ToolDefinition, ...]: ...
    def list_resources(self) -> tuple[ResourceDefinition, ...]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...
    async def read_resource(self, uri: str) -> str: ...
