"""Code-owned extension points; workspace configuration cannot register code."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from aictrl.adapters.base import AgentAdapter, RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.adapters.codex import CodexAdapter
from aictrl.runtime.auth import claude_authenticated
from aictrl.runtime.codex_auth import codex_authenticated
from aictrl.runtime.config import ProjectConfig


class RuntimeProviderConfig(Protocol):
    image: str


@dataclass(frozen=True)
class RuntimeAgentSpec:
    factory: Callable[[str, RoutingMode], AgentAdapter]
    config: Callable[[ProjectConfig], RuntimeProviderConfig | None]
    authenticated: Callable[[str], bool]
    login_hint: str
    requires_gateway: bool = False


AGENT_REGISTRY: Mapping[str, RuntimeAgentSpec] = MappingProxyType({
    'claude': RuntimeAgentSpec(ClaudeAdapter, lambda settings: settings.claude,
                               claude_authenticated, 'make claude-login'),
    'codex': RuntimeAgentSpec(CodexAdapter, lambda settings: settings.codex,
                              codex_authenticated, 'make codex-login', requires_gateway=True),
})


def resolve_agent(name: str) -> RuntimeAgentSpec:
    try:
        return AGENT_REGISTRY[name]
    except KeyError:
        raise ValueError('Unsupported runtime agent.') from None
