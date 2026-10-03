"""Adapted from agent-sandbox images/proxy/addons/enforcer.py.

MIT, Matt Olson 2026; see LICENSE.agent-sandbox. T02 keeps request-header and
CONNECT enforcement, omitting credential injection, reload, and content policy.
"""

import os
import sys
from pathlib import Path

from mitmproxy import http

sys.path.insert(0, str(Path(__file__).parent))
from destinations import DestinationList


class RuntimeEnforcer:
    def __init__(self) -> None:
        self.destinations = DestinationList.from_file(Path(os.environ["AICTRL_DESTINATIONS_FILE"]))

    def running(self) -> None:
        Path('/tmp/aictrl-proxy-ready').touch()

    async def _admit(self, flow: http.HTTPFlow) -> None:
        try:
            await self.destinations.address(flow.request.host, flow.request.port)
        except (OSError, ValueError, TimeoutError):
            flow.response = http.Response.make(403, b"AICTRL destination denied\n", {"Content-Type": "text/plain"})

    async def http_connect(self, flow: http.HTTPFlow) -> None:
        await self._admit(flow)

    async def requestheaders(self, flow: http.HTTPFlow) -> None:
        await self._admit(flow)

    async def server_connect(self, data) -> None:
        try:
            host, port = data.server.address
            checked_ip = await self.destinations.address(host, port)
            data.server.address = checked_ip, port
        except (OSError, ValueError, TimeoutError, TypeError):
            data.server.error = "AICTRL destination denied"

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        if flow.response:
            flow.response.stream = True


addons = [RuntimeEnforcer()]
