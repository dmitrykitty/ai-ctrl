#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
if ! docker image inspect aictrl-claude:2.1.285-t02 >/dev/null 2>&1; then
    ./scripts/claude-image.sh
fi
docker build --file docker/base/Dockerfile.runtime --tag aictrl-claude:2.1.285-t03 docker/base
python3 scripts/record-image.py claude_runtime aictrl-claude:2.1.285-t03
