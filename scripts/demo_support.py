"""Explicit host-only fixture orchestration; never imported by production."""

from datetime import datetime, timezone
import json
from pathlib import Path

from aictrl.guards.threat_feed import load_feed
from aictrl.policy.loader import load_policy
from aictrl.runtime.docker import docker
from aictrl.runtime.workspace import PROJECT_ROOT


def notify_policy(path: Path) -> None:
    """Attack boundary suites qualify decisions separately from host responses."""
    policy = load_policy(path).model_dump(mode='json')
    policy['response'].update(medium='notify', high='notify', critical='notify')
    atomic(path, policy)


def atomic(path: Path, value: object) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def select_fixture(runtime, config: Path, *, semantic: bool = True) -> None:
    """Select validated temporary public config, keeping the real audit mount.

    Production policy is never changed. The same runtime, Docker boundary,
    native handlers and durable stores are used. Only the explicitly labelled
    semantic fixture replaces an external provider when semantic=True.
    """
    load_policy(config / 'policy.yaml')
    load_feed(config / 'threat-feed.json')
    manifest = json.loads(runtime.manifest.read_text())
    gateway = manifest['services']['gateway']
    mount = next(item for item in gateway['volumes'] if isinstance(item, dict) and item['target'] == '/etc/aictrl/config')
    mount['source'] = str(config.resolve())
    if semantic:
        gateway['environment']['PYTHONPATH'] = '/opt/aictrl/src:/fixtures'
        gateway['entrypoint'] = ['python', '-m', 'uvicorn', 'gateway_factory:application', '--factory',
                                '--host', '0.0.0.0', '--port', '8000', '--no-access-log', '--log-level', 'warning']
        gateway['volumes'].append({'type': 'bind', 'source': str(PROJECT_ROOT / 'tests/fixtures'),
                                   'target': '/fixtures', 'read_only': True})
    runtime.manifest.write_text(json.dumps(manifest))
    runtime._docker([*runtime.compose, 'up', '--detach', '--wait', '--force-recreate', 'gateway'], timeout=30)


def cleanup_checks(identifier: str) -> dict[str, bool]:
    checks = {}
    for resource in ('container', 'network', 'volume'):
        command = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        checks['cleanup_' + resource] = not docker([*command, '--filter', 'label=io.aictrl.session=' + identifier]).stdout.strip()
    return checks


def save_report(name: str, data: dict) -> None:
    path = PROJECT_ROOT / '.aictrl/qualifications' / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data['recorded_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)
