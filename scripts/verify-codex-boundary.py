"""Focused real Docker Codex qualification with a synthetic Responses origin."""
import json
import ipaddress
import shutil
import tempfile
import threading
import time
import uuid
import sys
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aictrl.adapters.base import RoutingMode
from aictrl.adapters.codex import CodexAdapter
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.contracts import AgentSession
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import docker, RuntimeFailure
from aictrl.runtime.codex_auth import codex_authenticated
from aictrl.runtime.auth import AuthenticationCheckError
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


def clean_session(identifier):
    for resource in ('container','network','volume'):
        command = ['ps','--all','--quiet'] if resource == 'container' else [resource,'ls','--quiet']
        assert not docker([*command,'--filter','label=io.aictrl.session='+identifier]).stdout.strip(), resource+' leaked'


def verify_leases():
    """Real provider lease names; no native client or provider-state contents."""
    checks, sessions = {}, []
    def runtime(adapter, settings):
        workspace = PROJECT_ROOT/'demo/project'
        identity = AgentSession(agent_id=adapter.name,adapter=adapter.name,user_id='local',profile_id='local',
                                workspace=str(workspace),protocol=adapter.protocol,billing_mode=adapter.billing_mode,
                                started_at=datetime.now(timezone.utc))
        selected = RuntimeSupervisor(workspace,settings,adapter.render_config(identity))
        sessions.append(selected)
        return selected
    settings = load_config(PROJECT_ROOT)
    try:
        first = runtime(CodexAdapter(settings.codex.image,RoutingMode.EGRESS_ONLY),settings)
        first.prepare()
        other = runtime(CodexAdapter(settings.codex.image,RoutingMode.EGRESS_ONLY),settings)
        try: other.prepare()
        except RuntimeFailure: checks['second_codex_refused']=True
        else: checks['second_codex_refused']=False
        other.close()
        checks['failed_contender_preserves_first_lease'] = first._owned(first.lock_id)
        try: codex_authenticated(settings.codex.image)
        except AuthenticationCheckError: checks['concurrent_authentication_refused']=True
        else: checks['concurrent_authentication_refused']=False
        claude = runtime(ClaudeAdapter(settings.claude.image,RoutingMode.EGRESS_ONLY),settings)
        claude.prepare()
        checks['claude_and_codex_independent_leases'] = first._owned(first.lock_id) and claude._owned(claude.lock_id) and first.lock_name != claude.lock_name
    finally:
        for selected in reversed(sessions):
            selected.close(); clean_session(selected.identifier)
    checks['all_prepared_sessions_cleaned'] = True
    checks['both_provider_volumes_preserved'] = all(docker(['volume','inspect',name],check=False).returncode == 0 for name in ('aictrl-claude-state','aictrl-codex-state'))
    print('AICTRL_T05_LEASES '+json.dumps(checks,sort_keys=True),flush=True)
    assert all(checks.values()), 'Provider lease qualification failed'


