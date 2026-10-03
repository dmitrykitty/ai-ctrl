"""Run after the exact production bootstrap, with the production proxy."""

import json
import os
import socket
import subprocess
from pathlib import Path

checks = {}
proxy = os.environ['AICTRL_PROXY_IP']
target = os.environ['AICTRL_TEST_TARGET_IP']
sibling = os.environ['AICTRL_TEST_SIBLING_IP']
host = os.environ['AICTRL_TEST_HOST_IP']
host_port = int(os.environ['AICTRL_TEST_HOST_PORT'])


def blocked_tcp(address, port, family=socket.AF_INET):
    with socket.socket(family, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        try:
            connection.connect((address, port))
        except OSError:
            return True
    return False


def inaccessible(path):
    try:
        return not Path(path).exists()
    except PermissionError:
        return True


def blocked_udp(address, port, data=b'AICTRL_SYNTHETIC'):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(1)
        try:
            connection.sendto(data, (address, port))
            connection.recv(4096)
        except OSError:
            return True
    return False


def proxy_request(authority, path, connect=False):
    with socket.create_connection((proxy, 8080), timeout=5) as connection:
        if connect:
            connection.sendall(f'CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n'.encode())
            response = connection.recv(4096)
            if b' 200 ' not in response.split(b'\r\n', 1)[0]:
                return response
            connection.sendall(f'GET {path} HTTP/1.1\r\nHost: allowed.test\r\nConnection: close\r\n\r\n'.encode())
        else:
            connection.sendall(f'GET http://{authority}{path} HTTP/1.1\r\nHost: {authority}\r\nConnection: close\r\n\r\n'.encode())
        parts = []
        while part := connection.recv(4096):
            parts.append(part)
        return b''.join(parts)


status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
checks['host_uid_gid'] = (os.getuid(), os.getgid()) == (int(os.environ['AICTRL_UID']), int(os.environ['AICTRL_GID']))
checks['non_root'] = os.getuid() != 0
checks['all_capability_sets_empty'] = all(int(status[name].strip(), 16) == 0 for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))
checks['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
checks['cpu_limit'] = Path('/sys/fs/cgroup/cpu.max').read_text().strip() == '200000 100000'
checks['memory_limit'] = Path('/sys/fs/cgroup/memory.max').read_text().strip() == str(2048 * 1024 * 1024)
checks['pid_limit'] = Path('/sys/fs/cgroup/pids.max').read_text().strip() == '256'
checks['firewall_mutation_denied'] = subprocess.run(['iptables', '-F'], capture_output=True).returncode != 0
checks['workspace_read'] = Path('/workspace/input.txt').read_text() == 'host workspace\n'
Path('/workspace/created.txt').write_text('agent workspace\n')
Path('/workspace/input.txt').write_text('edited by agent\n')
checks['workspace_create_edit'] = Path('/workspace/created.txt').is_file()
checks['dedicated_state_writable'] = os.access('/home/dev/.claude', os.W_OK)
checks['host_credentials_absent'] = all(inaccessible(p) for p in ('/root/.ssh', '/root/.aws', '/home/dev/.ssh', '/home/dev/.aws', '/home/dev/.kube', '/home/dev/.codex', '/home/dev/.aictrl', '/host'))
checks['docker_socket_absent'] = not Path('/var/run/docker.sock').exists()
public = Path('/etc/aictrl/proxy-ca.pem').read_bytes()
checks['only_public_ca'] = b'BEGIN CERTIFICATE' in public and b'PRIVATE KEY' not in public and not Path('/home/mitmproxy/.mitmproxy').exists()
checks['real_claude_version'] = '2.1.285' in subprocess.check_output(['claude', '--version'], text=True)
checks['allowed_http'] = b'AICTRL_SYNTHETIC_OK' in proxy_request('allowed.test:8081', '/allowed')
checks['allowed_connect_tunnel'] = b'AICTRL_SYNTHETIC_OK' in proxy_request('allowed.test:8081', '/tunnel', True)
checks['unapproved_http_denied'] = b' 403 ' in proxy_request('denied.test:8081', '/denied').split(b'\r\n', 1)[0]
checks['unapproved_connect_denied'] = b' 403 ' in proxy_request('denied.test:8081', '/denied', True).split(b'\r\n', 1)[0]
checks['private_proxy_destination_denied'] = b' 403 ' in proxy_request(f'{target}:8081', '/private').split(b'\r\n', 1)[0]
checks['wrong_port_denied'] = b' 403 ' in proxy_request('allowed.test:8082', '/port').split(b'\r\n', 1)[0]
for key in tuple(os.environ):
    if key.lower().endswith('_proxy'):
        os.environ.pop(key)
checks['unset_proxy_direct_ipv4_denied'] = blocked_tcp(target, 8081) and blocked_tcp('1.1.1.1', 443)
checks['host_service_denied'] = blocked_tcp(host, host_port)
checks['live_sibling_denied'] = blocked_tcp(sibling, 8081)
checks['docker_dns_tcp_denied'] = blocked_tcp('127.0.0.11', 53)
query = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01'
checks['docker_dns_udp_denied'] = blocked_udp('127.0.0.11', 53, query)
checks['external_dns_tcp_udp_denied'] = blocked_tcp('1.1.1.1', 53) and blocked_udp('1.1.1.1', 53, query)
checks['live_udp_target_denied'] = blocked_udp(target, 8082)
checks['ipv6_denied'] = blocked_tcp('2606:4700:4700::1111', 443, socket.AF_INET6) and blocked_tcp('::1', 8081, socket.AF_INET6)
print('AICTRL_PROBE ' + json.dumps(checks), flush=True)
raise SystemExit(0 if all(checks.values()) else 1)
