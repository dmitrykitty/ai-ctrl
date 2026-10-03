#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="$task_root/.tools/cache"
export UV_PYTHON_INSTALL_DIR="$task_root/.tools/python"
if [[ -x "$task_root/.tools/uv/bin/uv" ]]; then
    exec "$task_root/.tools/uv/bin/uv" "$@"
fi
exec uv "$@"
