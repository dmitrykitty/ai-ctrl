import asyncio
import importlib.util
from pathlib import Path

import pytest

PROXY_PATH = Path(__file__).resolve().parents[2] / "docker/auth-proxy.py"
spec = importlib.util.spec_from_file_location("auth_proxy", PROXY_PATH)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


@pytest.mark.parametrize("connect_line", [
    b"CONNECT example.com:443 HTTP/1.1",
    b"CONNECT claude.ai.evil.test:443 HTTP/1.1",
    b"CONNECT api.anthropic.com:80 HTTP/1.1",
    b"CONNECT 127.0.0.1:443 HTTP/1.1",
    b"CONNECT 169.254.169.254:443 HTTP/1.1",
    b"CONNECT user@claude.ai:443 HTTP/1.1",
    b"CONNECT claude.ai:443 HTTP/1.1\r\nInjected: yes",
    b"GET http://claude.ai/ HTTP/1.1",
])
def test_forbidden_connect_authority_is_rejected(connect_line):
    with pytest.raises(ValueError):
        proxy.connect_destination(connect_line)


def test_allowed_connect_and_private_dns_rebinding(monkeypatch):
    assert proxy.connect_destination(b"CONNECT claude.ai:443 HTTP/1.1") == "claude.ai"
    async def verify():
        async def private_dns(*args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 443))]
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", private_dns)
        with pytest.raises(ValueError, match="non-public"):
            await proxy.resolve_public("claude.ai")
    asyncio.run(verify())


def test_denied_request_never_opens_upstream_and_health_is_local(monkeypatch):
    async def verify():
        async def forbidden_upstream(host):
            raise AssertionError("forbidden destination must never resolve upstream")
        monkeypatch.setattr(proxy, "resolve_public", forbidden_upstream)
        server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0, limit=8192)
        port = server.sockets[0].getsockname()[1]
        async with server:
            for payload, status in (
                (b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n", b"403 Forbidden"),
                (b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n", b"200 OK"),
            ):
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(payload)
                await writer.drain()
                response = await asyncio.wait_for(reader.read(), timeout=2)
                assert status in response
                writer.close()
                await writer.wait_closed()
    asyncio.run(verify())
