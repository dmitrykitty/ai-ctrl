"""Live checks of the T01 authentication bootstrap, without model requests."""

import json
import os
import socket
from pathlib import Path


def connect_status(host):
    with socket.create_connection(("172.30.88.2", 8080), timeout=15) as connection:
        connection.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode())
        return connection.recv(4096).split(b"\r\n", 1)[0]


def blocked_tcp(host, port, family=socket.AF_INET):
    with socket.socket(family, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        try:
            connection.connect((host, port))
        except OSError:
            return True
    return False


def blocked_dns_udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(2)
        # Valid A query for example.com to Docker's embedded resolver.
        query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01"
        try:
            connection.sendto(query, ("127.0.0.11", 53))
            connection.recv(4096)
        except OSError:
            return True
    return False


status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
checks = {
    "unprivileged_user": os.getuid() == 501,
    "capabilities_dropped": all(int(status[name].strip(), 16) == 0 for name in ("CapEff", "CapPrm", "CapInh", "CapAmb", "CapBnd")),
    "no_new_privileges": status["NoNewPrivs"].strip() == "1",
    "provider_connect_allowed": b"200" in connect_status("claude.ai"),
    "other_destination_denied": b"403" in connect_status("example.com"),
    "private_destination_denied": b"403" in connect_status("127.0.0.1"),
    "direct_internet_denied": blocked_tcp("1.1.1.1", 443),
    "docker_dns_tcp_denied": blocked_tcp("127.0.0.11", 53),
    "docker_dns_udp_denied": blocked_dns_udp(),
    "ipv6_direct_denied": blocked_tcp("2606:4700:4700::1111", 443, socket.AF_INET6),
}
print(json.dumps(checks, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
