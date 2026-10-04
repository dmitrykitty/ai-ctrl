"""Actual Docker response proof, fixed secret input, zero external calls."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.policy.loader import load_policy
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import atomic, cleanup_checks, save_report, select_fixture


def case(mode: str, *, history: bool) -> dict:
    current = None
    stop = threading.Event()
    watcher = None
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix='aictrl-response-') as folder:
        root = Path(folder)
        project, workspace = root / 'control', root / 'workspace'
        (project / 'config').mkdir(parents=True)
        (project / 'docker').mkdir()
        workspace.mkdir()
        for name in ('config/policy.yaml', 'config/threat-feed.json', 'docker/compose.yaml'):
            shutil.copy(PROJECT_ROOT / name, project / name)
        policy = load_policy(project / 'config/policy.yaml').model_dump(mode='json')
        policy['policy_version'] = 'response-' + mode
        policy['risk']['thresholds'] = {'medium': 1, 'high': 2, 'critical': 100 if mode == 'restrict' else 3}
        atomic(project / 'config/policy.yaml', policy)
        settings = load_config(PROJECT_ROOT)
        settings.limits.wall_time_seconds = 90
        control = PROJECT_ROOT if history else project
        try:
            current = RuntimeSupervisor(workspace, settings, DemoAgentAdapter(settings.demo.image), control,
                                        session_kind='offline-demo' if history else 'verification')
            current.prepare()
            select_fixture(current, project / 'config', semantic=False)
            manifest = json.loads(current.manifest.read_text())
            manifest['services']['agent']['environment']['AICTRL_RESPONSE_CASE'] = mode
            current.manifest.write_text(json.dumps(manifest))
            ephemeral = Path(current.directory.name)
            session = current.session.identity.session_id
            store = EventStore(control / '.aictrl/audit/events.sqlite3')
            checks['no_provider_state_or_lease'] = current.lock_id is None and 'provider-state' not in manifest['volumes']
            checks['agent_has_no_config_audit_socket'] = len(manifest['services']['agent']['volumes']) == 2 and all(
                'docker.sock' not in str(item) and '/config' not in str(item) and '/audit' not in str(item)
                for item in manifest['services']['agent']['volumes'])
            if mode == 'restrict':
                def watch():
                    while not stop.wait(0.1):
                        try:
                            owned = current._owned(current.session.container_name)
                            result = docker(['inspect', '--format', '{{json .NetworkSettings.Networks}}', current.session.container_name],
                                            check=False, timeout=3)
                            if owned and result.returncode == 0 and json.loads(result.stdout) == {}:
                                checks['real_owned_network_disconnect'] = True
                                (workspace / 'response-disconnected').write_text('confirmed\n')
                                return
                        except Exception:
                            checks['real_owned_network_disconnect'] = False
                            return
                watcher = threading.Thread(target=watch, daemon=True)
                watcher.start()
            started = time.perf_counter()
            code, output = current.run(('python', '/opt/aictrl/demo/agent/response.py'), capture_output=True)
            elapsed = time.perf_counter() - started
            stop.set()
            if watcher:
                watcher.join(timeout=4)
            checks['real_guard_block'] = 'AICTRL_RESPONSE_BLOCKED' in output and any(
                event.reason_code == 'guard.secret.detected' and event.action == 'BLOCK' for event in store.events(session))
            if mode == 'restrict':
                line = next((item for item in output.splitlines() if item.startswith('AICTRL_RESPONSE_CLIENT ')), None)
                checks['restricted_agent_cannot_reach_gateway'] = bool(line and json.loads(line.split(' ', 1)[1]).get('gateway_unreachable_after_restrict'))
                checks['restricted_workload_exits_zero'] = code == 0
            else:
                checks['real_owned_sigterm_bounded'] = current._response_termination and code in (143, 137) and elapsed < 20
            with sqlite3.connect(store.path) as db:
                rows = db.execute('SELECT response,response_completed_at,failures FROM alerts WHERE session_id=?', (str(session),)).fetchall()
                state = db.execute('SELECT state,ended_at FROM sessions WHERE session_id=?', (str(session),)).fetchone()
                stages = {row[0] for row in db.execute('SELECT stage FROM latency_samples WHERE session_id=?', (str(session),))}
            checks['one_matching_alert_completed_once'] = len(rows) == 1 and rows[0][0] == mode and rows[0][1] is not None and rows[0][2] == 0
            checks['durable_terminal_lifecycle'] = state is not None and state[0] == 'TERMINATED' and state[1] is not None
            checks['latency_recorded'] = {'total', 'deterministic_guards'} <= stages
            checks['ephemeral_removed'] = not ephemeral.exists()
            checks.update(cleanup_checks(current.identifier))
            checks['no_secret_or_identity_in_audit'] = all(value.encode() not in store.path.read_bytes() for value in (
                'AICTRL_SECRET_demo', current.session.identity.session_token.get_secret_value()))
            return {'response': mode, 'session_id': str(session), 'native_exit': code, 'seconds': round(elapsed, 3),
                    'checks': checks, 'passed': all(checks.values())}
        finally:
            stop.set()
            if watcher:
                watcher.join(timeout=4)
            if current:
                current.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true', help='Preserve only safe offline-demo evidence in the dashboard.')
    args = parser.parse_args()
    previous = os.environ.pop('AICTRL_JEV_API_KEY', None)
    try:
        results = [case(mode, history=args.history) for mode in ('restrict', 'terminate')]
        report = {'milestone': 'T08', 'mode': 'actual-docker-zero-provider-calls', 'cases': results,
                  'passed': all(item['passed'] for item in results)}
        save_report('t08-response-docker', report)
        print('AICTRL_T08_RESPONSE ' + json.dumps(report, sort_keys=True), flush=True)
        print('T08 HOST RESPONSE ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
        return 0 if report['passed'] else 1
    except Exception:
        print('T08 HOST RESPONSE FAIL: Docker, reporting or bounded workload unavailable.', flush=True)
        return 1
    finally:
        if previous is not None:
            os.environ['AICTRL_JEV_API_KEY'] = previous


if __name__ == '__main__':
    raise SystemExit(main())
