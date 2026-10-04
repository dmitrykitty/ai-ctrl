"""Native Anthropic Messages protocol; admission lives in ControlPipeline."""

from types import MappingProxyType

import httpx

from aictrl.contracts import AgentProtocol, Channel, Direction, InspectionLevel
from aictrl.gateway.headers import request_headers
from aictrl.gateway.inspection import text_content
from aictrl.guards.models import InspectionSegment, Source
from aictrl.gateway.sse import AnthropicTerminal
from aictrl.gateway.usage import AnthropicUsage, requested_reservation

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
    def extract_inspection(payload: dict) -> tuple[InspectionSegment, ...]:
        segments = text_content(payload.get('system'), ('system',), Source.SYSTEM_INSTRUCTION)
        for index, message in enumerate(payload['messages']):
            if not isinstance(message, dict):
                raise ValueError('Invalid message shape.')
            source = Source.MODEL_OUTPUT if message.get('role') == 'assistant' else Source.USER_INPUT
            segments.extend(text_content(message.get('content'), ('messages', index, 'content'), source))
        return tuple(segments)

    @staticmethod
    def new_output_buffer(max_bytes: int):
        from aictrl.gateway.output import AnthropicOutputBuffer
        return AnthropicOutputBuffer(max_bytes)

    new_stream_observer = staticmethod(AnthropicTerminal)
    new_usage_collector = staticmethod(AnthropicUsage)

    @staticmethod
    def token_reservation(payload: dict, settings) -> int:
        return requested_reservation(payload, 'max_tokens', settings.token_reservation, settings.input_token_allowance)
