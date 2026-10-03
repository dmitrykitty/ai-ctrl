#!/usr/bin/env bash
set -euo pipefail
if [[ -n "$(docker ps --filter volume=aictrl-claude-state --format '{{.ID}}')" ]]; then
    echo 'Stop the active Claude state container before persistence verification' >&2
    exit 1
fi
docker volume create aictrl-claude-state >/dev/null
task_marker=".aictrl-probe-$(python3 -c 'import uuid; print(uuid.uuid4())')"
task_args=(--rm --network none --cap-drop ALL --security-opt no-new-privileges:true
    --user 0:0 --cap-add SETUID --cap-add SETGID --cap-add SETPCAP
    --mount type=volume,source=aictrl-claude-state,target=/home/dev/.claude
    --env "AICTRL_STATE_PROBE=$task_marker" --entrypoint /bin/bash aictrl-claude:2.1.285-t02)
task_drop='task_uid=$(stat -c %u /home/dev/.claude); task_gid=$(stat -c %g /home/dev/.claude); [[ "$task_uid" != 0 && "$task_gid" != 0 ]]; exec setpriv --reuid="$task_uid" --regid="$task_gid" --clear-groups --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs bash -ec "$1"'
docker run "${task_args[@]}" -ec \
    "$task_drop" -- 'test "$CLAUDE_CONFIG_DIR" = /home/dev/.claude; printf prepared > "$CLAUDE_CONFIG_DIR/$AICTRL_STATE_PROBE"'
docker run "${task_args[@]}" -ec \
    "$task_drop" -- 'test "$(cat "$CLAUDE_CONFIG_DIR/$AICTRL_STATE_PROBE")" = prepared; rm "$CLAUDE_CONFIG_DIR/$AICTRL_STATE_PROBE"; printf "Claude named state survived container restart; owner "; stat -c "%u:%g" "$CLAUDE_CONFIG_DIR"'
