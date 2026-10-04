#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_context="$(mktemp -d /tmp/aictrl-demo-build-XXXXXXXX)"
trap 'rm -rf -- "$task_context"' EXIT
# Export the official client and its locked dependency closure only.
./scripts/uv.sh export --frozen --only-group demo --no-emit-project --no-header \
    --format requirements-txt --output-file "$task_context/requirements.txt" >/dev/null
cp docker/demo/Dockerfile "$task_context/Dockerfile"
cp docker/base/entrypoint.sh "$task_context/entrypoint.sh"
cp docker/base/init-firewall.sh "$task_context/init-firewall.sh"
cp demo/agent/main.py "$task_context/main.py"
cp demo/agent/governance.py "$task_context/governance.py"
docker build --tag aictrl-demo:t07 "$task_context"
python3 scripts/record-image.py demo aictrl-demo:t07
