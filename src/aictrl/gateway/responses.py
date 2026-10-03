"""Native Responses over HTTP/SSE, sharing the existing admission pipeline."""
from aictrl.gateway.anthropic import AnthropicGateway
from aictrl.gateway.headers import codex_request_headers
from aictrl.gateway.sse import ResponsesTerminal

# Explicitly approved native-subscription origin. No caller/env selector.
UPSTREAM = 'https://chatgpt.com/backend-api/codex'


class ResponsesGateway(AnthropicGateway):
    protocol = 'RESPONSES'
    target = 'openai'
    paths = {'/codex/responses': 'responses'}
    upstream_paths = {'responses': UPSTREAM + '/responses'}
    provider_headers = staticmethod(codex_request_headers)
    stream_observer = staticmethod(ResponsesTerminal)

    @staticmethod
    def valid_payload(payload: object) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get('input'), (list, str))
