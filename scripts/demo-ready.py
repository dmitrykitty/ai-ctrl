"""Fast warm preflight. Checks only; no installs, image rebuilds or LLM calls."""

import argparse
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

from aictrl.guards.threat_feed import load_feed
from aictrl.policy.loader import load_policy
from aictrl.reporting.service import ReportingStore
from aictrl.governance.store import GovernanceStore
from aictrl.runtime.config import load_config
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import save_report


def command(args: list[str], *, timeout: float = 12):
    return subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout)


def preflight(port: int) -> dict:
    checks: dict[str, bool] = {}
    hints: dict[str, str] = {}
    def check(name, operation, hint):
        try:
            checks[name] = bool(operation())
        except Exception:
            checks[name] = False
        if not checks[name]:
            hints[name] = hint
    check('python_frozen_environment', lambda: sys.version_info[:2] == (3, 12) and command(
        [str(PROJECT_ROOT / 'scripts/uv.sh'), 'sync', '--frozen', '--offline', '--check']).returncode == 0,
        'Run make bootstrap, then ./scripts/uv.sh sync --frozen.')
    check('docker_daemon', lambda: command(['docker', 'version', '--format', '{{.Server.Version}}']).returncode == 0,
          'Start Docker and check docker version.')
    settings = load_config(PROJECT_ROOT)
    lock = json.loads((PROJECT_ROOT / 'docker/images.lock.json').read_text())
    images = {'base': (lock['base_local_ref'], 'make bootstrap'),
              'claude_runtime': (settings.claude.image, 'make runtime-image'),
              'proxy': (settings.runtime.proxy_image, 'make proxy-image'),
              'gateway': (settings.gateway.image, 'make gateway-image'),
              'demo': (settings.demo.image, 'make demo-image')}
    for component, (reference, hint) in images.items():
        def image_check(reference=reference, component=component):
            result = command(['docker', 'image', 'inspect', reference, '--format', '{{.Id}}'])
            return result.returncode == 0 and result.stdout.strip() == lock[component + '_image_id']
        check('image_' + component, image_check, hint)
    # Native read-only status runs in its dedicated volume with network=none.
    # No auth file is opened here and no raw status JSON is printed.
    check('claude_authenticated', lambda: command([sys.executable, '-c',
          'import sys; from aictrl.runtime.auth import claude_authenticated; sys.exit(0 if claude_authenticated(sys.argv[1]) else 1)',
          settings.claude.image]).returncode == 0,
          'Run make claude-auth-status; if unauthenticated, make claude-login.')
    check('policy_valid', lambda: load_policy(PROJECT_ROOT / 'config/policy.yaml') is not None,
          'Validate config/policy.yaml (schema5).')
    check('threat_feed_valid', lambda: load_feed(PROJECT_ROOT / 'config/threat-feed.json') is not None,
          'Validate config/threat-feed.json (schema1).')
    def audit_write():
        folder = PROJECT_ROOT / settings.gateway.audit_directory
        if folder.resolve() != folder or folder.is_symlink():
            return False
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
        path = folder / 'events.sqlite3'
        ReportingStore(path)
        GovernanceStore(path)
        with sqlite3.connect(path, timeout=2) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('SELECT 1')
            db.rollback()
        return True
    check('audit_writable', audit_write, 'Check the protected .aictrl/audit directory and disk space.')
    check('local_dashboard_assets', lambda: all((PROJECT_ROOT / 'src/aictrl/dashboard' / name).is_file()
          for name in ('templates/dashboard.html', 'assets/dashboard.css', 'assets/dashboard.js')),
          'Restore the checked-in dashboard templates/assets.')
    def available():
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', port))
        return True
    check('dashboard_port_available', available, 'Stop your existing dashboard or use a different --port.')
    def no_sessions():
        result = command(['docker', 'ps', '--filter', 'label=io.aictrl.managed=true', '--format', '{{.ID}}'])
        return result.returncode == 0 and not result.stdout.strip()
    check('no_active_managed_sessions', no_sessions,
        'Stop the active managed session before rehearsing.')
    return {'checks': checks, 'hints': hints, 'passed': all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        print('DEMO READY FAIL: invalid port.')
        return 1
    started = time.perf_counter()
    try:
        report = preflight(args.port)
    except Exception:
        print('DEMO READY FAIL: project configuration unavailable.')
        return 1
    report['seconds'] = round(time.perf_counter() - started, 3)
    save_report('demo-ready', report)
    for name, passed in report['checks'].items():
        print(('PASS ' if passed else 'FAIL ') + name + ('' if passed else ': ' + report['hints'][name]))
    print('DEMO READY ' + ('PASS' if report['passed'] else 'FAIL') + f" ({report['seconds']:.2f}s; no rebuilds/provider calls)")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
