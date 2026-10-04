"""Deterministic reporting/privacy/response qualification; no provider calls."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ['tests/unit/test_reporting.py', 'tests/unit/test_reporting_integration.py', 'tests/unit/test_dashboard.py']


def main() -> int:
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *TESTS], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        print('T08 REPORTING FAIL. Run the three reporting/dashboard test files for details.')
        return 1
    print('T08 reporting: durable real SQLite, native SSE and official MCP SDK; explicitly offline provider fixtures.')
    print(result.stdout.strip().splitlines()[-1])
    print('AICTRL T08 REPORTING PASS: counters, sessions, latency, risk, alerts, restrict/terminate, routes, privacy and cleanup.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
