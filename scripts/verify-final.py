"""One offline judge orchestrating existing checks; never runs real providers."""

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from aictrl.runtime.workspace import PROJECT_ROOT
from aictrl.runtime.config import load_config
from demo_support import save_report

STAGES = (('offline', 'test', 90), ('governance', 'verify-governance', 90),
          ('reporting', 'verify-reporting', 90), ('compose', 'compose-config', 30),
          ('native_gateway_docker', 'verify-gateway-boundary', 180),
          ('mcp_boundary_docker', 'verify-demo-boundary', 180),
          ('responses_synthetic_docker', 'verify-codex-boundary', 180),
          ('governance_docker', 'verify-governance-demo', 180),
          ('owned_response_docker', 'verify-reporting-response', 180))


def main() -> int:
    started = time.perf_counter()
    env = dict(os.environ)
    env.pop('AICTRL_JEV_API_KEY', None)
    key_file = env.pop('AICTRL_JEV_KEY_FILE', None)
    stages = []
    print('AICTRL FINAL JUDGE: offline fixtures + actual Docker/SQLite; zero live Claude/Codex/Jev calls.', flush=True)
    for name, target, deadline in STAGES:
        before = time.perf_counter()
        try:
            result = subprocess.run(['make', target], cwd=PROJECT_ROOT, env=env, capture_output=True,
                                    text=True, timeout=deadline)
            passed = result.returncode == 0
            # Persist no raw process/test output, even on failure.
            matches = re.findall(r'\b(\d+) passed\b', result.stdout)
            record = {'stage': name, 'command': 'make ' + target, 'passed': passed,
                      'exit_code': result.returncode, 'seconds': round(time.perf_counter() - before, 3)}
            if matches:
                record['tests_passed'] = int(matches[-1])
        except (OSError, subprocess.TimeoutExpired):
            record = {'stage': name, 'command': 'make ' + target, 'passed': False,
                      'exit_code': None, 'seconds': round(time.perf_counter() - before, 3)}
        stages.append(record)
        print(('PASS ' if record['passed'] else 'FAIL ') + record['command'] + f" ({record['seconds']:.2f}s)", flush=True)
        if not record['passed']:
            print('Run the named failed command to diagnose it; no automatic retry.', flush=True)
            break
    checks = {}
    try:
        spec = importlib.util.spec_from_file_location('safe_final_checks', Path(__file__).with_name('final-checks.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checks = {**module.privacy(Path(key_file) if key_file else None), **module.cleanup()}
    except Exception:
        checks['privacy_cleanup_available'] = False
    report = {'milestone': load_config(PROJECT_ROOT).milestone, 'mode': 'offline-judge-no-live-provider-calls', 'stages': stages,
              'checks': checks, 'actual_key_scan': bool(key_file), 'seconds': round(time.perf_counter() - started, 3),
              'passed': len(stages) == len(STAGES) and all(item['passed'] for item in stages) and bool(checks) and all(checks.values())}
    save_report('final-judge', report)
    print(('PASS' if checks and all(checks.values()) else 'FAIL') + ' privacy and cleanup', flush=True)
    print('AICTRL FINAL JUDGE ' + ('PASS' if report['passed'] else 'FAIL') + f" ({report['seconds']:.2f}s)", flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
