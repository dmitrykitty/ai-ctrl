"""Native Responses protocol behavior; admission lives in ControlPipeline."""

import httpx

from aictrl.contracts import AgentProtocol, Channel, Direction, InspectionLevel
from aictrl.gateway.headers import codex_request_headers
from aictrl.gateway.sse import ResponsesTerminal
from aictrl.gateway.inspection import argument_strings, strings, text_content
from aictrl.guards.models import InspectionSegment, Source

# Explicitly approved native-subscription origin. No caller/env selector.
UPSTREAM = 'https://chatgpt.com/backend-api/codex'


class ResponsesHandler:
    protocol = AgentProtocol.RESPONSES
    channel = Channel.LLM
    direction = Direction.OUTBOUND
    inspection_level = InspectionLevel.STRUCTURED
    target = 'openai'

    def resolve_operation(self, method: str, path: str) -> str | None:
        return 'responses' if method == 'POST' and path == '/codex/responses' else None

    def build_upstream_url(self, operation: str, raw_query: bytes) -> httpx.URL:
        if operation != 'responses':
            raise ValueError('Unsupported native operation.')
        return httpx.URL(UPSTREAM + '/responses').copy_with(query=raw_query)

    filter_request_headers = staticmethod(codex_request_headers)
    new_stream_observer = staticmethod(ResponsesTerminal)

    @staticmethod
    def validate_payload(payload: object, operation: str) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get('input'), (list, str))

    @staticmethod
    def extract_inspection(payload: dict) -> tuple[InspectionSegment, ...]:
        segments = strings(payload.get('instructions'), ('instructions',), Source.SYSTEM_INSTRUCTION)
        value = payload['input']
        if isinstance(value, str):
            segments.extend(strings(value, ('input',), Source.USER_INPUT))
        else:
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    raise ValueError('Invalid Responses item.')
                path = ('input', index)
                if item.get('type') in ('function_call_output', 'custom_tool_call_output'):
                    segments.extend(strings(item.get('output'), (*path, 'output'), Source.TOOL_RESULT, untrusted=True))
                elif item.get('type') == 'function_call':
                    segments.extend(argument_strings(item.get('arguments'), (*path, 'arguments')))
                elif item.get('type') == 'custom_tool_call':
                    segments.extend(strings(item.get('input'), (*path, 'input'), Source.TOOL_ARGUMENT))
                else:
                    source = Source.MODEL_OUTPUT if item.get('role') == 'assistant' else Source.USER_INPUT
                    segments.extend(text_content(item.get('content'), (*path, 'content'), source))
        return tuple(segments)

    @staticmethod
    def new_output_buffer(max_bytes: int):
        from aictrl.gateway.output import ResponsesOutputBuffer
        return ResponsesOutputBuffer(max_bytes)
