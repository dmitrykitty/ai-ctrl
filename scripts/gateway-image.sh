#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_context="$(mktemp -d /tmp/aictrl-gateway-build-XXXXXXXX)"
trap 'rm -rf -- "$task_context"' EXIT
# Send only code and locked public dependencies to Docker, never the checkout.
./scripts/uv.sh export --frozen --no-dev --no-emit-project --no-header \
    --format requirements-txt --output-file "$task_context/requirements.txt" >/dev/null
python3 - "$task_context" <<'PY'
import shutil, sys
from pathlib import Path
context = Path(sys.argv[1])
shutil.copytree('src', context / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copyfile('docker/gateway/Dockerfile', context / 'Dockerfile')
PY
docker build --tag aictrl-gateway:t07 "$task_context"
python3 scripts/record-image.py gateway aictrl-gateway:t07
