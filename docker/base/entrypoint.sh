#!/usr/bin/env bash
# Adapted from agent-sandbox images/base/entrypoint.sh (MIT, Matt Olson 2026).
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Trusted root bootstrap is required' >&2; exit 1; }
case "${AICRTL_BOOTSTRAP_MODE:-}" in
    auth)
        # The bootstrap login path cannot be turned into an agent launch.
        [[ "$#" == 4 && "$1" == claude && "$2" == auth && "$3" == login && "$4" == --claudeai ]] || {
            echo 'Authentication bootstrap permits only claude auth login --claudeai' >&2
            exit 1
        }
        ;;
    runtime)
        echo 'Runtime startup is not implemented yet — milestone T02' >&2
        exit 2
        ;;
    *) echo 'Explicit restricted bootstrap mode required' >&2; exit 1 ;;
esac
/usr/local/bin/init-firewall.sh
if [[ -f /etc/aictrl/proxy-ca.pem ]]; then
    /usr/local/bin/install-proxy-ca.sh
fi
mkdir -p /home/dev/.claude
chown 501:501 /home/dev/.claude
chmod 700 /home/dev/.claude
exec setpriv --reuid=501 --regid=501 --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs "$@"
