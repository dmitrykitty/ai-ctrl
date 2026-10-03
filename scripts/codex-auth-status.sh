#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
exec ./scripts/uv.sh run --frozen python -m aictrl.runtime.codex_auth
