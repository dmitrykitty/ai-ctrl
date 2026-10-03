"""Synthetic HTTP/UDP counters for the real Docker boundary probes."""

import json
import socket
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

counts = Counter()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/counts':
            counts[self.path] += 1
        body = json.dumps(dict(counts)).encode() if self.path == '/counts' else b'AICTRL_SYNTHETIC_OK'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(('0.0.0.0', 8082))
        while True:
            body, peer = server.recvfrom(1024)
            counts['udp'] += 1
            server.sendto(body, peer)


if __name__ == '__main__':
    threading.Thread(target=udp, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 8081), Handler).serve_forever()
