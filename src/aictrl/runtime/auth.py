"""Read native Claude authentication status without exporting provider data."""

import json
import subprocess

CLAUDE_IMAGE = "aictrl-claude:2.1.285-t02"
CLAUDE_STATE = "aictrl-claude-state"
AUTH_CONTAINER = "aictrl-claude-auth"

STATUS_COMMAND = (
    'task_uid=$(stat -c %u /home/dev/.claude); task_gid=$(stat -c %g /home/dev/.claude); '
    '[[ "$task_uid" != 0 && "$task_gid" != 0 ]] || exit 2; '
    'exec setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups '
    '--bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs '
    'claude auth status --json'
)


class AuthenticationCheckError(RuntimeError):
    pass


def claude_authenticated(image: str = CLAUDE_IMAGE) -> bool:
    try:
        active = subprocess.run(
            ["docker", "ps", "--filter", f"volume={CLAUDE_STATE}", "--format", "{{.ID}}"],
            capture_output=True, text=True, check=False,
        )
        if active.returncode:
            raise AuthenticationCheckError("Cannot check Claude state: Docker is unavailable.")
        if active.stdout.strip():
            raise AuthenticationCheckError("Claude state is in use; stop its active container before checking authentication.")
        result = subprocess.run(
            ["docker", "run", "--rm", "--name", AUTH_CONTAINER,
             "--network", "none", "--cap-drop", "ALL",
             "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "SETPCAP",
             "--security-opt", "no-new-privileges:true", "--user", "0:0",
             "--env", "HOME=/home/dev",
             "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
             "--mount", f"type=volume,source={CLAUDE_STATE},target=/home/dev/.claude,readonly",
             "--entrypoint", "/bin/bash", image, "-ec", STATUS_COMMAND],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        raise AuthenticationCheckError("Cannot check Claude state: Docker could not be started.") from None
    try:
        status = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise AuthenticationCheckError("Native Claude authentication status is unavailable.") from None
    if not isinstance(status, dict) or type(status.get("loggedIn")) is not bool:
        raise AuthenticationCheckError("Native Claude authentication status is invalid.")
    if result.returncode == 0 and status["loggedIn"]:
        return True
    if result.returncode in (0, 1) and not status["loggedIn"]:
        return False
    raise AuthenticationCheckError("Native Claude authentication status failed.")


def main() -> int:
    try:
        authenticated = claude_authenticated()
    except AuthenticationCheckError as error:
        print(str(error))
        return 2
    print("Claude is already authenticated." if authenticated else "Claude is not authenticated. Run: make claude-login")
    return 0 if authenticated else 1


if __name__ == "__main__":
    raise SystemExit(main())
