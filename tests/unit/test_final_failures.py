"""Close remaining deterministic startup/backend failure qualification gaps."""

import asyncio
import shutil
import subprocess

import pytest

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.mcp.demo_backend import DemoMCPBackend
from aictrl.runtime.config import load_config
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT
from test_mcp import DemoSemanticFake, setup, with_sdk


def test_invalid_initial_policy_refuses_startup_before_container_launch(tmp_path, monkeypatch):
    project, workspace = tmp_path / 'control', tmp_path / 'workspace'
    (project / 'config').mkdir(parents=True); workspace.mkdir()
    (project / 'config/policy.yaml').write_text('private: PRIVATE_STARTUP_SENTINEL')
    shutil.copy(PROJECT_ROOT / 'config/threat-feed.json', project / 'config/threat-feed.json')
    settings = load_config(PROJECT_ROOT)
    runtime = RuntimeSupervisor(workspace, settings, DemoAgentAdapter(settings.demo.image), project)
    commands = []
    def ready(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, 'synthetic-ready', '')
    monkeypatch.setattr(runtime, '_docker', ready)
    try:
        with pytest.raises(ValueError) as error:
            runtime.prepare()
        assert 'PRIVATE_STARTUP_SENTINEL' not in str(error.value)
        assert not any('up' in args or 'run' in args or 'create' in args for args in commands)
        assert runtime.reporting is None and not runtime._prepared
    finally:
        runtime.close()
    assert not (project / '.aictrl/audit/events.sqlite3').exists()


def test_mcp_backend_failure_records_safe_failure_and_withholds_exception(tmp_path, caplog):
    class Unavailable(DemoMCPBackend):
        async def call_tool(self, name, arguments):
            raise RuntimeError('PRIVATE_BACKEND_FAILURE_SENTINEL')
    app, session, store, backend = setup(tmp_path, DemoSemanticFake(), Unavailable())
    async def proof(client):
        result = await client.call_tool('safe_lookup', {})
        assert result.is_error and 'mcp.backend_failed' in str(result)
        assert 'PRIVATE_BACKEND_FAILURE_SENTINEL' not in str(result)
    asyncio.run(with_sdk(app, proof))
    events = store.events(session.session_id)
    assert [event.reason_code for event in events] == ['mcp.policy.allowed', 'mcp.backend_failed']
    assert b'PRIVATE_BACKEND_FAILURE_SENTINEL' not in store.path.read_bytes()
    assert 'PRIVATE_BACKEND_FAILURE_SENTINEL' not in caplog.text
