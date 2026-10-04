"""Native numeric usage only, independent of text/arguments and output release."""

import re

from aictrl.contracts import BillingMode, ControlRequest, UsageMetric
from aictrl.gateway.inspection import strict_json


class NativeUsage:
    def __init__(self, operation: str, max_bytes: int = 1048576) -> None:
        self.operation, self.max_bytes = operation, max_bytes
        self.pending = bytearray()
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.completed = False
        self.invalid = False

    @staticmethod
    def number(value: object) -> int:
        if type(value) is not int or not 0 <= value <= 1_000_000_000:
            raise ValueError('Invalid usage counter.')
        return value

    def observe(self, chunk: bytes) -> None:
        if self.invalid:
            return
        self.pending.extend(chunk)
        while match := re.search(rb'(?:\r?\n){2}', self.pending):
            frame = bytes(self.pending[:match.end()])
            del self.pending[:match.end()]
            if len(frame) > self.max_bytes:
                self.invalid = True
                self.pending.clear()
                return
            data = b'\n'.join(line[5:].lstrip(b' ') for line in frame.splitlines() if line.startswith(b'data:'))
            if not data or data == b'[DONE]':
                continue
            try:
                payload = strict_json(data)
                if isinstance(payload, dict):
                    self.observe_json(payload)
            except (ValueError, RecursionError, TypeError):
                self.invalid = True
        if len(self.pending) > self.max_bytes:
            self.pending.clear()
            self.invalid = True

    def observe_json(self, payload: dict) -> None:
        raise NotImplementedError

    def metric(self, request: ControlRequest) -> UsageMetric | None:
        if self.invalid or not self.completed or self.input_tokens is None or self.output_tokens is None:
            return None
        return UsageMetric(request_id=request.request_id, session_id=request.session_id,
            input_tokens=self.input_tokens, output_tokens=self.output_tokens, requests=1, agent_steps=1,
            billing_mode=BillingMode.SUBSCRIPTION, cost_microunits=None)


class AnthropicUsage(NativeUsage):
    def __init__(self, operation: str) -> None:
        super().__init__(operation)
        self.final_usage = False

    def counters(self, usage: object, *, initial: bool) -> None:
        if not isinstance(usage, dict):
            raise ValueError('Invalid usage shape.')
        if initial:
            self.input_tokens = sum(self.number(usage.get(name, 0)) for name in (
                'input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')) if 'input_tokens' in usage else None
            if self.input_tokens is not None:
                self.number(self.input_tokens)
        if 'output_tokens' in usage:
            value = self.number(usage['output_tokens'])
            if self.output_tokens is not None and value < self.output_tokens:
                raise ValueError('Decreasing usage.')
            self.output_tokens = value
            if not initial:
                self.final_usage = True

    def observe_json(self, payload: dict) -> None:
        try:
            event = payload.get('type')
            if event == 'message_start':
                message = payload.get('message')
                if isinstance(message, dict) and 'usage' in message:
                    self.counters(message['usage'], initial=True)
            elif event == 'message_delta' and 'usage' in payload:
                self.counters(payload['usage'], initial=False)
            elif event == 'message_stop':
                self.completed = self.final_usage
            elif event == 'message' and 'usage' in payload:
                self.counters(payload['usage'], initial=True)
                self.completed = True
            elif self.operation == 'count_tokens' and 'input_tokens' in payload:
                self.input_tokens, self.output_tokens = self.number(payload['input_tokens']), 0
                self.completed = True  # this native operation does not generate text
        except (ValueError, TypeError):
            self.invalid = True


class ResponsesUsage(NativeUsage):
    def observe_json(self, payload: dict) -> None:
        try:
            response = payload.get('response') if payload.get('type') == 'response.completed' else payload if payload.get('object') == 'response' and payload.get('status') == 'completed' else None
            if isinstance(response, dict) and 'usage' in response:
                usage = response['usage']
                if not isinstance(usage, dict):
                    raise ValueError('Invalid usage.')
                self.input_tokens = self.number(usage.get('input_tokens'))
                self.output_tokens = self.number(usage.get('output_tokens'))
                if 'total_tokens' in usage and self.number(usage['total_tokens']) != self.input_tokens + self.output_tokens:
                    raise ValueError('Inconsistent usage.')
                self.completed = True
        except (ValueError, TypeError):
            self.invalid = True


def requested_reservation(payload: dict, field: str, fallback: int, input_allowance: int) -> int:
    value = payload.get(field)
    return (value if type(value) is int and 0 < value <= 10_000_000 else fallback) + input_allowance
