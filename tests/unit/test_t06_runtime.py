import json
import subprocess
from pathlib import Path

import pytest

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.runtime.compose import validate_provider_state
from aictrl.runtime.config import load_config
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT
from aictrl.guards.jev import load_key


def runtime(tmp_path,monkeypatch,*,demo=False):
    project=tmp_path/'control'
    (project/'config').mkdir(parents=True)
    (project/'docker').mkdir()
    workspace=tmp_path/'workspace'
    workspace.mkdir()
    for file in ('config/policy.yaml','config/threat-feed.json','docker/compose.yaml'):
        (project/file).write_bytes((PROJECT_ROOT/file).read_bytes())
    settings=load_config(PROJECT_ROOT)
    if demo: adapter=DemoAgentAdapter(settings.demo.image)
    else:
        from aictrl.adapters.claude import ClaudeAdapter
        adapter=ClaudeAdapter(settings.claude.image)
    current=RuntimeSupervisor(workspace,settings,adapter,project)
    commands=[]
    def docker(arguments,**kwargs):
        commands.append(arguments)
        output=current.identifier if arguments[0] in ('create','inspect') else ''
        return subprocess.CompletedProcess(arguments,0,output,'')
    monkeypatch.setattr('aictrl.runtime.supervisor.docker',docker)
    return current,commands


def test_trusted_stateless_runtime_has_identity_no_provider_mount_or_lease(tmp_path,monkeypatch):
    monkeypatch.delenv('AICTRL_JEV_API_KEY',raising=False)
    current,commands=runtime(tmp_path,monkeypatch,demo=True)
    directory=Path(current.directory.name)
    try:
        current.prepare()
        manifest=json.loads(current.manifest.read_text())
        assert 'provider-state' not in manifest['volumes'] and len(manifest['services']['agent']['volumes'])==2
        assert current.lock_id is None and current.lock_name is None
        assert not any(args[0]=='create' or 'volume=' in ' '.join(args) for args in commands)
        record=json.loads((directory/'session.json').read_text())
        assert record['protocol'] is None and record['session_id']==str(current.session.identity.session_id)
        assert manifest['services']['agent']['environment']['AICTRL_SESSION_TOKEN']==record['session_token']
        assert manifest['services']['agent']['networks']==['agent-internal']
    finally: current.close()
    assert not directory.exists()


@pytest.mark.parametrize('demo',[False,True])
def test_semantic_key_only_gateway_file_never_compose_env_audit_or_agent(tmp_path,monkeypatch,demo):
    value='synthetic_jev_key_boundary_fixture'
    monkeypatch.setenv('AICTRL_JEV_API_KEY',value)
    current,commands=runtime(tmp_path,monkeypatch,demo=demo)
    directory=Path(current.directory.name)
    try:
        current.prepare()
        path=directory/'jev_api_key'
        assert path.stat().st_mode&0o777==0o400 and load_key(path).get_secret_value()==value
        manifest=json.loads(current.manifest.read_text())
        assert value not in current.manifest.read_text() and value not in repr(current.agent)
        for name in ('agent','proxy'):
            assert str(path) not in str(manifest['services'][name])
            assert not any('JEV' in key for key in manifest['services'][name]['environment'])
        mount=manifest['services']['gateway']['volumes'][-1]
        assert mount['source']==str(path) and mount['target']=='/run/secrets/aictrl/jev_api_key' and mount['read_only']
        assert value not in json.dumps(manifest['services']['gateway']['environment'])
    finally: current.close()
    assert not path.exists()


def test_stateless_flag_cannot_select_host_or_provider_state():
    validate_provider_state(None,None,stateless=True)
    for volume,mount in (('/host/secrets','/home/dev/.provider'),('provider','/home/dev/.provider'),(None,'/host')):
        with pytest.raises(ValueError): validate_provider_state(volume,mount,stateless=True)
    with pytest.raises(ValueError): validate_provider_state(None,None)
