"""Real Docker T03 qualification; synthetic upstream is test-only injection.

Uses production supervisor, images, firewall, proxy, native forwarding, policy
and SQLite. Does not inspect or mount production provider authentication.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import TestDestination, load_config
from aictrl.runtime.docker import docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


def clean_session(identifier):
    for resource in ('container', 'network', 'volume'):
        args = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        assert not docker([*args, '--filter', 'label=io.aictrl.session=' + identifier]).stdout.strip(), resource + ' leaked'


def main():
    name = 'aictrl-gateway-probe-' + uuid.uuid4().hex
    network, volume, target, sibling = (name + suffix for suffix in ('-upstream', '-state', '-target', '-sibling'))
    counters = Counter()
    checks = {}
    current = None

    class HostHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            counters[self.path] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'SYNTHETIC_HOST')
        def log_message(self, *args):
            pass

    host = ThreadingHTTPServer(('0.0.0.0', 0), HostHandler)
    threading.Thread(target=host.serve_forever, daemon=True).start()
    try:
        docker(['network', 'create', network])
        docker(['volume', 'create', volume])
        docker(['run', '--detach', '--name', target, '--network', network, '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges:true', '--user', '501:501',
                '--mount', f'type=bind,src={PROJECT_ROOT / "tests/fixtures"},dst=/fixtures,readonly',
                '--entrypoint', 'python', 'aictrl-base:py3.12.15-t02', '/fixtures/gateway_target.py'])
        target_ip = docker(['inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', target]).stdout.strip()
        for _ in range(30):
            ready = docker(['exec', target, 'python', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=1)"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(.1)
        assert ready.returncode == 0, 'Synthetic backend startup failed'
        with tempfile.TemporaryDirectory(prefix='aictrl-gateway-qualification-') as directory:
            root = Path(directory)
            project, workspace = root / 'control', root / 'workspace'
            (project / 'config').mkdir(parents=True)
            (project / 'docker').mkdir()
            workspace.mkdir()
            for file in ('config/policy.yaml', 'config/threat-feed.json', 'docker/compose.yaml'):
                shutil.copyfile(PROJECT_ROOT / file, project / file)
            for file in ('gateway_probe.py', 'runtime_probe.py'):
                shutil.copyfile(PROJECT_ROOT / 'tests/fixtures' / file, workspace / file)
            (workspace / 'input.txt').write_text('host workspace\n')

            def runtime():
                settings = load_config(PROJECT_ROOT)
                settings.runtime.test_destinations = (TestDestination(host='allowed.test', port=8081, connect_ip=target_ip),)
                settings.limits.wall_time_seconds = 90
                agent = ClaudeAdapter(settings.claude.image, settings.runtime.routing_mode)
                agent.persistent_state_volume = volume
                return RuntimeSupervisor(workspace, settings, agent, project, test_upstream_network=network)

            current = runtime()
            current.prepare()
            manifest = json.loads(current.manifest.read_text())
            gateway = manifest['services']['gateway']
            gateway['environment']['AICTRL_SYNTHETIC_IP'] = target_ip
            gateway['environment']['PYTHONPATH'] = '/opt/aictrl/src:/fixtures'
            gateway['entrypoint'] = ['python', '-m', 'uvicorn', 'gateway_factory:application', '--factory', '--host', '0.0.0.0', '--port', '8000', '--no-access-log', '--log-level', 'warning']
            gateway['volumes'].append({'type': 'bind', 'source': str(PROJECT_ROOT / 'tests/fixtures'), 'target': '/fixtures', 'read_only': True})
            # Only this qualification replaces the transport; production origin
            # remains fixed, and there is no production override setting.
            current.manifest.write_text(json.dumps(manifest))
            current._docker([*current.compose, 'up', '--detach', '--wait', '--force-recreate', 'gateway'], timeout=30)
            gateway_id = docker([*current.compose, 'ps', '--quiet', 'gateway']).stdout.strip()
            metadata = json.loads(docker(['inspect', '--format', '{{json .HostConfig}}', gateway_id]).stdout)
            checks['gateway_cap_drop_readonly_no_socket'] = metadata['CapDrop'] == ['ALL'] and metadata['ReadonlyRootfs'] and not any('docker.sock' in mount for mount in (metadata.get('Binds') or []))
            checks['gateway_process_nonroot_no_caps'] = docker(['exec', gateway_id, 'python', '-c', "import os; from pathlib import Path; s=dict(x.split(':',1) for x in Path('/proc/self/status').read_text().splitlines() if ':' in x); assert os.getuid()!=0 and int(s['CapEff'],16)==0 and s['NoNewPrivs'].strip()=='1'"]).returncode == 0
            mounts = json.loads(docker(['inspect', '--format', '{{json .Mounts}}', gateway_id]).stdout)
            checks['gateway_has_no_workspace_state_or_ca'] = not any(mount['Destination'] in ('/workspace', '/home/dev/.claude', '/home/mitmproxy/.mitmproxy', '/etc/aictrl/proxy-ca.pem') for mount in mounts)
            manifest['services']['sibling'] = {
                'profiles': ['runtime'], 'image': 'aictrl-base:py3.12.15-t02',
                'entrypoint': ['python', '/target.py'], 'user': '501:501', 'cap_drop': ['ALL'],
                'security_opt': ['no-new-privileges:true'], 'networks': ['agent-internal'],
                'labels': {'io.aictrl.session': current.identifier, 'io.aictrl.managed': 'true'},
                'volumes': [{'type': 'bind', 'source': str(PROJECT_ROOT / 'tests/fixtures/runtime_target.py'), 'target': '/target.py', 'read_only': True}],
            }
            current.manifest.write_text(json.dumps(manifest))
            docker([*current.compose, 'up', '--detach', 'sibling'])
            sibling_id = docker([*current.compose, 'ps', '--quiet', 'sibling']).stdout.strip()
            sibling_ip = docker(['inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', sibling_id]).stdout.strip()
            assert docker(['exec', sibling_id, 'python', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=2)"]).returncode == 0
            host_ip = json.loads(docker(['network', 'inspect', network]).stdout)[0]['IPAM']['Config'][0]['Gateway']
            manifest['services']['agent']['environment'].update({'AICTRL_TEST_TARGET_IP': target_ip, 'AICTRL_TEST_SIBLING_IP': sibling_ip,
                                                               'AICTRL_TEST_HOST_IP': host_ip, 'AICTRL_TEST_HOST_PORT': str(host.server_port)})
            current.manifest.write_text(json.dumps(manifest))
            identifier = current.identifier
            session_id = current.session.identity.session_id
            code, output = current.run(('python', '/workspace/gateway_probe.py'), capture_output=True)
            for prefix in ('AICTRL_GATEWAY_PROBE ', 'AICTRL_PROBE '):
                line = next((line for line in output.splitlines() if line.startswith(prefix)), None)
                assert line is not None, 'Agent qualification output absent; exit ' + str(code)
                checks.update(json.loads(line[len(prefix):]))
            assert code == 0 and all(checks.values()), 'Agent boundary qualification failed'
            clean_session(identifier)
            print('PASS native gateway forwarding, proxy partition, runtime boundary and cleanup', flush=True)
            audit_path = project / '.aictrl/audit/events.sqlite3'
            events = EventStore(audit_path).events(session_id)
            checks['durable_admission_completion_block_after_cleanup'] = Counter(event.action for event in events) == {'ALLOW': 2, 'AUDIT': 2, 'BLOCK': 2}
            checks['event_attribution_structured'] = all(event.agent_id == 'claude' and event.channel == 'LLM' and event.inspection_level == 'STRUCTURED' for event in events)
            raw = audit_path.read_bytes()
            checks['no_prompt_or_provider_credential_in_audit'] = b'synthetic-private-prompt' not in raw and b'synthetic-provider' not in raw
            counts = json.loads(docker(['exec', target, 'python', '-c', "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/counts').read().decode())"]).stdout)
            checks['only_allowed_upstream_hits'] = counts == {'/v1/messages?beta=true&x=a%2Fb': 1, '/v1/messages/count_tokens?beta=true': 1, '/allowed': 1, '/tunnel': 1}
            checks['zero_host_bypass_hits'] = not counters
            print('PASS durable attributable events and zero denied upstream hits', flush=True)

            # A stopped required gateway prevents the workload from starting;
            # the existing host deadline terminates preparation and cleans up.
            current = runtime()
            current.prepare()
            identifier = current.identifier
            gateway_id = docker([*current.compose, 'ps', '--quiet', 'gateway']).stdout.strip()
            docker(['stop', '--time', '1', gateway_id])
            current._deadline = time.monotonic() + 5
            code, _ = current.run(('python', '-c', "from pathlib import Path; Path('/workspace/forbidden-start').touch()"), capture_output=True)
            checks['gateway_unavailable_prevents_agent_start'] = code == 124 and not (workspace / 'forbidden-start').exists()
            clean_session(identifier)
            checks['session_cleanup_preserves_durable_store'] = audit_path.is_file() and len(EventStore(audit_path).events(session_id)) == 6
            checks['fixture_provider_state_preserved'] = docker(['volume', 'inspect', volume], check=False).returncode == 0
            assert all(checks.values()), 'T03 Docker qualification failed'
            print('AICTRL_T03_DOCKER_PASS ' + json.dumps(checks, sort_keys=True), flush=True)
    finally:
        if current is not None:
            current.close()
        docker(['rm', '--force', target, sibling], check=False)
        docker(['volume', 'rm', volume], check=False)
        docker(['network', 'rm', network], check=False)
        host.shutdown()
        host.server_close()


if __name__ == '__main__':
    main()
