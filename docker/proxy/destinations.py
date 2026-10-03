"""Small, static T02 destination list; not the central policy engine."""

import asyncio
import ipaddress
import json
import re
import socket
from pathlib import Path


class DestinationList:
    def __init__(self, records: list[dict]) -> None:
        self.destinations: dict[tuple[str, int], str | None] = {}
        # A stateless MCP-only agent has no external destinations. An empty
        # allowlist is a valid deny-all policy; address() rejects before DNS.
        for record in records:
            if set(record) - {"host", "port", "connect_ip"}:
                raise ValueError("Unknown runtime destination field")
            host, port = record["host"], record["port"]
            if not isinstance(host, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host) or ".." in host:
                raise ValueError("Exact lowercase destination host required")
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Invalid destination port")
            address = record.get("connect_ip")
            if address:
                ip = ipaddress.IPv4Address(address)
                if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
                    raise ValueError("Unsafe explicit test destination")
            if (host, port) in self.destinations:
                raise ValueError("Duplicate runtime destination")
            self.destinations[host, port] = address

    @classmethod
    def from_file(cls, path: Path) -> "DestinationList":
        records = json.loads(path.read_text())
        if not isinstance(records, list):
            raise ValueError("Runtime destinations must be a list")
        return cls(records)

    def permits(self, host: str, port: int) -> bool:
        return (host.lower(), port) in self.destinations

    async def address(self, host: str, port: int) -> str:
        key = host.lower(), port
        if key not in self.destinations:
            raise ValueError("Destination denied")
        if self.destinations[key]:
            return self.destinations[key]
        answers = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, key[0], port, socket.AF_INET, socket.SOCK_STREAM), 10,
        )
        addresses = [ipaddress.ip_address(answer[4][0]) for answer in answers]
        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("Non-public destination resolution denied")
        # Connect to the checked numeric address, without a second DNS lookup.
        return str(addresses[0])
