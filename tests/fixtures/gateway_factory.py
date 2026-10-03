"""Docker-only synthetic transport injection. Production has no upstream override."""

import os
from pathlib import Path

import httpx

from aictrl.gateway.app import create_app
from aictrl.gateway.session import load_session
from aictrl.policy.loader import load_policy
from aictrl.reporting.store import EventStore


class SyntheticTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        assert request.url.scheme == 'https' and request.url.host == 'api.anthropic.com'
        assert 'x-aictrl-session' not in request.headers
        url = request.url.copy_with(scheme='http', host=os.environ['AICTRL_SYNTHETIC_IP'], port=8081)
        synthetic = httpx.Request(request.method, url, headers=request.headers, content=request.content)
        return await self.transport.handle_async_request(synthetic)

    async def aclose(self):
        await self.transport.aclose()


def application():
    client = httpx.AsyncClient(transport=SyntheticTransport(), trust_env=False, timeout=5)
    return create_app(load_session(Path(os.environ['AICTRL_SESSION_FILE'])),
                      load_policy(Path(os.environ['AICTRL_POLICY_FILE'])),
                      EventStore(Path(os.environ['AICTRL_EVENTS_DB'])), client)
