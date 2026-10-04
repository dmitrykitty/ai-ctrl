"""Explicit production Claude qualification, safe fixed prompt, no retry loop."""

import argparse
import json
import os
import re
import sqlite3
import subprocess
from uuid import UUID

from aictrl.reporting.queries import ReportingQueries
from aictrl.reporting.store import EventStore
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import cleanup_checks, save_report

EXPECTED = 'AICTRL_FINAL_OK'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Run one actual Claude subscription session with the fixed prompt.')
    args = parser.parse_args()
    if not args.live:
        print('PENDING: explicitly select --live for the production Claude proof.')
        return 2
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    env.pop('AICTRL_JEV_KEY_FILE', None)
    print('FINAL CLAUDE: native subscription, unchanged production boundary, fixed safe prompt; no Jev call.', flush=True)
    try:
        result = subprocess.run([str(PROJECT_ROOT / '.venv/bin/aictrl'), 'run', 'claude', str(PROJECT_ROOT / 'demo/project'),
                                 '--prompt', 'Reply with exactly: ' + EXPECTED, '--timeout', '90'],
                                cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120)
        found = re.search(r'AICTRL session ([a-f0-9]{32}):', result.stdout)
        if not found:
            raise ValueError('Managed session unavailable.')
        session = UUID(found.group(1))
        path = PROJECT_ROOT / '.aictrl/audit/events.sqlite3'
        events = EventStore(path).events(session)
        queries = ReportingQueries(path, PROJECT_ROOT)
        admissions = {event.request_id for event in events if event.action == 'ALLOW'}
        completions = {event.request_id for event in events if event.reason_code == 'llm.upstream_completed'}
        with sqlite3.connect(path) as db:
            lifecycle = db.execute('SELECT state,started_at,ended_at FROM sessions WHERE session_id=?', (str(session),)).fetchone()
            reservations = db.execute('SELECT state,usage_json FROM reservations WHERE session_id=?', (str(session),)).fetchall()
            dimensions = {row[0] for row in db.execute('''SELECT DISTINCT c.dimension FROM reservation_claims c JOIN reservations r
                USING(reservation_id) WHERE r.session_id=?''', (str(session),))}
        metrics = queries.latency(session)
        checks = {'native_exit_zero': result.returncode == 0, 'exact_response': EXPECTED in result.stdout.splitlines(),
                  'durable_allow_and_completion': bool(admissions) and admissions == completions,
                  'no_block_or_failure': not any(event.action == 'BLOCK' or event.reason_code in ('llm.upstream_failed', 'llm.output_blocked') for event in events),
                  'governance_request_step_token_claims': bool(reservations) and {'requests', 'agent_steps', 'tokens'} <= dimensions,
                  'governance_settled_or_conservative_unknown': bool(reservations) and all(row[0] in ('SETTLED', 'UNKNOWN') for row in reservations),
                  'numeric_usage_settled_when_present': all(row[0] == 'SETTLED' for row in reservations if row[1]),
                  'lifecycle_terminated': lifecycle is not None and lifecycle[0] == 'TERMINATED' and bool(lifecycle[1]) and bool(lifecycle[2]),
                  'separate_latency_persisted': all(metrics[stage]['count'] > 0 for stage in ('deterministic_guards', 'governance', 'upstream_stream', 'total')),
                  'no_critical_alert': not any(item['severity'] == 'CRITICAL' for item in queries.alerts(session)['items']),
                  'shared_event_schema_one': all(event.schema_version == 1 for event in events)}
        checks.update(cleanup_checks(session.hex))
        report = {'milestone': 'T09', 'session_id': str(session), 'native_exit': result.returncode,
                  'event_count': len(events), 'checks': checks, 'passed': all(checks.values()),
                  'redactions': sum(event.action == 'REDACT' for event in events),
                  'latency': metrics, 'reservations': [{'state': row[0], 'usage': json.loads(row[1]) if row[1] else None} for row in reservations]}
        save_report('final-claude', report)
        print(EXPECTED if checks['exact_response'] else 'Exact response missing.', flush=True)
        print('AICTRL_FINAL_CLAUDE ' + json.dumps({name: report[name] for name in ('session_id', 'native_exit', 'event_count', 'redactions', 'checks', 'passed')}, sort_keys=True), flush=True)
        print('FINAL CLAUDE ' + ('PASS' if report['passed'] else 'FAIL') + '; no automatic retry.', flush=True)
        return 0 if report['passed'] else 1
    except Exception:
        print('FINAL CLAUDE FAIL: native/provider/control unavailable; no raw output persisted and no automatic retry.', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
