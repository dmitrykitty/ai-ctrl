#!/usr/bin/env bash
# Adapted from agent-sandbox images/base/entrypoint.sh (MIT, Matt Olson 2026).
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Trusted root bootstrap is required' >&2; exit 1; }
umask 077
case "${AICTRL_ADAPTER:-claude}" in
    claude) task_state=/home/dev/.claude ;;
    codex) task_state=/home/dev/.codex ;;
    *) echo 'Unsupported provider state' >&2; exit 1 ;;
esac
case "${AICTRL_BOOTSTRAP_MODE:-}" in
    auth)
        # The bootstrap login path cannot be turned into an agent launch.
        if [[ "${AICTRL_ADAPTER:-claude}" == codex ]]; then
            task_auth_ok=false
            [[ "$#" == 4 && "$1" == codex && "$2" == --no-daemon && "$3" == login && "$4" == --device-auth ]] && task_auth_ok=true
        else
            task_auth_ok=false
            [[ "$#" == 4 && "$1" == claude && "$2" == auth && "$3" == login && "$4" == --claudeai ]] && task_auth_ok=true
        fi
        "$task_auth_ok" || {
            echo 'Authentication bootstrap permits only the native provider login command' >&2
            exit 1
        }
        task_uid=501
        task_gid=501
        ;;
    runtime)
        task_uid="${AICTRL_UID:?Runtime UID is required}"
        task_gid="${AICTRL_GID:?Runtime GID is required}"
        python - <<'PY'
import os
for name in ('AICTRL_UID', 'AICTRL_GID'):
    value = os.environ[name]
    if not value.isdecimal() or not 1 <= int(value) <= 2147483647:
        raise SystemExit('Runtime UID/GID must be positive numeric host identities')
PY
        [[ -f /etc/aictrl/proxy-ca.pem ]] || { echo 'Required public proxy CA is absent' >&2; exit 1; }
        case "${AICTRL_ROUTING_MODE:-EGRESS_ONLY}" in
            EGRESS_ONLY) ;;
            APPLICATION_GATEWAY) [[ -n "${AICTRL_GATEWAY_IP:-}" ]] || { echo 'Required gateway address is absent' >&2; exit 1; } ;;
            *) echo 'Invalid routing mode' >&2; exit 1 ;;
        esac
        ;;
    *) echo 'Explicit restricted bootstrap mode required' >&2; exit 1 ;;
esac
/usr/local/bin/init-firewall.sh
if [[ -f /etc/aictrl/proxy-ca.pem ]]; then
    /usr/local/bin/install-proxy-ca.sh
fi
mkdir -p "$task_state"
# Prevent usermod's implicit home traversal. Only the explicit no-follow state
# preparation below may change ownership; workspace links are never followed.
usermod --home /nonexistent dev
if [[ "$(id -g dev)" != "$task_gid" ]]; then
    if ! getent group "$task_gid" >/dev/null; then groupmod --gid "$task_gid" dev; fi
    usermod --gid "$task_gid" dev
fi
if [[ "$(id -u dev)" != "$task_uid" ]]; then usermod --uid "$task_uid" dev; fi
usermod --home /home/dev dev
# Only container-owned home/state is prepared; never change /workspace.
chown "$task_uid:$task_gid" /home/dev
find "$task_state" -xdev -exec chown -h "$task_uid:$task_gid" {} +
chmod 700 "$task_state"
export HOME=/home/dev USER=dev LOGNAME=dev
if [[ "$AICTRL_BOOTSTRAP_MODE" == runtime ]]; then
    setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups \
        --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
        bash -ec 'test -r /workspace && test -w /workspace' || {
            echo 'Workspace is not readable and writable by the runtime identity' >&2; exit 1;
        }
    if [[ "$1" == claude ]]; then
        setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups \
            --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
            python /usr/local/bin/prepare-claude-ui.py
    fi
    if [[ "${AICTRL_ADAPTER:-claude}" == codex ]]; then
        setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups \
            --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
            python /usr/local/bin/prepare-codex-profile.py
    fi
fi
exec setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs "$@"
