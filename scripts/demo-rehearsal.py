"""One deterministic real-Docker rehearsal; explicit offline semantic fixture."""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from aictrl.reporting.queries import ReportingQueries
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import save_report


@contextmanager
def demo_lock():
    path = PROJECT_ROOT / '.aictrl/demo.lock'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('Unsafe demo lock.')
    with path.open('a') as stream:
        path.chmod(0o600)
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def main() -> int:
    started = time.perf_counter()
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    stages = [('guards', 'verify-demo-boundary.py'), ('governance', 'verify-governance-demo.py'),
              ('response', 'verify-reporting-response.py')]
    checks: dict[str, bool] = {}
    seconds: dict[str, float] = {}
    print('DEMO REHEARSAL: actual Docker/MCP/SQLite/host CLI; explicit offline semantic fixture; zero live LLM/Jev calls.', flush=True)
    try:
        with demo_lock():
            for name, script in stages:
                before = time.perf_counter()
                result = subprocess.run([sys.executable, str(PROJECT_ROOT / 'scripts' / script), '--history'],
                                        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=180)
                seconds[name] = round(time.perf_counter() - before, 3)
                checks[name] = result.returncode == 0
                print(('PASS ' if checks[name] else 'FAIL ') + name + f" ({seconds[name]:.2f}s)", flush=True)
                if not checks[name]:
                    break
            queries = ReportingQueries(PROJECT_ROOT / '.aictrl/audit/events.sqlite3', PROJECT_ROOT)
            summary = queries.summary()
            checks['dashboard_data'] = all(summary[key] > 0 for key in ('sessions', 'blocked', 'redacted', 'approval_events', 'alerts'))
            checks['durable_demo_history'] = sum(item['kind'] == 'offline-demo' and item['state'] == 'TERMINATED'
                                                 for item in queries.sessions()['items']) >= 4
            checks['completed_response_visible'] = any(item['response'] == 'terminate' and item['response_completed_at']
                                                      for item in queries.alerts()['items'])
    except Exception:
        checks['control_available'] = False
    report = {'mode': 'actual-docker-explicit-offline-semantic-fixture', 'checks': checks, 'stage_seconds': seconds,
              'seconds': round(time.perf_counter() - started, 3), 'passed': len(seconds) == 3 and all(checks.values())}
    save_report('demo-rehearsal', report)
    for name in ('dashboard_data', 'durable_demo_history', 'completed_response_visible'):
        if name in checks:
            print(('PASS ' if checks[name] else 'FAIL ') + name, flush=True)
    print('AICTRL DEMO REHEARSAL ' + ('PASS' if report['passed'] else 'FAIL') + f" ({report['seconds']:.2f}s)", flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
