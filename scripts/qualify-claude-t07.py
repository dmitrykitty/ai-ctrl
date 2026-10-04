"""Exactly one explicitly invoked native Claude smoke; no automatic retry."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from uuid import UUID

from aictrl.reporting.store import EventStore
from aictrl.runtime.docker import docker
from aictrl.runtime.workspace import PROJECT_ROOT

EXPECTED = 'AICTRL_T07_CLAUDE_OK'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Authorize one actual native Claude run with the fixed prompt.')
    args = parser.parse_args()
    if not args.live:
        print('PENDING: use --live for exactly one real Claude smoke; no retry is performed.')
        return 2
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    print('T07 Claude qualification: one native subscription invocation; fixed smoke prompt; no Jev call.', flush=True)
    result = subprocess.run([str(PROJECT_ROOT / '.venv/bin/aictrl'), 'run', 'claude', str(PROJECT_ROOT / 'demo/project'),
                             '--prompt', 'Reply with exactly: ' + EXPECTED, '--timeout', '90'],
                            env=env, capture_output=True, text=True, timeout=120)
    found = re.search(r'AICTRL session ([a-f0-9]{32}):', result.stdout)
    if found is None:
        print('T07 CLAUDE FAIL: managed session unavailable; no automatic retry.', flush=True)
        return 1
    session = UUID(found.group(1))
    store = EventStore(PROJECT_ROOT / '.aictrl/audit/events.sqlite3')
    events = store.events(session)
    completions = [event for event in events if event.reason_code == 'llm.upstream_completed']
    admissions = [event for event in events if event.action == 'ALLOW']
    blocks = [event for event in events if event.action == 'BLOCK']
    with sqlite3.connect(store.path) as db:
        rows = db.execute('SELECT reservation_id,request_id,state,usage_json FROM reservations WHERE session_id=?', (str(session),)).fetchall()
        dimensions = {row[0] for row in db.execute('''SELECT DISTINCT c.dimension FROM reservation_claims c JOIN reservations r
            ON c.reservation_id=r.reservation_id WHERE r.session_id=?''', (str(session),))}
    checks = {'native_exit_zero': result.returncode == 0, 'exact_response': EXPECTED in result.stdout.splitlines(),
              'durable_allow_completion': bool(admissions) and bool(completions) and
                  {event.request_id for event in completions} <= {event.request_id for event in admissions},
              'no_blocked_or_failed_request': not blocks and not any(event.reason_code in ('llm.upstream_failed', 'llm.output_blocked') for event in events),
              'budget_reserved_request_step_tokens': bool(rows) and {'requests', 'agent_steps', 'tokens'} <= dimensions,
              'reservation_final_state': bool(rows) and all(row[2] in ('SETTLED', 'UNKNOWN') for row in rows),
              'usage_settled_when_available': all(row[2] == 'SETTLED' for row in rows if row[3] is not None),
              'shared_event_schema_one': all(event.schema_version == 1 for event in events)}
    for resource in ('container', 'network', 'volume'):
        command = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        checks['cleanup_' + resource] = not docker([*command, '--filter', 'label=io.aictrl.session=' + session.hex]).stdout.strip()
    redactions = [event for event in events if event.action == 'REDACT']
    report = {'milestone': 'T07', 'session_id': str(session), 'native_exit': result.returncode,
              'checks': checks, 'passed': all(checks.values()), 'redaction_count': len(redactions),
              'events': [event.model_dump(mode='json') for event in events],
              'reservations': [{'reservation_id': row[0], 'request_id': row[1], 'state': row[2],
                                'usage': json.loads(row[3]) if row[3] else None} for row in rows],
              'recorded_at': datetime.now(timezone.utc).isoformat()}
    path = PROJECT_ROOT / '.aictrl/qualifications/t07-claude.json'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(report, indent=2))
    path.chmod(0o600)
    print(EXPECTED if checks['exact_response'] else 'Exact response missing.', flush=True)
    print('AICTRL_T07_CLAUDE ' + json.dumps({key: report[key] for key in ('session_id', 'native_exit', 'checks', 'passed', 'redaction_count')}, sort_keys=True), flush=True)
    print('T07 CLAUDE ' + ('PASS' if report['passed'] else 'FAIL') + '; no automatic retry.', flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
