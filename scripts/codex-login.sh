#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_status=0
bash scripts/codex-auth-status.sh || task_status=$?
case "$task_status" in
    0) exit 0 ;;
    1) ;;
    *) exit "$task_status" ;;
esac
if [[ ! -t 0 || ! -t 1 ]]; then
    echo 'Codex login requires an interactive terminal: make codex-login' >&2
    exit 1
fi
if [[ -n "$(docker ps --filter volume=aictrl-codex-state --format '{{.ID}}')" ]]; then
    echo 'Codex state volume is already attached to an active container' >&2
    exit 1
fi
docker volume create aictrl-codex-state >/dev/null
task_compose=(docker compose -f docker/compose.codex-auth.yaml)
task_cleanup() { "${task_compose[@]}" down --remove-orphans >/dev/null; }
trap task_cleanup EXIT
"${task_compose[@]}" up --detach --wait auth-proxy
echo 'Open the native device-login URL in your browser and enter the code there.'
timeout --foreground --signal=TERM --kill-after=10s 600 \
    "${task_compose[@]}" run --rm --name aictrl-codex-auth --no-deps codex-login
