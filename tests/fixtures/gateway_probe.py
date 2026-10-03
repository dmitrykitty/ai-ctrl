"""Exercise the native gateway after production firewall/privilege bootstrap."""

import json
import os
import runpy
import socket
import urllib.error
import urllib.request
from pathlib import Path

checks = {}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = os.environ['ANTHROPIC_BASE_URL']
token = os.environ['ANTHROPIC_CUSTOM_HEADERS'].split(': ', 1)[1]
body = json.dumps({'model': 'synthetic', 'messages': [{'role': 'user', 'content': 'synthetic-private-prompt'}], 'stream': True}).encode()


def native(path, identity=token):
    request = urllib.request.Request(base + path, data=body, headers={
        'X-AICtrl-Session': identity, 'Authorization': 'Bearer synthetic-provider',
        'Content-Type': 'application/json', 'anthropic-version': '2023-06-01', 'anthropic-beta': 'synthetic-beta',
    })
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


status, stream = native('/v1/messages?beta=true&x=a%2Fb')
checks['native_messages_through_gateway'] = status == 200 and [part.split(b'\n', 1)[0] for part in stream.split(b'\n\n') if part] == [b'event: message_start', b'event: ping', b'event: message_stop']
status, result = native('/v1/messages/count_tokens?beta=true')
checks['native_count_tokens'] = status == 200 and json.loads(result)['input_tokens'] == 7
checks['invalid_identity_blocked'] = native('/v1/messages', 'invalid-synthetic-token')[0] == 401
checks['unknown_route_blocked'] = native('/v1/models')[0] == 403
checks['agent_cannot_read_gateway_storage'] = all(not Path(path).exists() for path in ('/etc/aictrl/session.json', '/etc/aictrl/policy.yaml', '/var/lib/aictrl/events.sqlite3'))
with socket.create_connection((os.environ['AICTRL_PROXY_IP'], 8080), timeout=5) as connection:
    connection.sendall(b'CONNECT api.anthropic.com:443 HTTP/1.1\r\nHost: api.anthropic.com:443\r\n\r\n')
    checks['inference_connect_proxy_denied'] = b' 403 ' in connection.recv(4096).split(b'\r\n', 1)[0]
with socket.create_connection((os.environ['AICTRL_PROXY_IP'], 8080), timeout=5) as connection:
    connection.sendall(b'POST http://api.anthropic.com:443/v1/messages HTTP/1.1\r\nHost: api.anthropic.com:443\r\nContent-Length: 0\r\n\r\n')
    checks['inference_http_proxy_denied'] = b' 403 ' in connection.recv(4096).split(b'\r\n', 1)[0]
print('AICTRL_GATEWAY_PROBE ' + json.dumps(checks), flush=True)
assert all(checks.values()), 'Gateway boundary check failed'
# Qualify the affected runtime boundary once in APPLICATION_GATEWAY mode.
runpy.run_path('/workspace/runtime_probe.py', run_name='__main__')
