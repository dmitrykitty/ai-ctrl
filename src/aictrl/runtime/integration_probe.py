"""Small qualification workload run inside the normal managed agent sandbox.

The host supplies this trusted source as Python command text, so qualification
needs neither another mount nor a rebuilt runtime image. Only safe results leave
the sandbox; native output, internal identity and provider state are not printed.
"""

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from uuid import UUID

EXPECTED = 'AICTRL_T04_OK'
PREFIX = 'AICTRL_INTEGRATION_RESULT '


def main() -> None:
    result = {'claude_exit': -1, 'claude_response': None, 'forbidden_status': -1,
              'forbidden_request_id': None, 'direct_blocked': False,
              'direct_errno': None, 'proxy_denied': False}
    try:
        # Match the normal launcher's non-root, credential-free UI preparation.
        subprocess.run(['python', '/usr/local/bin/prepare-claude-ui.py'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        native = subprocess.run(['claude', '--print', '--output-format', 'text'],
                                input=sys.stdin.read(), capture_output=True, text=True)
        result['claude_exit'] = native.returncode
        if native.returncode == 0 and native.stdout.strip() == EXPECTED:
            result['claude_response'] = EXPECTED
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        token = os.environ['ANTHROPIC_CUSTOM_HEADERS'].split(': ', 1)[1]
        request = urllib.request.Request(os.environ['ANTHROPIC_BASE_URL'] + '/v1/messages',
                                         method='GET', headers={'X-AICtrl-Session': token})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=5) as response:
                result['forbidden_status'] = response.status
        except urllib.error.HTTPError as error:
            result['forbidden_status'] = error.code
            payload = json.load(error)
            result['forbidden_request_id'] = str(UUID(payload['request_id']))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass

    # Low-level sockets ignore HTTP proxy and gateway environment variables.
    try:
        with socket.create_connection(('1.1.1.1', 443), timeout=2):
            pass
    except OSError as error:
        result['direct_blocked'] = True
        result['direct_errno'] = error.errno

    try:
        with socket.create_connection((os.environ['AICTRL_PROXY_IP'], 8080), timeout=5) as connection:
            connection.sendall(b'CONNECT api.anthropic.com:443 HTTP/1.1\r\nHost: api.anthropic.com:443\r\n\r\n')
            result['proxy_denied'] = b' 403 ' in connection.recv(4096).split(b'\r\n', 1)[0]
    except (OSError, KeyError):
        pass

    print(PREFIX + json.dumps(result), flush=True)
    passed = (result['claude_exit'] == 0 and result['claude_response'] == EXPECTED
              and result['forbidden_status'] == 403 and result['forbidden_request_id'] is not None
              and result['direct_blocked'] and result['proxy_denied'])
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
