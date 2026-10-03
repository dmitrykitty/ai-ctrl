#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
if [[ ! -t 0 || ! -t 1 ]]; then
    echo 'Claude login requires an interactive terminal: make claude-login' >&2
    exit 1
fi
if [[ -n "$(docker ps --filter volume=aictrl-claude-state --format '{{.ID}}')" ]]; then
    echo 'Claude state volume is already attached to an active container' >&2
    exit 1
fi
docker volume create aictrl-claude-state >/dev/null
task_compose=(docker compose -f docker/compose.auth.yaml)
task_cleanup() { "${task_compose[@]}" down --remove-orphans >/dev/null; }
trap task_cleanup EXIT
"${task_compose[@]}" up --detach --wait auth-proxy
echo 'Open the native login URL in your host browser; enter any code in this terminal only.'
# The native flow needs no enterprise secrets or host configuration mounts.
# Keep provider state on cancellation and enforce a ten-minute bootstrap limit.
timeout --foreground --signal=TERM --kill-after=10s 600 \
    "${task_compose[@]}" run --rm --name aictrl-claude-auth --no-deps claude-login
