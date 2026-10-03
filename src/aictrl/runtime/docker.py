"""Host-only Docker operations with safe error reporting."""

import ipaddress
import json
import secrets
import subprocess
from collections.abc import Callable


class RuntimeFailure(RuntimeError):
    pass


class RuntimeDeadline(RuntimeFailure):
    pass


def docker(arguments: list[str], timeout: float = 15, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeFailure('Docker operation is unavailable or timed out.') from None
    if check and result.returncode:
        raise RuntimeFailure('Docker operation failed. Verify the daemon, required images, and available resources.')
    return result


def free_subnet(run: Callable = docker) -> ipaddress.IPv4Network:
    identifiers = run(['network', 'ls', '--quiet']).stdout.split()
    occupied = []
    if identifiers:
        for network in json.loads(run(['network', 'inspect', *identifiers]).stdout):
            for item in network.get('IPAM', {}).get('Config') or []:
                if item.get('Subnet'):
                    occupied.append(ipaddress.ip_network(item['Subnet']))
    offset = secrets.randbelow(256)
    for second in range(28, 32):
        for index in range(256):
            candidate = ipaddress.ip_network(f'172.{second}.{(offset + index) % 256}.0/24')
            if not any(candidate.overlaps(network) for network in occupied if network.version == 4):
                return candidate
    raise RuntimeFailure('No isolated runtime subnet is available.')
