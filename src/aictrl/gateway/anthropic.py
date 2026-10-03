"""Native Anthropic Messages protocol; admission lives in ControlPipeline."""

from types import MappingProxyType

import httpx

from aictrl.contracts import AgentProtocol, Channel, Direction, InspectionLevel
from aictrl.gateway.headers import request_headers

UPSTREAM = 'https://api.anthropic.com'
PATHS = MappingProxyType({'/anthropic/v1/messages': 'messages',
                         '/anthropic/v1/messages/count_tokens': 'count_tokens'})


class AnthropicMessagesHandler:
    protocol = AgentProtocol.ANTHROPIC_MESSAGES
    channel = Channel.LLM
    direction = Direction.OUTBOUND
    inspection_level = InspectionLevel.STRUCTURED
    target = 'anthropic'

    def resolve_operation(self, method: str, path: str) -> str | None:
        return PATHS.get(path) if method == 'POST' else None

    def build_upstream_url(self, operation: str, raw_query: bytes) -> httpx.URL:
        paths = {'messages': '/v1/messages', 'count_tokens': '/v1/messages/count_tokens'}
        if operation not in paths:
            raise ValueError('Unsupported native operation.')
        return httpx.URL(UPSTREAM + paths[operation]).copy_with(query=raw_query)

    @staticmethod
    def validate_payload(payload: object, operation: str) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get('messages'), list)

    filter_request_headers = staticmethod(request_headers)

    @staticmethod
    def new_stream_observer():
        return None
