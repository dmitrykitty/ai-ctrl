"""Native Responses protocol behavior; admission lives in ControlPipeline."""

import httpx

from aictrl.contracts import AgentProtocol, Channel, Direction, InspectionLevel
from aictrl.gateway.headers import codex_request_headers
from aictrl.gateway.sse import ResponsesTerminal

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
