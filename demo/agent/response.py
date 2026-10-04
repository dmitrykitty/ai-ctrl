"""Real isolated SDK client for bounded host restriction/termination proofs."""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def demonstrate() -> int:
    mode = os.environ['AICTRL_RESPONSE_CASE']
    url = os.environ['AICTRL_GATEWAY_URL']
    async with httpx2.AsyncClient(headers={'X-AICtrl-Session': os.environ['AICTRL_SESSION_TOKEN']},
                                  trust_env=False, timeout=3) as http:
        async with Client(streamable_http_client(url + '/mcp', http_client=http), cache=None) as client:
            denied = await client.call_tool('echo_contact', {'contact': 'AICTRL_SECRET_demo'})
            if not denied.is_error or 'guard.secret.detected' not in str(denied):
                return 1
            print('AICTRL_RESPONSE_BLOCKED', flush=True)
            if mode == 'terminate':
                await asyncio.sleep(45)  # The host must SIGTERM before this deadline.
                return 1
            marker = Path('/workspace/response-disconnected')
            for _ in range(200):
                if marker.exists():
                    break
                await asyncio.sleep(0.1)
            else:
                return 1
            disconnected = False
            try:
                await http.get(url + '/health')
            except (httpx2.TransportError, TimeoutError):
                disconnected = True
            print('AICTRL_RESPONSE_CLIENT ' + json.dumps({'gateway_unreachable_after_restrict': disconnected}), flush=True)
            return 0 if disconnected else 1


if __name__ == '__main__':
    logging.getLogger('mcp').setLevel(logging.CRITICAL)
    try:
        code = asyncio.run(demonstrate())
    except Exception:
        print('AICTRL RESPONSE CLIENT FAIL: control unavailable.', flush=True)
        code = 1
    raise SystemExit(code)