def main():
    name = 'aictrl-codex-probe-'+uuid.uuid4().hex
    network, volume, target = (name+suffix for suffix in ('-upstream','-state','-target'))
    checks, host_hits = {}, Counter()
    current = None
    class HostHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            host_hits[self.path] += 1
            self.send_response(200); self.end_headers(); self.wfile.write(b'PUBLIC_HOST_FIXTURE')
        def log_message(self,*args): pass
    host = ThreadingHTTPServer(('0.0.0.0',0),HostHandler)
    threading.Thread(target=host.serve_forever,daemon=True).start()
    try:
        docker(['network','create',network]); docker(['volume','create',volume])
        docker(['run','--detach','--name',target,'--network',network,'--cap-drop','ALL',
                '--security-opt','no-new-privileges:true','--user','501:501',
                '--mount',f'type=bind,src={PROJECT_ROOT / "tests/fixtures"},dst=/fixtures,readonly',
                '--entrypoint','python','aictrl-base:py3.12.15-t02','/fixtures/responses_target.py'])
        target_ip = docker(['inspect','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',target]).stdout.strip()
        for _ in range(30):
            ready = docker(['exec',target,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=1)"],check=False)
            if not ready.returncode: break
            time.sleep(.1)
        assert ready.returncode == 0, 'Synthetic Responses server failed to start'
        with tempfile.TemporaryDirectory(prefix='aictrl-codex-qualification-') as directory:
            root = Path(directory); project, workspace = root/'control', root/'workspace'
            (project/'config').mkdir(parents=True); (project/'docker').mkdir(); workspace.mkdir(mode=0o750)
            for file in ('config/policy.yaml','docker/compose.yaml'):
                shutil.copyfile(PROJECT_ROOT/file, project/file)
            shutil.copyfile(PROJECT_ROOT/'tests/fixtures/codex_probe.py',workspace/'codex_probe.py')
            (workspace/'input.txt').write_text('host workspace\n')
            before = workspace.stat()
            settings = load_config(PROJECT_ROOT); settings.limits.wall_time_seconds = 120
            session = AgentSession(agent_id='codex',adapter='codex',user_id='test',profile_id='local',workspace=str(workspace),
                                   protocol='RESPONSES',billing_mode='SUBSCRIPTION',started_at=datetime.now(timezone.utc))
            agent = CodexAdapter(settings.codex.image,RoutingMode.EGRESS_ONLY).render_config(session)
            agent.persistent_state_volume = volume
            current = RuntimeSupervisor(workspace,settings,agent,project,test_upstream_network=network)
            current.prepare()
            manifest = json.loads(current.manifest.read_text()); gateway = manifest['services']['gateway']
            gateway['environment'].update({'AICTRL_SYNTHETIC_IP':target_ip,'PYTHONPATH':'/opt/aictrl/src:/fixtures'})
            gateway['entrypoint'] = ['python','-m','uvicorn','gateway_factory:application','--factory','--host','0.0.0.0','--port','8000','--no-access-log','--log-level','warning']
            gateway['volumes'].append({'type':'bind','source':str(PROJECT_ROOT/'tests/fixtures'),'target':'/fixtures','read_only':True})
            manifest['services']['sibling'] = {'profiles':['runtime'],'image':'aictrl-base:py3.12.15-t02',
                'entrypoint':['python','/fixtures/runtime_target.py'],'user':'501:501','cap_drop':['ALL'],
                'security_opt':['no-new-privileges:true'],
                'networks':{'agent-internal':{'ipv4_address':str(ipaddress.ip_address(current.proxy_ip)+2)}},
                'labels':{'io.aictrl.session':current.identifier,'io.aictrl.managed':'true'},
                'volumes':[{'type':'bind','source':str(PROJECT_ROOT/'tests/fixtures'),'target':'/fixtures','read_only':True}]}
            current.manifest.write_text(json.dumps(manifest))
            startup = current._docker([*current.compose,'up','--detach','--wait','--force-recreate','gateway','sibling'],timeout=30,check=False)
            if startup.returncode:
                # No workload has run: these are fixture startup diagnostics.
                safe = startup.stderr.replace(current.session.identity.session_token.get_secret_value(),'[redacted]')
                print('Synthetic infrastructure startup failed: '+safe[-1600:],flush=True)
                gateway_id = docker([*current.compose,'ps','--all','--quiet','gateway'],check=False).stdout.strip()
                if gateway_id:
                    logs = docker(['logs',gateway_id],check=False)
                    safe = (logs.stdout+logs.stderr).replace(current.session.identity.session_token.get_secret_value(),'[redacted]')
                    print('Synthetic startup diagnostics: '+safe[-2200:],flush=True)
                raise RuntimeError('Synthetic infrastructure failed to start')
            gateway_id = docker([*current.compose,'ps','--quiet','gateway']).stdout.strip()
            metadata = json.loads(docker(['inspect','--format','{{json .HostConfig}}',gateway_id]).stdout)
            checks['gateway_cap_drop_readonly_no_socket'] = metadata['CapDrop'] == ['ALL'] and metadata['ReadonlyRootfs'] and not any('docker.sock' in mount for mount in (metadata.get('Binds') or []))
            mounts = json.loads(docker(['inspect','--format','{{json .Mounts}}',gateway_id]).stdout)
            checks['gateway_has_no_provider_state_or_workspace'] = not any(mount['Destination'] in ('/home/dev/.claude','/home/dev/.codex','/workspace','/home/mitmproxy/.mitmproxy') for mount in mounts)
            sibling_id = docker([*current.compose,'ps','--quiet','sibling']).stdout.strip()
            sibling_ip = docker(['inspect','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',sibling_id]).stdout.strip()
            assert not docker(['exec',sibling_id,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/counts',timeout=2)"]).returncode
            host_ip = json.loads(docker(['network','inspect',network]).stdout)[0]['IPAM']['Config'][0]['Gateway']
            manifest['services']['agent']['environment'].update({'AICTRL_TEST_TARGET_IP':target_ip,'AICTRL_TEST_SIBLING_IP':sibling_ip,
                    'AICTRL_TEST_HOST_IP':host_ip,'AICTRL_TEST_HOST_PORT':str(host.server_port)})
            current.manifest.write_text(json.dumps(manifest))
            checks['agent_only_workspace_state_public_ca_mounts'] = len(manifest['services']['agent']['volumes']) == 3 and manifest['services']['agent']['volumes'][1] == 'codex-state:/home/dev/.codex'
            identifier = current.identifier; session_id = current.session.identity.session_id
            code, output = current.run(('python','/workspace/codex_probe.py'),capture_output=True)
            line = next((line for line in output.splitlines() if line.startswith('AICTRL_CODEX_PROBE ')),None)
            assert line is not None, 'Safe Codex probe result absent; exit '+str(code)
            checks.update(json.loads(line.removeprefix('AICTRL_CODEX_PROBE ')))
            checks.pop('native_profile_rejected',None)
            clean_session(identifier); checks['cleanup_no_session_resources'] = True
            after = workspace.stat()
            checks['workspace_ownership_mode_unchanged'] = (before.st_uid,before.st_gid,before.st_mode) == (after.st_uid,after.st_gid,after.st_mode)
            events = EventStore(project/'.aictrl/audit/events.sqlite3').events(session_id)
            admissions = [event for event in events if event.action == 'ALLOW']
            completions = [event for event in events if event.reason_code == 'llm.upstream_completed']
            checks['durable_allow_completion_after_cleanup'] = len(admissions) >= 3 and {event.request_id for event in admissions} == {event.request_id for event in completions}
            checks['durable_blocks'] = sum(event.action == 'BLOCK' for event in events) >= 2
            checks['responses_event_attribution'] = all(event.agent_id == event.adapter == 'codex' and event.protocol == 'RESPONSES' and event.inspection_level == 'STRUCTURED' for event in events)
            checks['no_private_tokens_in_audit'] = all(value not in (project/'.aictrl/audit/events.sqlite3').read_bytes() for value in (b'synthetic-provider',b'synthetic-account',current.session.identity.session_token.get_secret_value().encode()))
            counts = json.loads(docker(['exec',target,'python','-c',"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/counts').read().decode())"]).stdout)
            checks['only_responses_upstream_hits'] = counts.get('responses',0) == len(admissions) and counts.get('tool_followup',0) == 1 and set(counts) <= {'responses','tool_followup'}
            checks['zero_host_bypass_hits'] = not host_hits
            checks['provider_fixture_state_preserved'] = docker(['volume','inspect',volume],check=False).returncode == 0
            print('AICTRL_T05_DOCKER '+json.dumps(checks,sort_keys=True),flush=True)
            assert code == 0 and all(checks.values()), 'Focused Codex Docker qualification failed'
    finally:
        if current is not None: current.close()
        docker(['rm','--force',target],check=False); docker(['volume','rm',volume],check=False); docker(['network','rm',network],check=False)
        host.shutdown(); host.server_close()


if __name__ == '__main__':
    if sys.argv[1:] == ['--leases-only']: verify_leases()
    elif not sys.argv[1:]: main()
    else: raise SystemExit('Supported option: --leases-only')
