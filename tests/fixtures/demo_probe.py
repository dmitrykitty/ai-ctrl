"""Actual stateless workload: isolated primitives plus the official MCP client."""

import json
import os
from pathlib import Path
import runpy
import socket

checks={}
status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
checks['nonroot_host_uid_gid']=os.getuid()==int(os.environ['AICTRL_UID']) and os.getgid()==int(os.environ['AICTRL_GID']) and os.getuid()!=0
checks['all_capabilities_zero']=all(int(status[key].strip(),16)==0 for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))
checks['no_new_privileges']=status['NoNewPrivs'].strip()=='1'
def inaccessible(path):
    try:
        return not Path(path).exists()
    except PermissionError:
        return True
checks['no_access_to_host_credentials_socket_or_semantic_secret']=all(inaccessible(path) for path in ('/var/run/docker.sock','/root/.ssh','/root/.aws','/root/.kube','/home/dev/.ssh','/home/dev/.aws','/home/dev/.kube','/host','/run/secrets/aictrl/jev_api_key'))
checks['no_provider_authentication_state']=all(inaccessible(path) for path in ('/home/dev/.claude/.credentials.json','/home/dev/.codex/auth.json'))
checks['no_semantic_environment']=not any('JEV' in key.upper() for key in os.environ)

def blocked(address,port,*,family=socket.AF_INET,kind=socket.SOCK_STREAM):
    client=socket.socket(family,kind)
    client.settimeout(.3)
    try:
        if kind==socket.SOCK_DGRAM: client.sendto(b'synthetic probe',(address,port)); client.recvfrom(32)
        else: client.connect((address,port))
        return False
    except OSError: return True
    finally: client.close()

checks['direct_internet_blocked']=blocked('1.1.1.1',443)
checks['tcp_dns_blocked']=blocked('127.0.0.11',53)
checks['udp_dns_blocked']=blocked('127.0.0.11',53,kind=socket.SOCK_DGRAM)
checks['udp_internet_blocked']=blocked('1.1.1.1',443,kind=socket.SOCK_DGRAM)
checks['ipv6_blocked']=blocked('2606:4700:4700::1111',443,family=socket.AF_INET6)
for host in ('chatgpt.com','api.openai.com','api.anthropic.com','api.typesafe.ai'):
    client=socket.create_connection((os.environ['AICTRL_PROXY_IP'],8080),timeout=3)
    client.sendall(('CONNECT '+host+':443 HTTP/1.1\r\nHost: '+host+':443\r\n\r\n').encode())
    checks['proxy_denies_'+host.replace('.','_')]=b' 403 ' in client.recv(256).split(b'\r\n')[0]
    client.close()
print('AICTRL_DEMO_BOUNDARY '+json.dumps(checks,sort_keys=True),flush=True)
if not all(checks.values()): raise SystemExit(1)
runpy.run_path('/opt/aictrl/demo/agent/main.py',run_name='__main__')
