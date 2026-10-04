"""Actual Docker/MCP/host CLI/reload proof; --live uses production Jev.

Default is an explicitly injected offline semantic fixture, never a fallback.
Host approval is limited to the task-authorized exact counter-only demo request.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.contracts import ControlRequest, PolicyContext
from aictrl.governance.approvals import request_digest
from aictrl.governance.store import GovernanceStore
from aictrl.reporting.store import EventStore
from aictrl.policy.loader import load_policy
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import select_fixture


def atomic(path: Path, value: object) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def numeric_counters(store):
    return [(str(item.budget_id), item.scope, item.scope_id, item.dimension,
             item.window_start.isoformat(), item.window_end.isoformat(), item.used, item.reserved) for item in store.budgets()]


def host_cli(project, *args):
    result = subprocess.run([str(PROJECT_ROOT / '.venv/bin/aictrl'), *args, '--project', str(project)],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError('Explicit host approval CLI failed.')
    print(result.stdout.strip(), flush=True)  # CLI emits safe identifiers/states only


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Use production factory and real external Jev.')
    parser.add_argument('--key-file', type=Path, help='Private host .env input, used only with --live; never deleted by this verifier.')
    parser.add_argument('--history', action='store_true', help='Keep safe demo evidence in the dashboard; production config remains unchanged.')
    args = parser.parse_args()
    previous_key = os.environ.get('AICTRL_JEV_API_KEY')
    current = None
    stop = threading.Event()
    coordinator = None
    checks = {}
    coordination_failed = threading.Event()
    try:
        if args.live:
            if args.key_file:
                path = args.key_file
                if (path.is_symlink() or path.stat().st_mode & 0o777 != 0o600
                        or path.parent.stat().st_mode & 0o777 != 0o700):
                    raise RuntimeError('Private Jev input permissions invalid.')
                text = path.read_text().strip()
                if not text.startswith('AICTRL_JEV_API_KEY=') or '\n' in text:
                    raise RuntimeError('Private Jev input invalid.')
                value = text.split('=', 1)[1].strip().strip('\"\'')
                if not value:
                    raise RuntimeError('Jev key unavailable.')
                os.environ['AICTRL_JEV_API_KEY'] = value
            if not os.environ.get('AICTRL_JEV_API_KEY'):
                raise RuntimeError('Production demo needs a securely supplied host Jev key.')
        else:
            os.environ['AICTRL_JEV_API_KEY'] = 'synthetic_t07_gateway_mount_key'
        print('T07 governance Docker demo: ' + ('production gateway + live Jev.' if args.live else 'explicit offline semantic fixture; zero live Jev calls.'), flush=True)
        with tempfile.TemporaryDirectory(prefix='aictrl-t07-governance-') as directory:
            root = Path(directory)
            project, workspace = root / 'control', root / 'workspace'
            (project / 'config').mkdir(parents=True)
            (project / 'docker').mkdir()
            workspace.mkdir()
            for file in ('config/project.yaml', 'config/policy.yaml', 'config/threat-feed.json', 'docker/compose.yaml'):
                shutil.copyfile(PROJECT_ROOT / file, project / file)
            original = load_policy(project / 'config/policy.yaml').model_dump(mode='json')
            original['response'].update(medium='notify', high='notify', critical='notify')
            initial = deepcopy(original)
            initial['policy_version'] = 't07-demo'
            atomic(project / 'config/policy.yaml', initial)
            settings = load_config(PROJECT_ROOT)
            settings.limits.wall_time_seconds = 120
            control = PROJECT_ROOT if args.history else project
            current = RuntimeSupervisor(workspace, settings, DemoAgentAdapter(settings.demo.image), control,
                                        session_kind=('demo' if args.live else 'offline-demo') if args.history else 'verification')
            current.prepare()
            manifest = json.loads(current.manifest.read_text())
            checks['stateless_no_provider_lease'] = current.lock_id is None and 'provider-state' not in manifest['volumes']
            checks['config_only_gateway_readonly'] = all('/config' not in str(manifest['services'][name]['volumes']) for name in ('agent', 'proxy')) and manifest['services']['gateway']['volumes'][1]['read_only']
            select_fixture(current, project / 'config', semantic=not args.live)
            gateway_id = docker([*current.compose, 'ps', '--quiet', 'gateway']).stdout.strip()
            started = docker(['inspect', '--format', '{{.State.StartedAt}}/{{.RestartCount}}', gateway_id]).stdout.strip()
            identity = current.session.identity
            store = GovernanceStore(control / '.aictrl/audit/events.sqlite3')
            audit = EventStore(store.path)
            context = PolicyContext(session_id=identity.session_id, agent_id='demo-agent', user_id=identity.user_id,
                                    profile_id=identity.profile_id, policy_version='t07-demo')
            request = ControlRequest(session_id=identity.session_id, channel='MCP', direction='OUTBOUND', protocol=None,
                                     inspection_level='STRUCTURED', target_id='demo-mcp', operation_id='tool.destructive_delete_all', created_at=datetime.now(timezone.utc))
            expected_digest = request_digest(context, request, {'confirmation': 't07-demo'})
            ephemeral = Path(current.directory.name)
            checkpoint = workspace / 't07-checkpoint.json'
            def coordinate():
                completed = set()
                before = None
                deadline = time.monotonic() + 90
                try:
                    while not stop.is_set() and time.monotonic() < deadline:
                        try:
                            phase = json.loads(checkpoint.read_text()).get('phase')
                        except (OSError, ValueError):
                            stop.wait(0.05)
                            continue
                        if phase in completed:
                            stop.wait(0.05)
                            continue
                        if phase == 'pending':
                            # Do not approve arbitrary agent-supplied IDs or operations.
                            records = [record for record in store.approvals(identity.session_id)
                                       if record.operation_id == 'tool.destructive_delete_all'
                                       and record.approval.request_digest == expected_digest
                                       and record.approval.policy_version == 't07-demo'
                                       and record.approval.state == 'PENDING']
                            if len(records) != 1:
                                raise RuntimeError('Exact authorized synthetic request unavailable.')
                            record = records[0]
                            host_cli(control, 'approvals', '--session', str(identity.session_id))
                            print('Host CLI: aictrl approve ' + str(record.approval.approval_id), flush=True)
                            host_cli(control, 'approve', str(record.approval.approval_id))
                            checks['explicit_host_cli_approved_exact_request'] = True
                        elif phase == 'approval_complete':
                            states = [item for item in store.budgets() if item.dimension == 'tool_calls' and item.scope_id == str(identity.session_id) and item.window_start.timestamp() != 0]
                            if len(states) != 1 or states[0].used != 3 or states[0].reserved:
                                raise RuntimeError('Expected tool accounting unavailable.')
                            before = [row for row in numeric_counters(store) if row[2] == str(identity.session_id)]
                            candidate = deepcopy(original)
                            candidate['policy_version'] = 't07-demo-budget'
                            for rule in candidate['governance']['budgets']:
                                if rule['id'] == 'session.tool-calls':
                                    rule['limit'] = 3
                            atomic(project / 'config/policy.yaml', candidate)
                        elif phase == 'budget_complete':
                            checks['failed_multi_budget_no_partial_step'] = before == [row for row in numeric_counters(store) if row[2] == str(identity.session_id)]
                            candidate = deepcopy(original)
                            candidate['policy_version'] = 't07-demo-block'
                            rule = deepcopy(candidate['agents']['demo-agent']['rules'][-1])
                            rule.update(id='demo.reload-block', operations=['tool.safe_lookup'], action='BLOCK')
                            candidate['agents']['demo-agent']['rules'].append(rule)
                            atomic(project / 'config/policy.yaml', candidate)
                        elif phase == 'policy_complete':
                            candidate = deepcopy(original)
                            candidate['policy_version'] = 't07-demo-feed'
                            atomic(project / 'config/policy.yaml', candidate)
                            atomic(project / 'config/threat-feed.json', {'schema_version': 1, 'feed_version': 't07-demo-threat', 'signatures': [{
                                'signature_id': 'governance-demo', 'revision': 1, 'kind': 'literal', 'pattern': 'AICTRL_GOVERNANCE_FEED_BLOCK',
                                'action': 'BLOCK', 'severity': 'HIGH', 'channels': ['MCP'], 'enabled': True}]})
                        elif phase == 'feed_complete':
                            atomic(project / 'config/policy.yaml', {'unknown': 'invalid candidate'})
                            atomic(project / 'config/threat-feed.json', {'schema_version': 1, 'feed_version': 'invalid', 'signatures': [{
                                'signature_id': 'bad', 'revision': 1, 'kind': 'regex', 'pattern': '(x+)+',
                                'action': 'BLOCK', 'severity': 'HIGH', 'channels': ['MCP'], 'enabled': True}]})
                        elif phase == 'invalid_complete':
                            candidate = deepcopy(original)
                            candidate['policy_version'] = 't07-demo-runaway'
                            candidate['governance']['runaway']['max_tool_calls'] = 4
                            atomic(project / 'config/policy.yaml', candidate)
                        elif phase == 'done':
                            checks['reload_without_gateway_restart'] = started == docker(['inspect', '--format', '{{.State.StartedAt}}/{{.RestartCount}}', gateway_id]).stdout.strip()
                            (workspace / 't07-host-completed').write_text('complete\n')
                            return
                        completed.add(phase)
                    if not stop.is_set():
                        raise RuntimeError('Host coordination deadline exceeded.')
                except Exception:
                    coordination_failed.set()
            coordinator = threading.Thread(target=coordinate, daemon=True)
            coordinator.start()
            code, output = current.run(('python', '/opt/aictrl/demo/agent/governance.py'), capture_output=True)
            coordinator.join(timeout=2)
            stop.set()
            coordinator.join(timeout=1)
            checks['host_coordination_completed'] = not coordination_failed.is_set() and 'reload_without_gateway_restart' in checks
            line = next((line for line in output.splitlines() if line.startswith('AICTRL_T07_GOVERNANCE_CLIENT ')), None)
            checks['scripted_sdk_demo_pass'] = code == 0 and 'T07 GOVERNANCE DEMO PASS' in output and line is not None
            if line:
                checks.update(json.loads(line.split(' ', 1)[1]))
            events = audit.events(identity.session_id)
            checks['durable_approval_budget_feed_runaway_events'] = all(any(event.reason_code == reason for event in events) for reason in (
                'governance.approval.required', 'governance.approval.consumed', 'governance.budget.tool_calls_exceeded',
                'guard.threat_feed.detected', 'governance.runaway.tool_calls_exceeded'))
            checks['backend_completed_exactly_four_calls'] = sum(event.reason_code == 'mcp.backend_completed' for event in events) == 4
            checks['approval_one_consumed_other_pending'] = sorted(record.approval.state.value for record in store.approvals(identity.session_id)) == ['CONSUMED', 'PENDING']
            raw = store.path.read_bytes()
            checks['no_raw_argument_feed_marker_key_or_identity_in_sqlite'] = all(value.encode() not in raw for value in (
                'AICTRL_GOVERNANCE_FEED_BLOCK', os.environ['AICTRL_JEV_API_KEY'], identity.session_token.get_secret_value(), '"confirmation"'))
            checks['ephemeral_identity_key_removed'] = not ephemeral.exists()
            for resource in ('container', 'network', 'volume'):
                command = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
                checks['cleanup_' + resource] = not docker([*command, '--filter', 'label=io.aictrl.session=' + current.identifier]).stdout.strip()
            report = {'milestone': 'T07', 'mode': 'production-live-jev' if args.live else 'explicit-offline-semantic-fixture',
                      'session_id': str(identity.session_id), 'native_exit': code, 'event_count': len(events),
                      'checks': checks, 'passed': all(checks.values()), 'recorded_at': datetime.now(timezone.utc).isoformat()}
            folder = PROJECT_ROOT / '.aictrl/qualifications'
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            report_path = folder / ('t07-governance-live.json' if args.live else 't07-governance-docker.json')
            report_path.write_text(json.dumps(report, indent=2))
            report_path.chmod(0o600)
            print('AICTRL_T07_GOVERNANCE_DOCKER ' + json.dumps(report, sort_keys=True), flush=True)
            print('T07 GOVERNANCE DEMO ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
            return 0 if report['passed'] else 1
    except Exception:
        print('T07 GOVERNANCE DEMO FAIL: configuration, provider or host coordination unavailable.', flush=True)
        return 1
    finally:
        stop.set()
        if coordinator:
            coordinator.join(timeout=1)
        if current:
            current.close()
        if previous_key is None:
            os.environ.pop('AICTRL_JEV_API_KEY', None)
        else:
            os.environ['AICTRL_JEV_API_KEY'] = previous_key


if __name__ == '__main__':
    raise SystemExit(main())
