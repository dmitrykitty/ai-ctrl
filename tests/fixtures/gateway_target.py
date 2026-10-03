"""Synthetic native endpoint with safe aggregate counters, never payload logs."""

import json
import threading
from http.server import ThreadingHTTPServer

from runtime_target import Handler, counts, udp

SSE = b'event: message_start\ndata: {"type":"message_start"}\n\nevent: ping\ndata: {"type":"ping"}\n\nevent: message_stop\ndata: {"type":"message_stop"}\n\n'


class NativeHandler(Handler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        assert json.loads(body)['messages']
        assert self.headers['Authorization'] == 'Bearer synthetic-provider'
        assert self.headers['anthropic-version'] == '2023-06-01'
        assert self.headers['anthropic-beta'] == 'synthetic-beta'
        assert self.headers.get('X-AICtrl-Session') is None
        counts[self.path] += 1
        result = b'{"input_tokens":7}' if self.path.startswith('/v1/messages/count_tokens') else SSE
        self.send_response(200)
        self.send_header('Content-Type', 'application/json' if self.path.startswith('/v1/messages/count_tokens') else 'text/event-stream')
        self.send_header('Content-Length', str(len(result)))
        self.end_headers()
        self.wfile.write(result)


if __name__ == '__main__':
    threading.Thread(target=udp, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 8081), NativeHandler).serve_forever()
