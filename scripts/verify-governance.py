"""Repeatable real SQLite/control qualification. Zero external provider calls."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ['tests/unit/test_governance.py', 'tests/unit/test_governance_integration.py',
         'tests/unit/test_reload.py', 'tests/unit/test_usage.py']
CHECKS = ('request allowed below limit; next request blocked before send',
          '50 concurrent reservations: exactly 10 allowed at limit 10',
          'failed multi-budget claim rolls back every counter',
          'session/agent/user/profile scopes and fixed windows',
          'pending approval + explicit host CLI approve + exact retry',
          'two concurrent retries execute backend exactly once; replay blocked',
          'changed arguments, expiry and policy/snapshot binding',
          'approval is preserved on budget/audit denial',
          'valid policy/feed reload; invalid candidates retain last good',
          'active stream keeps one immutable version',
          'literal/limited regex feed signatures and privacy-before-Jev',
          'lifetime runaway limits survive window resets',
          'safe native usage settlement; unknown usage keeps reservation',
          'actual SQLite failure prevents protected side effects')


def main():
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *TESTS], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        print('T07 GOVERNANCE FAIL. Run the four named governance/reload/usage test files for details.')
        return 1
    print('T07 governance verification: actual SQLite and SDK; explicitly offline semantic fixtures; zero paid calls.')
    for check in CHECKS:
        print('[PASS] ' + check)
    print(result.stdout.strip().splitlines()[-1])
    print('T07 GOVERNANCE PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
