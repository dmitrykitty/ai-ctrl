#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
docker build --tag aictrl-base:py3.12.15-t01 docker/base
docker build --tag aictrl-claude:2.1.285-t01 docker/claude
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true \
    --user 501:501 --entrypoint claude aictrl-claude:2.1.285-t01 --version
docker volume create aictrl-claude-state >/dev/null
python3 - <<'PY'
import json
import subprocess
from pathlib import Path
lock_path = Path('docker/images.lock.json')
lock = json.loads(lock_path.read_text())
for component in ('base', 'claude'):
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', lock[f'{component}_local_ref']]))[0]
    lock[f'{component}_image_id'] = info['Id']
    lock[f'{component}_repo_digests'] = info['RepoDigests']
lock_path.write_text(json.dumps(lock, indent=2) + '\n')
PY
