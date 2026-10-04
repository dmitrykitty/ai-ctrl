"""Safe offline privacy/cleanup checks; never open native provider state."""

import json
import os
from pathlib import Path
import re
import subprocess

from aictrl.runtime.docker import docker
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import save_report

SENTINELS = (b'AICTRL_SECRET_demo', b'user@example.com', b'Ignore previous instructions',
             b'AICTRL_PRIVATE_MEMORY_SYNTHETIC', b'synthetic_provider_credential_never_store',
             b'synthetic-provider', b'synthetic_internal_identity_abcdefghijklmnopqrstuvwxyz',
             b'synthetic_t07_gateway_mount_key', b'synthetic_jev_key_boundary_only',
             b'AICTRL_GOVERNANCE_FEED_BLOCK')


def private_key(path: Path) -> bytes:
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600 or path.parent.stat().st_mode & 0o777 != 0o700:
        raise ValueError('Private input permissions invalid.')
    value = path.read_text().strip()
    if not value.startswith('AICTRL_JEV_API_KEY=') or '\n' in value:
        raise ValueError('Private input invalid.')
    result = value.split('=', 1)[1].strip().strip('"').strip("'").encode()
    if not result:
        raise ValueError('Private input empty.')
    return result


def privacy(key_file: Path | None = None) -> dict[str, bool]:
    key = private_key(key_file) if key_file else None
    files = [* (PROJECT_ROOT / '.aictrl/audit').glob('events.sqlite3*'),
             * (PROJECT_ROOT / '.aictrl/qualifications').glob('*.json')]
    files = [item for item in files if item.is_file() and not item.is_symlink()]
    checks = {'safe_sqlite_reports': all(not any(value in item.read_bytes() for value in SENTINELS) for item in files)}
    if key:
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=PROJECT_ROOT).split(b'\0')
        source = [PROJECT_ROOT / name.decode() for name in names if name]
        checks['actual_jev_key_absent'] = all(key not in item.read_bytes() for item in [*source, *files] if item.is_file() and not item.is_symlink())
    return checks


def cleanup() -> dict[str, bool]:
    checks = {}
    for resource in ('container', 'network', 'volume'):
        command = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        result = docker([*command, '--filter', 'label=io.aictrl.session'], check=False)
        checks['no_session_' + resource] = result.returncode == 0 and not result.stdout.strip()
    directories = [item for item in Path('/tmp').glob('aictrl-*') if item.is_dir() and re.fullmatch(r'aictrl-[a-f0-9]{32}-.+', item.name)]
    checks['no_ephemeral_identity_directories'] = not directories
    checks['no_ephemeral_gateway_jev_files'] = not any((item / 'jev_api_key').exists() for item in directories)
    checks['provider_volumes_preserved'] = all(docker(['volume', 'inspect', name, '--format', '{{.Name}}'], check=False).returncode == 0
                                               for name in ('aictrl-claude-state', 'aictrl-codex-state'))
    checks['project_workspace_preserved'] = (PROJECT_ROOT / 'demo/project').is_dir()
    return checks


def main() -> int:
    try:
        key = os.environ.get('AICTRL_JEV_KEY_FILE')
        checks = {**privacy(Path(key) if key else None), **cleanup()}
        passed = all(checks.values())
        save_report('final-privacy-cleanup', {'checks': checks, 'passed': passed, 'actual_key_scan': bool(key)})
        print('AICTRL PRIVACY CLEANUP ' + json.dumps(checks, sort_keys=True))
        print('PRIVACY CLEANUP ' + ('PASS' if passed else 'FAIL'))
        return 0 if passed else 1
    except Exception:
        print('PRIVACY CLEANUP FAIL: protected source, reporting or Docker unavailable.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
