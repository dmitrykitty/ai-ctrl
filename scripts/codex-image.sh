#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_context="$(mktemp -d /tmp/aictrl-codex-build-XXXXXXXX)"
trap 'rm -rf -- "$task_context"' EXIT
mkdir "$task_context/base" "$task_context/codex"
cp docker/base/entrypoint.sh docker/base/prepare-codex-profile.py "$task_context/base/"
cp docker/codex/Dockerfile docker/codex/aictrl.config.toml docker/codex/LICENSE.openai-codex \
    docker/codex/COPYING.bubblewrap docker/codex/LICENSE.bubblewrap "$task_context/codex/"
docker build --file "$task_context/codex/Dockerfile" --tag aictrl-codex:0.159.3-t05 "$task_context"
python3 scripts/record-image.py codex aictrl-codex:0.159.3-t05
