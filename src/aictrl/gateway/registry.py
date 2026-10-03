"""Immutable trusted protocol registry, independent of CLI/agent brands."""

from collections.abc import Callable, Mapping
from types import MappingProxyType

from aictrl.contracts import AgentProtocol
from aictrl.gateway.anthropic import AnthropicMessagesHandler
from aictrl.gateway.protocols import NativeProtocolHandler
from aictrl.gateway.responses import ResponsesHandler

PROTOCOL_HANDLERS: Mapping[AgentProtocol, Callable[[], NativeProtocolHandler]] = MappingProxyType({
    AgentProtocol.ANTHROPIC_MESSAGES: AnthropicMessagesHandler,
    AgentProtocol.RESPONSES: ResponsesHandler,
})


def resolve_handler(protocol: AgentProtocol) -> NativeProtocolHandler:
    try:
        return PROTOCOL_HANDLERS[protocol]()
    except KeyError:
        raise ValueError('Unsupported trusted gateway protocol.') from None
