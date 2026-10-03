#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
if [[ ! -x .tools/uv/bin/uv ]] && ! command -v uv >/dev/null; then
    python3 -m pip install --no-deps --index-url https://pypi.org/simple --target .tools/uv 'uv==0.12.22'
fi
./scripts/uv.sh python install --no-bin "$(cat .python-version)"
./scripts/uv.sh sync --frozen
