#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
if [[ -n "$(docker ps --filter volume=aictrl-claude-state --format '{{.ID}}')" ]]; then
    echo 'Stop the active Claude state container before boundary verification' >&2
    exit 1
fi
task_compose=(docker compose -f docker/compose.auth.yaml)
task_cleanup() { "${task_compose[@]}" down --remove-orphans >/dev/null; }
trap task_cleanup EXIT
"${task_compose[@]}" up --detach --wait auth-proxy
# Host-controlled probe uses the actual reused firewall and privilege drop.
# It mounts one read-only synthetic probe file and no provider state/workspace.
docker run --rm --network aictrl-auth_auth-internal \
    --cap-drop ALL --cap-add NET_ADMIN --cap-add NET_RAW --cap-add SETUID \
    --cap-add SETGID --cap-add SETPCAP --security-opt no-new-privileges:true \
    --env AICTRL_BOOTSTRAP_MODE=auth --env AICTRL_PROXY_IP=172.30.88.2 \
    --mount "type=bind,source=$task_root/tests/fixtures/auth_boundary_probe.py,target=/opt/aictrl/auth-boundary-probe.py,readonly" \
    --entrypoint /bin/bash aictrl-base:py3.12.15-t01 -ec \
    '/usr/local/bin/init-firewall.sh; exec setpriv --reuid=501 --regid=501 --clear-groups --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs python /opt/aictrl/auth-boundary-probe.py'
