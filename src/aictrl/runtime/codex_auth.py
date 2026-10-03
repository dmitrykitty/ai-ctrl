"""Offline native ChatGPT status; credentials never leave provider storage."""
import subprocess

from aictrl.runtime.auth import AuthenticationCheckError

CODEX_IMAGE = 'aictrl-codex:0.159.3-t05'
CODEX_STATE = 'aictrl-codex-state'
CODEX_AUTH_CONTAINER = 'aictrl-codex-auth'
STATUS_COMMAND = (
    'task_uid=$(stat -c %u /home/dev/.codex); task_gid=$(stat -c %g /home/dev/.codex); '
    '[[ "$task_uid" != 0 && "$task_gid" != 0 ]] || exit 2; '
    'exec setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups '
    '--bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs '
    'codex --no-daemon -c \'log_dir="/tmp/codex-status"\' login status'
)


def codex_authenticated(image: str = CODEX_IMAGE) -> bool:
    try:
        active = subprocess.run(
            ['docker', 'ps', '--filter', f'volume={CODEX_STATE}', '--format', '{{.ID}}'],
            capture_output=True, text=True, check=False, timeout=15,
        )
        if active.returncode:
            raise AuthenticationCheckError('Cannot check Codex state: Docker is unavailable.')
        if active.stdout.strip():
            raise AuthenticationCheckError('Codex state is in use; stop its active container before checking authentication.')
        result = subprocess.run(
            ['docker', 'run', '--rm', '--name', CODEX_AUTH_CONTAINER,
             '--network', 'none', '--cap-drop', 'ALL', '--cap-add', 'SETUID',
             '--cap-add', 'SETGID', '--cap-add', 'SETPCAP',
             '--security-opt', 'no-new-privileges:true', '--user', '0:0',
             '--env', 'HOME=/home/dev', '--env', 'CODEX_HOME=/home/dev/.codex',
             '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
             '--mount', f'type=volume,source={CODEX_STATE},target=/home/dev/.codex,readonly',
             '--entrypoint', '/bin/bash', image, '-ec', STATUS_COMMAND],
            capture_output=True, text=True, check=False, timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AuthenticationCheckError('Native Codex authentication status is unavailable.') from None
    # Native status text stays private, including any API-key diagnostic.
    output = result.stdout + result.stderr
    if result.returncode == 0 and 'Logged in using ChatGPT' in output:
        return True
    if result.returncode == 1 and 'Not logged in' in output:
        return False
    raise AuthenticationCheckError('Native Codex status failed or stored authentication is not ChatGPT.')


def main() -> int:
    try:
        authenticated = codex_authenticated()
    except AuthenticationCheckError as error:
        print(str(error))
        return 2
    print('Codex is already authenticated with ChatGPT.' if authenticated else
          'Codex is not authenticated. Run: make codex-login')
    return 0 if authenticated else 1


if __name__ == '__main__':
    raise SystemExit(main())
