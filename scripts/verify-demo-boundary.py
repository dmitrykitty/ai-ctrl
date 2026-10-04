"""Focused actual Docker demo qualification with an explicit semantic fake."""

import json
import argparse
import os
import shutil
import tempfile
from pathlib import Path

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import notify_policy, select_fixture


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--history',action='store_true',help='Keep safe explicitly offline demo history in the dashboard.')
    args=parser.parse_args()
    current=None
    previous_key=os.environ.get('AICTRL_JEV_API_KEY')
    os.environ['AICTRL_JEV_API_KEY']='synthetic_jev_key_boundary_only'
    try:
        with tempfile.TemporaryDirectory(prefix='aictrl-demo-qualification-') as directory:
            root=Path(directory)
            project,workspace=root/'control',root/'workspace'
            (project/'config').mkdir(parents=True)
            (project/'docker').mkdir()
            workspace.mkdir()
            for file in ('config/policy.yaml','config/threat-feed.json','docker/compose.yaml'):
                shutil.copyfile(PROJECT_ROOT/file,project/file)
            notify_policy(project/'config/policy.yaml')
            shutil.copyfile(PROJECT_ROOT/'tests/fixtures/demo_probe.py',workspace/'demo_probe.py')
            settings=load_config(PROJECT_ROOT)
            settings.limits.wall_time_seconds=90
            control=PROJECT_ROOT if args.history else project
            current=RuntimeSupervisor(workspace,settings,DemoAgentAdapter(settings.demo.image),control,
                                      session_kind='offline-demo' if args.history else 'verification')
            current.prepare()
            session=current.session.identity.session_id
            identifier=current.identifier
            ephemeral=Path(current.directory.name)
            manifest=json.loads(current.manifest.read_text())
            checks={'no_provider_volume_or_lease':'provider-state' not in manifest['volumes'] and current.lock_id is None,
                    'agent_two_mounts':len(manifest['services']['agent']['volumes'])==2}
            select_fixture(current,project/'config')
            gateway_id=docker([*current.compose,'ps','--quiet','gateway']).stdout.strip()
            gateway_mounts=json.loads(docker(['inspect','--format','{{json .Mounts}}',gateway_id]).stdout)
            secret=next(mount for mount in gateway_mounts if mount['Destination']=='/run/secrets/aictrl/jev_api_key')
            checks['gateway_key_readonly']=secret['RW'] is False and (ephemeral/'jev_api_key').stat().st_mode&0o777==0o400
            proxy_id=docker([*current.compose,'ps','--quiet','proxy']).stdout.strip()
            proxy_mounts=json.loads(docker(['inspect','--format','{{json .Mounts}}',proxy_id]).stdout)
            checks['proxy_has_no_semantic_secret']=not any('jev_api_key' in mount['Destination'] for mount in proxy_mounts)
            code,output=current.run(('python','/workspace/demo_probe.py'),capture_output=True)
            boundary=next((line for line in output.splitlines() if line.startswith('AICTRL_DEMO_BOUNDARY ')),None)
            assert boundary is not None,'Demo boundary output unavailable.'
            checks.update(json.loads(boundary.split(' ',1)[1]))
            checks['official_sdk_attack_demo_pass']=code==0 and 'T07 GUARDS DEMO PASS' in output
            checks['ephemeral_key_and_identity_removed']=not ephemeral.exists()
            for resource in ('container','network','volume'):
                args=['ps','--all','--quiet'] if resource=='container' else [resource,'ls','--quiet']
                checks['cleanup_'+resource]=not docker([*args,'--filter','label=io.aictrl.session='+identifier]).stdout.strip()
            events=EventStore(control/'.aictrl/audit/events.sqlite3').events(session)
            checks['durable_mcp_allow_redact_block']=all(any(event.action==action for event in events) for action in ('ALLOW','REDACT','BLOCK'))
            checks['mcp_attribution']=all(event.agent_id==event.adapter=='demo-agent' and event.channel=='MCP' and event.protocol is None for event in events)
            raw=(control/'.aictrl/audit/events.sqlite3').read_bytes()
            checks['audit_has_no_raw_content']=all(secret not in raw for secret in (b'AICTRL_SECRET_demo',b'user@example.com',b'Ignore previous instructions',b'AICTRL_PRIVATE_MEMORY_SYNTHETIC',b'synthetic_jev_key_boundary_only'))
            print('T07 Docker guards/boundary qualification: explicit offline semantic fixture; zero live Jev calls.',flush=True)
            print('AICTRL_T07_DEMO_DOCKER '+json.dumps(checks,sort_keys=True),flush=True)
            assert all(checks.values()),'Demo Docker qualification failed.'
    finally:
        if current is not None: current.close()
        if previous_key is None: os.environ.pop('AICTRL_JEV_API_KEY',None)
        else: os.environ['AICTRL_JEV_API_KEY']=previous_key


if __name__=='__main__': main()
