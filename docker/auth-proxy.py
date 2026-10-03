"""Provider-only CONNECT transport for native login, not the runtime gateway.

TLS remains end-to-end. Only the declared authentication hosts on port 443 may
be reached. No request bodies, authorization headers, or OAuth codes are logged.
The planned runtime mitmproxy integration belongs to T02 and later milestones.
"""

import asyncio
import ipaddress
import re
import socket

ALLOWED_HOSTS = frozenset({
    "claude.ai", "claude.com", "platform.claude.com", "console.anthropic.com",
    "api.anthropic.com",  # Native authentication connectivity/account checks.
})
ACTIVE_CONNECTIONS = asyncio.Semaphore(32)


def connect_destination(line: bytes) -> str:
    match = re.fullmatch(rb"CONNECT ([a-zA-Z0-9.-]+):443 HTTP/1\.[01]", line)
    if match is None:
        raise ValueError("only HTTPS CONNECT is supported")
    host = match[1].decode("ascii").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("destination is not an authentication host")
    return host


async def resolve_public(host: str) -> str:
    async with asyncio.timeout(10):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise ValueError("non-public upstream address refused")
    # Connect to the checked numeric address to prevent DNS re-resolution races.
    return addresses[0][4][0]


async def relay(source: asyncio.StreamReader, destination: asyncio.StreamWriter) -> None:
    while data := await source.read(65536):
        destination.write(data)
        await destination.drain()


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    upstream_writer = None
    connected = False
    try:
        async with ACTIVE_CONNECTIONS, asyncio.timeout(600):
            async with asyncio.timeout(10):
                headers = await reader.readuntil(b"\r\n\r\n")
            if len(headers) > 8192:
                raise ValueError("oversized headers")
            line = headers.split(b"\r\n", 1)[0]
            if line == b"GET /healthz HTTP/1.1":
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
                await writer.drain()
                return
            host = connect_destination(line)
            address = await resolve_public(host)
            async with asyncio.timeout(10):
                upstream_reader, upstream_writer = await asyncio.open_connection(address, 443)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            connected = True
            tasks = (
                asyncio.create_task(relay(reader, upstream_writer)),
                asyncio.create_task(relay(upstream_reader, writer)),
            )
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (ValueError, OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        if not connected:
            writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            try:
                await writer.drain()
            except OSError:
                pass
    finally:
        if upstream_writer is not None:
            upstream_writer.close()
        writer.close()


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", 8080, limit=8192)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
