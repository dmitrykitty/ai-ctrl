"""Deterministic live qualification using production launcher enforcement.

Only a synthetic state volume and explicitly pinned synthetic upstream are
substituted. No native authentication state or model endpoint is inspected.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.contracts import SessionState
from aictrl.runtime.config import TestDestination, load_config
from aictrl.runtime.docker import RuntimeFailure, docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


def clean_session(identifier):
    for resource in ('container', 'network', 'volume'):
        args = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        assert not docker([*args, '--filter', 'label=io.aictrl.session=' + identifier]).stdout.strip(), resource + ' leaked'


def settings_and_agent(volume, target_ip, seconds=90):
    settings = load_config(PROJECT_ROOT)
    settings.runtime.routing_mode = RoutingMode.EGRESS_ONLY
    settings.runtime.test_destinations = (TestDestination(host='allowed.test', port=8081, connect_ip=target_ip),)
    settings.limits.wall_time_seconds = seconds
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY)
    agent.persistent_state_volume = volume
    agent.required_provider_endpoints = ()
    assert settings.runtime.routing_mode == RoutingMode.EGRESS_ONLY
    return settings, agent


def child():
    workspace, volume, target_ip, network, seconds, mode = sys.argv[2:]
    settings, agent = settings_and_agent(volume, target_ip, int(seconds))
    runtime = RuntimeSupervisor(Path(workspace), settings, agent, test_upstream_network=network)
    print('AICTRL_CHILD ' + runtime.identifier, flush=True)
    command = ('python', '-c', "from pathlib import Path; import time; Path('/workspace/child-ready').touch(); time.sleep(60)")
    if mode == 'exit':
        command = ('python', '-c', 'raise SystemExit(7)')
    elif mode == 'proxy-loss':
        command = ('python', '/workspace/loss.py')
    elif mode == 'startup-failure':
        settings.runtime.test_destinations = ()
    try:
        code, _ = runtime.run(command, capture_output=True)
    except RuntimeFailure:
        if mode != 'startup-failure':
            raise
        code = 2
    print(f'AICTRL_EXIT {code}', flush=True)
    raise SystemExit(code)


def main():
    name = 'aictrl-probe-' + uuid.uuid4().hex
    network, volume, target = name + '-upstream', name + '-state', name + '-target'
    fixture = PROJECT_ROOT / 'tests/fixtures/runtime_target.py'
    counters = Counter()

    class HostHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            counters[self.path] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'HOST_SYNTHETIC_OK')

        def log_message(self, *args):
            pass

    host = ThreadingHTTPServer(('0.0.0.0', 0), HostHandler)
    threading.Thread(target=host.serve_forever, daemon=True).start()
    current = None
    try:
        docker(['network', 'create', network])
        docker(['volume', 'create', volume])
        docker(['run', '--detach', '--name', target, '--network', network, '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges:true', '--user', '501:501',
                '--mount', f'type=bind,src={fixture},dst=/target.py,readonly', '--entrypoint', 'python',
                'aictrl-base:py3.12.15-t02', '/target.py'])
        info = json.loads(docker(['inspect', target]).stdout)[0]
        target_ip = info['NetworkSettings']['Networks'][network]['IPAddress']
        for _ in range(30):
            ready = docker(['exec', target, 'python', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=1)"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(.1)
        assert ready.returncode == 0, 'Synthetic backend did not start'
        with tempfile.TemporaryDirectory(prefix='aictrl-runtime-probes-') as directory:
            workspace = Path(directory)
            (workspace / 'probe.py').write_text((PROJECT_ROOT / 'tests/fixtures/runtime_probe.py').read_text())
            for iteration in range(2):
                (workspace / 'input.txt').write_text('host workspace\n')
                settings, agent = settings_and_agent(volume, target_ip)
                current = RuntimeSupervisor(workspace, settings, agent, test_upstream_network=network)
                current.prepare()
                internal = current.internal_network
                gateway = json.loads(docker(['network', 'inspect', internal]).stdout)[0]['IPAM']['Config'][0]['Gateway']
                positive = f"import urllib.request; assert urllib.request.urlopen('http://{gateway}:{host.server_port}/positive',timeout=2).status==200"
                assert docker(['exec', target, 'python', '-c', positive], check=False).returncode == 0, 'Host fixture is not live'
                manifest = json.loads(current.manifest.read_text())
                manifest['services']['sibling'] = {
                    'profiles': ['runtime'], 'image': 'aictrl-base:py3.12.15-t02',
                    'entrypoint': ['python', '/target.py'], 'user': '501:501', 'cap_drop': ['ALL'],
                    'security_opt': ['no-new-privileges:true'], 'networks': ['agent-internal'],
                    'labels': {'io.aictrl.session': current.identifier, 'io.aictrl.managed': 'true'},
                    'volumes': [{'type': 'bind', 'source': str(fixture), 'target': '/target.py', 'read_only': True}],
                }
                current.manifest.write_text(json.dumps(manifest))
                docker([*current.compose, 'up', '--detach', 'sibling'])
                sibling_id = docker([*current.compose, 'ps', '--quiet', 'sibling']).stdout.strip()
                sibling_ip = json.loads(docker(['inspect', sibling_id]).stdout)[0]['NetworkSettings']['Networks'][internal]['IPAddress']
                assert docker(['exec', sibling_id, 'python', '-c', "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=2).status==200"]).returncode == 0
                manifest['services']['agent']['environment'].update({
                    'AICTRL_TEST_TARGET_IP': target_ip, 'AICTRL_TEST_SIBLING_IP': sibling_ip,
                    'AICTRL_TEST_HOST_IP': gateway, 'AICTRL_TEST_HOST_PORT': str(host.server_port),
                })
                current.manifest.write_text(json.dumps(manifest))
                code, output = current.run(('python', '/workspace/probe.py'), capture_output=True)
                lines = [line.removeprefix('AICTRL_PROBE ') for line in output.splitlines() if line.startswith('AICTRL_PROBE ')]
                if not lines:
                    print(output)
                    raise AssertionError('Native boundary probe did not produce results')
                checks = json.loads(lines[-1])
                for check, passed in checks.items():
                    print(f"{'PASS' if passed else 'FAIL'} {check}")
                assert code == 0 and all(checks.values()), 'Runtime boundary failed'
                assert current.session.identity.state == SessionState.TERMINATED
                assert (workspace / 'input.txt').read_text() == 'edited by agent\n'
                assert (workspace / 'created.txt').stat().st_uid == os.getuid()
                clean_session(current.identifier)
                current = None
                docker(['volume', 'inspect', volume])
                print(f'PASS normal cleanup and state preservation, run {iteration + 1}')
            counts = json.loads(docker(['exec', target, 'python', '-c', "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/counts').read().decode())"]).stdout)
            assert counts == {'/allowed': 2, '/tunnel': 2}, counts
            assert counters == {'/positive': 2}, counters
            print('PASS denied requests produced no upstream, host, or UDP hits')

            (workspace / 'loss.py').write_text('''import os, socket, time
from pathlib import Path
def blocked(host,port):
    try:
        with socket.create_connection((host,port),timeout=1): return False
    except OSError: return True
assert not blocked(os.environ['AICTRL_PROXY_IP'],8080)
Path('/workspace/child-ready').touch()
while not Path('/workspace/proxy-removed').exists(): time.sleep(.1)
assert blocked(os.environ['AICTRL_PROXY_IP'],8080)
assert blocked('1.1.1.1',443)
''')

            for mode, seconds, expected in [('timeout', 10, 124), ('interrupt', 60, 130), ('terminate', 60, 143), ('exit', 60, 7), ('proxy-loss', 60, 0), ('startup-failure', 8, 2)]:
                (workspace / 'child-ready').unlink(missing_ok=True)
                process = subprocess.Popen([sys.executable, __file__, '--child', str(workspace), volume, target_ip, network, str(seconds), mode],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                identifier = process.stdout.readline().strip().removeprefix('AICTRL_CHILD ')
                if mode in ('interrupt', 'terminate', 'proxy-loss'):
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        found = docker(['ps', '--filter', 'name=aictrl-' + identifier + '-agent', '--format', '{{.ID}}']).stdout.strip()
                        if found and (workspace / 'child-ready').exists():
                            break
                        time.sleep(.2)
                    else:
                        process.terminate()
                        raise AssertionError('Signal fixture did not start')
                    if mode == 'proxy-loss':
                        settings, agent = settings_and_agent(volume, target_ip)
                        competing = RuntimeSupervisor(workspace, settings, agent, test_upstream_network=network)
                        try:
                            try:
                                competing.prepare()
                            except Exception as error:
                                assert 'already in use' in str(error), str(error)
                            else:
                                raise AssertionError('Concurrent state use was permitted')
                        finally:
                            competing.close()
                        clean_session(competing.identifier)
                        print('PASS concurrent provider-state use rejected')
                        proxy_id = docker(['ps', '--filter', 'label=io.aictrl.session=' + identifier,
                                           '--filter', 'label=com.docker.compose.service=proxy', '--format', '{{.ID}}']).stdout.strip()
                        assert proxy_id
                        docker(['rm', '--force', proxy_id])
                        (workspace / 'proxy-removed').touch()
                    else:
                        os.kill(process.pid, signal.SIGINT if mode == 'interrupt' else signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=35)
                assert process.returncode == expected, (mode, process.returncode, stdout, stderr)
                clean_session(identifier)
                docker(['volume', 'inspect', volume])
                print(f'PASS {mode}: exit {expected}, no leaked resources, state preserved')
    finally:
        if current is not None:
            current.close()
        host.shutdown()
        host.server_close()
        docker(['rm', '--force', target], check=False)
        docker(['network', 'rm', network], check=False)
        docker(['volume', 'rm', volume], check=False)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        child()
    else:
        main()
