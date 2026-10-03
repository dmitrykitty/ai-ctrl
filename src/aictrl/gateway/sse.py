"""Bounded SSE framing for terminal events, without parsing Responses payloads."""


class NativeTerminal:
    def __init__(self, success: bytes, failures: tuple[bytes, ...]) -> None:
        self._success, self._failures = success, failures
        self.completed = False
        self.failed = False
        self._prefix = bytearray()
        self._overflow = False
        self._event = b''
        self._data = False

    def observe(self, chunk: bytes) -> None:
        for value in chunk:
            if value == 10:
                line = bytes(self._prefix).rstrip(b'\r')
                if not line and not self._overflow:
                    if self._data:
                        self.completed |= self._event == self._success
                        self.failed |= self._event in self._failures
                    self._event, self._data = b'', False
                elif line.startswith(b'event:') and not self._overflow:
                    self._event = line[6:].strip()
                elif line.startswith(b'data:'):
                    self._data |= bool(line[5:].strip()) or self._overflow
                self._prefix.clear()
                self._overflow = False
            elif len(self._prefix) < 128:
                self._prefix.append(value)
            else:
                self._overflow = True


class ResponsesTerminal(NativeTerminal):
    def __init__(self) -> None:
        super().__init__(b'response.completed', (b'response.failed', b'response.incomplete', b'error'))


class AnthropicTerminal(NativeTerminal):
    def __init__(self) -> None:
        super().__init__(b'message_stop', (b'error',))
