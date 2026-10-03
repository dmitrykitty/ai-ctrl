"""Non-root probes through production Codex bootstrap; no credential access."""
import http.client
import json
import os
import socket
import subprocess
import time
from pathlib import Path

checks = {}
status = dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
checks['host_uid_gid'] = (os.getuid(),os.getgid()) == (int(os.environ['AICTRL_UID']),int(os.environ['AICTRL_GID']))
checks['all_capability_sets_empty'] = all(int(status[name],16) == 0 for name in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))
checks['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
checks['cpu_limit'] = Path('/sys/fs/cgroup/cpu.max').read_text().strip() == '200000 100000'
checks['memory_limit'] = Path('/sys/fs/cgroup/memory.max').read_text().strip() == str(2048*1024*1024)
checks['pid_limit'] = Path('/sys/fs/cgroup/pids.max').read_text().strip() == '256'
checks['firewall_mutation_denied'] = subprocess.run(['iptables','-F'],capture_output=True).returncode != 0
checks['codex_version'] = subprocess.check_output(['codex','--version'],text=True).strip() == 'codex-cli 0.159.3'
checks['provider_state_writable'] = os.access('/home/dev/.codex',os.W_OK)
Path('/home/dev/.codex/synthetic-marker').write_text('public fixture state')
checks['workspace_read'] = Path('/workspace/input.txt').read_text() == 'host workspace\n'
Path('/workspace/input.txt').write_text('edited by agent\n')
Path('/workspace/created.txt').write_text('agent workspace\n')
checks['workspace_create_edit'] = Path('/workspace/created.txt').is_file()
checks['host_credentials_absent'] = not any(Path(name).exists() for name in ('/home/dev/.ssh','/home/dev/.aws','/home/dev/.kube','/host'))
checks['docker_socket_absent'] = not Path('/var/run/docker.sock').exists()
public = Path('/etc/aictrl/proxy-ca.pem').read_bytes()
checks['only_public_ca'] = b'BEGIN CERTIFICATE' in public and b'PRIVATE KEY' not in public and not Path('/home/mitmproxy/.mitmproxy').exists()


def tcp_denied(address,port,family=socket.AF_INET):
    with socket.socket(family,socket.SOCK_STREAM) as connection:
        connection.settimeout(.8)
        try: connection.connect((address,port))
        except OSError: return True
    return False


def udp_denied(address,port):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as connection:
        connection.settimeout(.8)
        try:
            connection.sendto(b'AICTRL_SYNTHETIC', (address,port))
            connection.recv(4096)
        except OSError: return True
    return False


for authority in ('api.openai.com:443','chatgpt.com:443'):
    with socket.create_connection((os.environ['AICTRL_PROXY_IP'],8080),timeout=3) as connection:
        connection.sendall(f'CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n'.encode())
        checks['generic_proxy_denies_'+authority.split(':')[0]] = b' 403 ' in connection.recv(4096).split(b'\r\n',1)[0]
gateway = os.environ['AICTRL_GATEWAY_IP']
connection = http.client.HTTPConnection(gateway,8000,timeout=5)
connection.request('GET','/codex/responses',headers={'X-AICtrl-Session':os.environ['AICTRL_SESSION_TOKEN']})
blocked = connection.getresponse(); checks['policy_denied_get'] = blocked.status == 403; blocked.read(); connection.close()
connection = http.client.HTTPConnection(gateway,8000,timeout=5)
connection.request('POST','/codex/responses',body='{"input":"public synthetic input"}',headers={'Content-Type':'application/json'})
blocked = connection.getresponse(); checks['missing_identity_denied'] = blocked.status == 401; blocked.read(); connection.close()
connection = http.client.HTTPConnection(gateway,8000,timeout=5)
headers = {'Content-Type':'application/json','Authorization':'Bearer synthetic-provider',
           'ChatGPT-Account-ID':'synthetic-account','X-AICtrl-Session':os.environ['AICTRL_SESSION_TOKEN']}
connection.request('POST','/codex/responses?x=a%2Fb',body='{"input":[],"metadata":{"synthetic_tool":true},"stream":true}',headers=headers)
response = connection.getresponse()
started = time.monotonic(); first = response.readline(); elapsed = time.monotonic()-started
body = first + response.read(); connection.close()
checks['incremental_responses_sse'] = response.status == 200 and first.startswith(b'event: response.created') and elapsed < .12
checks['native_function_call'] = b'function_call' in body and b'call_synthetic' in body
connection = http.client.HTTPConnection(gateway,8000,timeout=5)
connection.request('POST','/codex/responses',body='{"input":[{"type":"function_call_output","call_id":"call_synthetic","output":"public tool fixture"}],"stream":true}',headers=headers)
response = connection.getresponse(); checks['native_tool_followup'] = response.status == 200 and b'AICTRL_SYNTHETIC_CODEX_OK' in response.read(); connection.close()

# Native pinned CLI verifies the public profile and the same gateway route.
# Auth is disabled only for this synthetic fixture, which has no native state.
# Production profile/authentication remain unchanged.
command = ['codex','--no-daemon','--strict-config','--profile','aictrl','exec','--skip-git-repo-check',
           '--ephemeral','--color','never','-c','model_providers.aictrl.requires_openai_auth=false']
native = subprocess.run(command,input='Reply with exactly: AICTRL_SYNTHETIC_CODEX_OK',text=True,capture_output=True,timeout=40)
checks['pinned_cli_native_responses'] = native.returncode == 0 and native.stdout.strip() == 'AICTRL_SYNTHETIC_CODEX_OK'
# Only a safe classification leaves the fixture; no native payload/error text.
if not checks['pinned_cli_native_responses']:
    checks['native_profile_rejected'] = 'config' in native.stderr.lower() and 'error' in native.stderr.lower()

for name in tuple(os.environ):
    if name.lower().endswith('_proxy'): os.environ.pop(name)
checks['direct_public_denied'] = tcp_denied('1.1.1.1',443)
checks['direct_synthetic_denied'] = tcp_denied(os.environ['AICTRL_TEST_TARGET_IP'],8081)
checks['host_service_denied'] = tcp_denied(os.environ['AICTRL_TEST_HOST_IP'],int(os.environ['AICTRL_TEST_HOST_PORT']))
checks['live_sibling_denied'] = tcp_denied(os.environ['AICTRL_TEST_SIBLING_IP'],8081)
checks['dns_tcp_denied'] = tcp_denied('127.0.0.11',53) and tcp_denied('1.1.1.1',53)
checks['dns_udp_denied'] = udp_denied('127.0.0.11',53) and udp_denied('1.1.1.1',53)
checks['other_udp_denied'] = udp_denied(os.environ['AICTRL_TEST_TARGET_IP'],8082)
checks['ipv6_denied'] = tcp_denied('2606:4700:4700::1111',443,socket.AF_INET6)
print('AICTRL_CODEX_PROBE '+json.dumps(checks,sort_keys=True),flush=True)
raise SystemExit(0 if all(value for key,value in checks.items() if key != 'native_profile_rejected') else 1)
